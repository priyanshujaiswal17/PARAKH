"""Golden set evaluator for Label Reader pipeline."""

from __future__ import annotations

import argparse
import glob
import json
import os
import time
from pathlib import Path
from PIL import Image
from rapidfuzz import fuzz

from pipeline.models import AnalysisResult
from pipeline.run import analyze


def evaluate_sample(image_path: Path, expected_data: dict, backend: str) -> dict:
    start_t = time.time()
    img = Image.open(image_path)
    final_result: AnalysisResult | None = None

    for item in analyze(images=[img], backend=backend):
        if isinstance(item, AnalysisResult):
            final_result = item

    elapsed = time.time() - start_t

    if not final_result:
        return {
            "name": image_path.name,
            "error": "No result returned",
            "elapsed": elapsed,
        }

    # 1. Medicine refusal
    is_medicine_expected = expected_data.get("is_medicine", False)
    medicine_refused_actual = final_result.refused and (
        "medicine" in (final_result.refusal_reason or "").lower()
    )
    medicine_correct = (is_medicine_expected == medicine_refused_actual)

    if is_medicine_expected:
        return {
            "name": image_path.name,
            "is_medicine": True,
            "medicine_correct": medicine_correct,
            "elapsed": elapsed,
        }

    # 2. Ingredient fidelity & hallucinations
    expected_ings = [i.lower() for i in expected_data.get("ingredients", [])]
    actual_ings = [v.text.replace("[unverified]", "").strip().lower() for v in final_result.verified_ingredients]

    matched_count = 0
    hallucination_count = 0

    for act in actual_ings:
        # Check against expected
        found_in_expected = any(fuzz.partial_ratio(act, exp) >= 80 for exp in expected_ings)
        if found_in_expected:
            matched_count += 1
        else:
            # Check if this item actually exists in the raw transcription
            raw = final_result.extract.raw_transcription.lower() if final_result.extract else ""
            if fuzz.partial_ratio(act, raw) < 70:
                hallucination_count += 1

    fidelity = (matched_count / len(expected_ings)) if expected_ings else 1.0

    # 3. Expiry date accuracy
    exp_expected = expected_data.get("expiry_date")
    actual_date = final_result.expiry.expiry_date.isoformat() if (final_result.expiry and final_result.expiry.expiry_date) else None
    date_correct = (exp_expected == actual_date) if exp_expected else True

    return {
        "name": image_path.name,
        "is_medicine": False,
        "fidelity": fidelity,
        "hallucination_count": hallucination_count,
        "medicine_correct": medicine_correct,
        "date_correct": date_correct,
        "elapsed": elapsed,
    }


def run_eval(golden_dir: Path, backend: str) -> None:
    jpg_files = list(golden_dir.glob("*.jpg")) + list(golden_dir.glob("*.jpeg")) + list(golden_dir.glob("*.png"))
    if not jpg_files:
        print(f"No golden images found in {golden_dir}.")
        print("Add sample label photos (*.jpg) and matching (*.json) files to tests/golden/ to run evaluation.")
        return

    print(f"\n=======================================================")
    print(f"Running Golden Evaluation on Backend: {backend.upper()}")
    print(f"Found {len(jpg_files)} test samples in {golden_dir}")
    print(f"=======================================================\n")

    results = []
    total_time = 0.0

    for img_file in jpg_files:
        json_file = img_file.with_suffix(".json")
        if not json_file.exists():
            print(f"Skipping {img_file.name}: no matching {json_file.name} found.")
            continue

        with open(json_file, "r", encoding="utf-8") as f:
            expected = json.load(f)

        print(f"Evaluating {img_file.name}...")
        res = evaluate_sample(img_file, expected, backend)
        results.append(res)
        total_time += res.get("elapsed", 0.0)

    if not results:
        print("No paired golden samples found.")
        return

    # Aggregate metrics
    food_results = [r for r in results if not r.get("is_medicine", False)]
    med_results = [r for r in results if r.get("is_medicine", False)]

    avg_fidelity = (sum(r.get("fidelity", 0) for r in food_results) / len(food_results)) if food_results else 0.0
    total_hallucinations = sum(r.get("hallucination_count", 0) for r in food_results)
    med_recall = (sum(1 for r in med_results if r.get("medicine_correct")) / len(med_results)) if med_results else 1.0
    date_acc = (sum(1 for r in food_results if r.get("date_correct")) / len(food_results)) if food_results else 1.0
    avg_sec = total_time / len(results)

    print("\n" + "=" * 50)
    print("EVALUATION SUMMARY METRICS")
    print("=" * 50)
    print(f"Backend evaluated:             {backend}")
    print(f"Total samples evaluated:       {len(results)}")
    print(f"Ingredient fidelity:           {avg_fidelity * 100:.1f}%")
    print(f"Hallucinations after validate: {total_hallucinations} (Target: 0)")
    print(f"Medicine refusal recall:       {med_recall * 100:.1f}%")
    print(f"Expiry date accuracy:          {date_acc * 100:.1f}%")
    print(f"Average seconds per sample:    {avg_sec:.1f} s")
    print("=" * 50)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate Label Reader on golden sample set.")
    parser.add_argument("--backend", default="gemini", choices=["gemini"])
    parser.add_argument("--dir", default="tests/golden")
    args = parser.parse_args()

    golden_path = Path(__file__).parent / "golden" if args.dir == "tests/golden" else Path(args.dir)
    run_eval(golden_path, args.backend)
