"""Extraction pass: runs vision model on label images to produce ExtractResult."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any
from pydantic import ValidationError

from config import BASE_DIR
from llm import ModelOutputError, generate
from pipeline.ingredients import split_top_level
from pipeline.models import ExtractResult

logger = logging.getLogger("label_reader.extract")

EXTRACT_PROMPT_PATH = BASE_DIR / "prompts" / "extract.txt"


def _load_extract_prompt() -> str:
    if EXTRACT_PROMPT_PATH.exists():
        with open(EXTRACT_PROMPT_PATH, "r", encoding="utf-8") as f:
            return f.read()
    return (
        "You are a careful label transcriber for packaged-food photos. Your only job is to read what is printed.\n"
        "Return ONLY JSON matching the provided schema."
    )


def recover_ingredients_from_transcription(raw_text: str) -> list[str]:
    """Recovers ingredients list if the vision model failed to format them on a blurry image."""
    if not raw_text:
        return []
    pattern = r'(?:ingredients|ingredients\s*used|contents|samagri)\s*[:\-–]\s*([^\.\n\r]+)'
    match = re.search(pattern, raw_text, re.IGNORECASE)
    if match:
        ing_block = match.group(1).strip()
        items = [i.strip() for i in ing_block.split(',') if i.strip() and len(i.strip()) > 1]
        if items:
            return items
    return []


def extract_label_data(
    images_bytes: list[bytes],
    backend: str | None = None,
    api_key: str | None = None,
) -> ExtractResult:
    """Performs pass 1 extraction on processed label image bytes using Gemma 4."""
    prompt = _load_extract_prompt()
    schema = ExtractResult.model_json_schema()

    def _call_and_validate(p: str) -> ExtractResult:
        raw_dict = generate(
            images=images_bytes,
            prompt=p,
            schema=schema,
            backend=backend,
            api_key=api_key,
            temperature=0.0,
            max_tokens=3000,
        )
        if not isinstance(raw_dict, dict):
            raise ModelOutputError(
                "Model did not return a dictionary for ExtractResult",
                user_message="The model gave an unreadable answer. Please try again.",
            )
        return ExtractResult.model_validate(raw_dict)

    # Attempt 1
    try:
        result = _call_and_validate(prompt)
    except (ValidationError, ModelOutputError) as err:
        logger.warning("First extraction attempt failed validation: %s. Retrying once...", err)
        retry_prompt = (
            f"{prompt}\n\nIMPORTANT: Strict JSON according to schema required. Ensure all fields are present."
        )
        try:
            result = _call_and_validate(retry_prompt)
        except Exception as retry_err:
            logger.error("Second extraction attempt also failed: %s", retry_err)
            raise ModelOutputError(
                f"Model failed to return valid ExtractResult after retry: {retry_err}",
                user_message="Could not read this label. Retake closer, in better light.",
            ) from retry_err

    # Post-process ingredients: if the model returned 1 long comma-separated string, split it
    if len(result.ingredients) == 1 and ("," in result.ingredients[0] or "，" in result.ingredients[0]):
        result.ingredients = split_top_level(result.ingredients[0])

    # If ingredients is still empty, attempt recovery from raw transcription
    if not result.ingredients and result.raw_transcription:
        recovered = recover_ingredients_from_transcription(result.raw_transcription)
        if recovered:
            logger.info("Recovered %d ingredients from raw transcription on blurry packaging: %s", len(recovered), recovered)
            result.ingredients = recovered

    return result
