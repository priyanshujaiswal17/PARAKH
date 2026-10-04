"""Explanation pass: generates grounded summary in English or Hinglish from verified data."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any
from pydantic import ValidationError

from config import BASE_DIR
from llm import generate
from pipeline.models import (
    ExpiryResult,
    ExtractResult,
    NutritionFlag,
    Summary,
    VerifiedItem,
)

logger = logging.getLogger("label_reader.explain")

PROMPT_EN_PATH = BASE_DIR / "prompts" / "explain_en.txt"
PROMPT_HINGLISH_PATH = BASE_DIR / "prompts" / "explain_hinglish.txt"


def _prepare_verified_payload(
    extract: ExtractResult,
    verified_ingredients: list[VerifiedItem],
    verified_allergens: list[VerifiedItem],
    nutrition_flags: list[NutritionFlag],
    expiry: ExpiryResult | None,
) -> str:
    """Prepares clean JSON containing only grounded and verified facts for explanation."""
    payload: dict[str, Any] = {
        "product_name": extract.product_name,
        "brand": extract.brand,
        "veg_mark": extract.veg_mark,
        "is_supplement": extract.is_supplement,
        "claims": extract.claims,
        "verified_ingredients": [v.text for v in verified_ingredients],
        "verified_allergens": [v.text for v in verified_allergens],
        "nutrition_flags": [
            {"nutrient": f.nutrient, "level": f.level, "value": f.value, "unit": f.unit}
            for f in nutrition_flags
        ],
        "nutrition_values": {
            k: v for k, v in extract.nutrition.values.model_dump().items() if v is not None
        },
        "nutrition_basis": extract.nutrition.basis,
    }
    if expiry:
        payload["expiry_status"] = expiry.status
        payload["expiry_explanation"] = expiry.explanation

    return json.dumps(payload, indent=2, ensure_ascii=False)


def generate_explanation(
    extract: ExtractResult,
    verified_ingredients: list[VerifiedItem],
    verified_allergens: list[VerifiedItem],
    nutrition_flags: list[NutritionFlag],
    expiry: ExpiryResult | None,
    language: str = "English",
    backend: str | None = None,
    api_key: str | None = None,
) -> Summary:
    """Pass 2: generates structured Summary from verified data only."""
    prompt_file = PROMPT_HINGLISH_PATH if language == "Hinglish" else PROMPT_EN_PATH
    if prompt_file.exists():
        with open(prompt_file, "r", encoding="utf-8") as f:
            template = f.read()
    else:
        template = "Explain this packaged food label in {language}. Return ONLY JSON.\n<label_data>\n{label_data_json}\n</label_data>"

    label_json_str = _prepare_verified_payload(
        extract=extract,
        verified_ingredients=verified_ingredients,
        verified_allergens=verified_allergens,
        nutrition_flags=nutrition_flags,
        expiry=expiry,
    )

    prompt = template.replace("{label_data_json}", label_json_str).replace("{language}", language)
    schema = Summary.model_json_schema()

    try:
        raw_dict = generate(
            images=[],
            prompt=prompt,
            schema=schema,
            backend=backend,
            api_key=api_key,
            temperature=0.2,
            max_tokens=1500,
        )
        if isinstance(raw_dict, dict):
            summary = Summary.model_validate(raw_dict)
            # Enforce limits in code as well
            summary.what_it_is = " ".join(summary.what_it_is.split()[:25])
            summary.good_things = [" ".join(item.split()[:20]) for item in summary.good_things[:4]]
            summary.watch_out = [" ".join(item.split()[:20]) for item in summary.watch_out[:4]]
            summary.suits = [" ".join(item.split()[:20]) for item in summary.suits[:4]]
            summary.avoid_or_ask_doctor = [" ".join(item.split()[:20]) for item in summary.avoid_or_ask_doctor[:4]]
            summary.overall_note = " ".join(summary.overall_note.split()[:30])
            return summary
    except Exception as exc:
        logger.warning("Explanation generation failed: %s", exc)

    # Fallback minimal summary if model call fails
    return Summary(
        what_it_is=extract.product_name or "Packaged food product",
        good_things=[],
        watch_out=[],
        suits=[],
        avoid_or_ask_doctor=[],
        overall_note="Check the ingredient table and physical pack for details.",
    )
