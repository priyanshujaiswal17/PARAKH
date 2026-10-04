"""Pipeline orchestrator for Label Reader."""

from __future__ import annotations

import logging
import sys
import time
from datetime import date
from typing import Any, Iterator
from PIL import Image

if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from config import settings
from pipeline.explain import generate_explanation
from pipeline.expiry import evaluate as evaluate_expiry
from pipeline.extract import extract_label_data
from pipeline.guards import check_food_label, check_medicine, check_supplement
from pipeline.models import AnalysisResult, ExtractResult, IngredientRating, Summary, VerifiedItem
from pipeline.nutrition import evaluate_nutrition
from pipeline.preprocess import preprocess_images
from pipeline.qa import answer_question
from pipeline.ratings import rate_ingredients
from pipeline.render import render_report, render_summary
from pipeline.safety_filter import apply_safety_filter
from pipeline.validate import (
    check_prompt_injection,
    verify_allergens,
    verify_ingredients,
    verify_nutrition_numbers,
)

logger = logging.getLogger("label_reader.pipeline")


class ProgressUpdate:
    def __init__(self, message: str, step: int, total_steps: int = 6):
        self.message = message
        self.step = step
        self.total_steps = total_steps

    def __str__(self) -> str:
        return f"[{self.step}/{self.total_steps}] {self.message}"


def analyze(
    images: list[Image.Image],
    language: str = "English",
    question: str = "",
    backend: str | None = None,
    api_key: str | None = None,
) -> Iterator[ProgressUpdate | AnalysisResult]:
    """Orchestrates all 11 pipeline stages, streaming ProgressUpdates and finally yielding AnalysisResult."""
    start_time = time.time()
    active_backend = "gemini"
    active_model = settings.gemini_model

    if not images:
        yield AnalysisResult(
            refused=True,
            refusal_reason="Please upload at least one photo of the label.",
            backend_used=active_backend,
            model_used=active_model,
            seconds_taken=0.0,
        )
        return

    warnings: list[str] = []

    # Step 1: Preprocess images
    yield ProgressUpdate("Cleaning image...", step=1, total_steps=6)
    image_bytes_list, prep_warnings = preprocess_images(images, backend=active_backend)
    warnings.extend(prep_warnings)

    # Step 2: Extract label text via model pass 1
    yield ProgressUpdate("Reading label...", step=2, total_steps=6)
    try:
        extract_result: ExtractResult = extract_label_data(
            image_bytes_list,
            backend=active_backend,
            api_key=api_key,
        )
    except Exception as exc:
        logger.error("Extract failed: %s", exc)
        yield AnalysisResult(
            refused=True,
            refusal_reason="Could not read this label. Retake closer, in better light.",
            warnings=warnings,
            backend_used=active_backend,
            model_used=active_model,
            seconds_taken=time.time() - start_time,
        )
        return

    # Step 3: Guards (Food-only check, Medicine refusal & Supplement check)
    is_non_food, non_food_reason = check_food_label(extract_result, language=language)
    if is_non_food:
        yield AnalysisResult(
            refused=True,
            refusal_reason=non_food_reason,
            warnings=warnings,
            extract=extract_result,
            backend_used=active_backend,
            model_used=active_model,
            seconds_taken=time.time() - start_time,
        )
        return

    is_med, med_reason = check_medicine(extract_result, language=language)
    if is_med:
        yield AnalysisResult(
            refused=True,
            refusal_reason=med_reason,
            warnings=warnings,
            extract=extract_result,
            backend_used=active_backend,
            model_used=active_model,
            seconds_taken=time.time() - start_time,
        )
        return

    supp_warning = check_supplement(extract_result)
    if supp_warning:
        warnings.append(supp_warning)

    # Check unreadable label condition (blur-tolerant: proceed if any packaging text was deciphered)
    has_ingredients = bool(extract_result.ingredients)
    has_nutrition = any(v is not None for v in extract_result.nutrition.values.model_dump().values())
    has_product_info = bool(extract_result.product_name or extract_result.brand or (len(extract_result.raw_transcription.strip()) >= 20))

    if not has_ingredients and not has_nutrition and not has_product_info:
        yield AnalysisResult(
            refused=True,
            refusal_reason="Could not read this label. Retake the photo closer, in better light.",
            warnings=warnings,
            extract=extract_result,
            backend_used=active_backend,
            model_used=active_model,
            seconds_taken=time.time() - start_time,
        )
        return

    if not has_ingredients and not has_nutrition:
        warnings.append("⚠️ Blurry / partial packaging: Ingredients table was partially obscured by camera blur. Showing analysis for all recognized packaging details.")

    # Step 4: Validation (Prompt-injection, ingredients, allergens, numbers)
    yield ProgressUpdate("Checking ingredients...", step=3, total_steps=6)
    inj_warning = check_prompt_injection(extract_result.raw_transcription)
    if inj_warning:
        warnings.append(inj_warning)

    verified_ings, ing_warnings = verify_ingredients(
        extract_result.ingredients,
        extract_result.raw_transcription,
    )
    warnings.extend(ing_warnings)

    verified_allgs, allg_warnings = verify_allergens(
        extract_result.allergen_statement,
        extract_result.raw_transcription,
    )
    warnings.extend(allg_warnings)

    verified_nut, nut_num_warnings = verify_nutrition_numbers(
        extract_result.nutrition,
        extract_result.raw_transcription,
    )
    warnings.extend(nut_num_warnings)
    extract_result.nutrition = verified_nut

    # Step 5: Pure Python computations (Expiry & Nutrition flags)
    expiry_result = evaluate_expiry(extract_result.date_strings, today=date.today())
    nut_flags, nut_notes = evaluate_nutrition(verified_nut, claims=extract_result.claims)
    warnings.extend(nut_notes)

    # Step 6: Concurrent ratings, explanation, and Q&A passes (ThreadPoolExecutor)
    yield ProgressUpdate("Analyzing ingredients & generating explanation...", step=4, total_steps=6)

    ratings_list: list = []
    summary_result = None
    qa_result = None

    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        future_ratings = executor.submit(
            rate_ingredients,
            verified_ings,
            backend=active_backend,
            api_key=api_key,
        )
        future_summary = executor.submit(
            generate_explanation,
            extract=extract_result,
            verified_ingredients=verified_ings,
            verified_allergens=verified_allgs,
            nutrition_flags=nut_flags,
            expiry=expiry_result,
            language=language,
            backend=active_backend,
            api_key=api_key,
        )
        future_qa = None
        if question.strip():
            future_qa = executor.submit(
                answer_question,
                question=question,
                extract=extract_result,
                verified_ingredients=verified_ings,
                language=language,
                backend=active_backend,
                api_key=api_key,
            )

        # Collect ratings
        try:
            ratings_list = future_ratings.result()
        except Exception as exc:
            logger.warning("Rating pass encountered an error: %s", exc)
            ratings_list = []
            warnings.append("Ingredient ratings could not be fully generated.")

        # Collect explanation
        try:
            summary_result = future_summary.result()
        except Exception as exc:
            logger.warning("Explanation generation failed: %s", exc)
            warnings.append("Explanation could not be generated. Showing ingredient and nutrition data only.")

        # Collect Q&A if requested
        if future_qa:
            try:
                qa_result = future_qa.result()
            except Exception as exc:
                logger.warning("QA pass failed: %s", exc)
                warnings.append("Could not generate answer for the question.")

    # Step 7: Safety Filter
    yield ProgressUpdate("Finalizing report...", step=6, total_steps=6)
    filtered_summary, filtered_qa, filtered_ratings, safety_warnings = apply_safety_filter(
        summary=summary_result,
        qa=qa_result,
        ratings=ratings_list,
    )
    warnings.extend(safety_warnings)

    seconds_taken = time.time() - start_time
    yield ProgressUpdate(f"Done in {seconds_taken:.1f} s", step=6, total_steps=6)

    final_result = AnalysisResult(
        refused=False,
        warnings=warnings,
        extract=extract_result,
        verified_ingredients=verified_ings,
        verified_allergens=verified_allgs,
        ratings=filtered_ratings,
        nutrition_flags=nut_flags,
        expiry=expiry_result,
        summary=filtered_summary,
        qa=filtered_qa,
        language=language,  # type: ignore
        backend_used=active_backend,
        model_used=active_model,
        seconds_taken=seconds_taken,
    )

    yield final_result


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m pipeline.run <path/to/img.jpg> [language] [question]", flush=True)
        sys.exit(1)

    img_path = sys.argv[1]
    lang = sys.argv[2] if len(sys.argv) > 2 else "English"
    q = sys.argv[3] if len(sys.argv) > 3 else ""

    print(f"Loading image from {img_path}...", flush=True)
    pil_img = Image.open(img_path)

    for item in analyze(images=[pil_img], language=lang, question=q):
        if isinstance(item, ProgressUpdate):
            print(f"> {item.message}", flush=True)
        elif isinstance(item, AnalysisResult):
            print("\n" + "=" * 60, flush=True)
            print(render_summary(item), flush=True)
            print("=" * 60, flush=True)
            report_path = render_report(item)
            print(f"\nReport written to: {report_path}", flush=True)
