"""Validation logic enforcing Honesty Rules H1, H4, and prompt-injection defense."""

from __future__ import annotations

import re
import unicodedata
from rapidfuzz import fuzz

from pipeline.models import ExtractResult, Nutrition, NutritionValues, VerifiedItem

INJECTION_PHRASES = [
    "ignore previous instructions",
    "ignore all instructions",
    "system prompt",
    "you are now",
    "disregard previous",
    "forget all prior",
]


def normalize_text(text: str) -> str:
    """Normalizes text by lowercasing, NFKD decomposing, removing accents, and collapsing spaces."""
    if not text:
        return ""
    # NFKD normalization to remove accents
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    lower = stripped.lower()
    # Replace punctuation with space
    punct_removed = re.sub(r"[^\w\s]", " ", lower)
    # Collapse multiple whitespaces
    return " ".join(punct_removed.split())


def check_prompt_injection(raw_transcription: str) -> str | None:
    """Detects suspicious prompt injection attempts printed in label text."""
    lower = raw_transcription.lower()
    for phrase in INJECTION_PHRASES:
        if phrase in lower:
            return "The label contains text that looks like an instruction. It was ignored."
    return None


def verify_text_item(item: str, transcription: str, norm_transcription: str) -> tuple[VerifiedItem | None, bool]:
    """Verifies a single ingredient or allergen item against the raw transcription.
    
    Returns (VerifiedItem or None if dropped, was_dropped_bool).
    """
    clean_item = item.strip()
    if not clean_item:
        return None, False

    # Items containing [unclear] are preserved
    if "[unclear]" in clean_item.lower():
        return VerifiedItem(text=clean_item, status="verified", match_score=100.0), False

    norm_item = normalize_text(clean_item)
    if not norm_item:
        return None, True

    # 1. Exact substring check in normalized transcription
    if norm_item in norm_transcription:
        return VerifiedItem(text=clean_item, status="verified", match_score=100.0), False

    # 2. Fuzzy partial ratio
    score = float(fuzz.partial_ratio(norm_item, norm_transcription))

    if score >= 85.0:
        return VerifiedItem(text=clean_item, status="verified", match_score=score), False
    elif 70.0 <= score < 85.0:
        return VerifiedItem(text=f"{clean_item} [unverified]", status="unverified", match_score=score), False
    else:
        # Dropped
        return None, True


def verify_ingredients(
    ingredients: list[str],
    raw_transcription: str,
) -> tuple[list[VerifiedItem], list[str]]:
    """Verifies each ingredient against raw_transcription.
    
    Drops below 70, flags unverified for 70-84, verifies >= 85.
    """
    verified_items: list[VerifiedItem] = []
    warnings: list[str] = []
    dropped_count = 0
    norm_trans = normalize_text(raw_transcription)

    for ing in ingredients:
        res, dropped = verify_text_item(ing, raw_transcription, norm_trans)
        if dropped:
            dropped_count += 1
        elif res:
            verified_items.append(res)

    if dropped_count > 0:
        warnings.append(
            f"{dropped_count} items from the model were not found on the label and were removed."
        )

    return verified_items, warnings


def verify_allergens(
    allergen_statements: list[str],
    raw_transcription: str,
) -> tuple[list[VerifiedItem], list[str]]:
    """Verifies allergen statements against raw_transcription."""
    verified_items: list[VerifiedItem] = []
    warnings: list[str] = []
    dropped_count = 0
    norm_trans = normalize_text(raw_transcription)

    for item in allergen_statements:
        res, dropped = verify_text_item(item, raw_transcription, norm_trans)
        if dropped:
            dropped_count += 1
        elif res:
            verified_items.append(res)

    if dropped_count > 0:
        warnings.append(
            f"{dropped_count} allergen statements from the model were not found on the label and were removed."
        )

    return verified_items, warnings


def verify_nutrition_numbers(
    nutrition: Nutrition,
    raw_transcription: str,
) -> tuple[Nutrition, list[str]]:
    """Verifies that non-null numeric values in Nutrition appear in the transcription."""
    warnings: list[str] = []
    values_dict = nutrition.values.model_dump()
    modified_dict = {}
    had_unconfirmed = False

    # Extract all digit sequences, with dots and commas
    trans_digits = raw_transcription

    for key, val in values_dict.items():
        if val is None:
            modified_dict[key] = None
            continue

        # Format number: strip trailing .0 e.g. 5.0 -> '5', 5.5 -> '5.5'
        val_str = f"{val:g}" if isinstance(val, (int, float)) else str(val)
        comma_swap = val_str.replace(".", ",")

        # Check if val_str or comma_swap is present as a standalone or delimited token in transcription
        pattern_dot = rf"(?<!\d){re.escape(val_str)}(?!\d)"
        pattern_comma = rf"(?<!\d){re.escape(comma_swap)}(?!\d)"

        if re.search(pattern_dot, trans_digits) or re.search(pattern_comma, trans_digits):
            modified_dict[key] = val
        else:
            modified_dict[key] = None
            had_unconfirmed = True

    if had_unconfirmed:
        warnings.append(
            "Some nutrition numbers could not be confirmed on the label and were left out."
        )

    verified_nutrition = Nutrition(
        basis=nutrition.basis,
        serving_size_text=nutrition.serving_size_text,
        values=NutritionValues(**modified_dict),
    )
    return verified_nutrition, warnings
