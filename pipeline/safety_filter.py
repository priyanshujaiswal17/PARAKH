"""Safety filter enforcing Honesty Rule H3 by removing banned absolute-safety phrases."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from config import BASE_DIR
from pipeline.models import IngredientRating, QAAnswer, Summary

DATA_PATH = BASE_DIR / "data" / "banned_phrases.json"
FALLBACK_TEXT = "Please see the ingredient ratings and ask a doctor if you have a health condition."


def _load_banned_phrases() -> list[str]:
    if not DATA_PATH.exists():
        return [
            "completely safe", "100% safe", "totally safe", "absolutely safe",
            "perfectly safe", "guaranteed safe", "safe for everyone",
            "no side effects", "cures", "cure for", "treats", "prevents cancer",
            "prevents diabetes", "detox", "bilkul safe", "poori tarah safe",
            "100% safe hai", "sabke liye safe", "koi side effect nahi"
        ]
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    phrases = []
    if isinstance(data, dict):
        phrases.extend(data.get("english", []))
        phrases.extend(data.get("hinglish", []))
    elif isinstance(data, list):
        phrases.extend(data)
    return [p.strip().lower() for p in phrases if p.strip()]


def split_sentences(text: str) -> list[str]:
    """Splits text into sentences while preserving sentence structure."""
    if not text:
        return []
    # Split by period, exclamation, or question mark followed by space or newline
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p.strip() for p in parts if p.strip()]


def filter_text(text: str, banned_phrases: list[str] | None = None) -> tuple[str, int]:
    """Filters a text string by dropping sentences containing any banned phrase.
    
    Returns (cleaned_text, dropped_count).
    If all sentences are dropped from non-empty text, returns FALLBACK_TEXT.
    """
    if not text or not text.strip():
        return "", 0

    phrases = banned_phrases if banned_phrases is not None else _load_banned_phrases()
    sentences = split_sentences(text)
    kept: list[str] = []
    dropped_count = 0

    for s in sentences:
        s_lower = s.lower()
        contains_banned = False
        for phrase in phrases:
            # Word boundary check for short words like 'cures', 'treats', 'detox'
            pattern = rf"\b{re.escape(phrase)}\b"
            if re.search(pattern, s_lower):
                contains_banned = True
                break
        if contains_banned:
            dropped_count += 1
        else:
            kept.append(s)

    if not kept:
        return FALLBACK_TEXT, dropped_count

    return " ".join(kept), dropped_count


def filter_string_list(items: list[str], banned_phrases: list[str] | None = None) -> tuple[list[str], int]:
    """Filters a list of bullet points, dropping items with banned phrases."""
    kept: list[str] = []
    total_dropped = 0
    phrases = banned_phrases if banned_phrases is not None else _load_banned_phrases()

    for item in items:
        cleaned, dropped = filter_text(item, phrases)
        if dropped > 0 and cleaned == FALLBACK_TEXT:
            total_dropped += dropped
            # Drop entire bullet point rather than showing fallback in a list
            continue
        elif dropped > 0:
            total_dropped += dropped
            if cleaned:
                kept.append(cleaned)
        else:
            kept.append(item)

    return kept, total_dropped


def apply_safety_filter(
    summary: Summary | None,
    qa: QAAnswer | None,
    ratings: list[IngredientRating],
) -> tuple[Summary | None, QAAnswer | None, list[IngredientRating], list[str]]:
    """Applies the safety filter to all model-generated strings."""
    banned = _load_banned_phrases()
    total_removals = 0
    warnings: list[str] = []

    # 1. Summary
    new_summary = None
    if summary:
        what_it_is, d1 = filter_text(summary.what_it_is, banned)
        good_things, d2 = filter_string_list(summary.good_things, banned)
        watch_out, d3 = filter_string_list(summary.watch_out, banned)
        suits, d4 = filter_string_list(summary.suits, banned)
        avoid, d5 = filter_string_list(summary.avoid_or_ask_doctor, banned)
        overall_note, d6 = filter_text(summary.overall_note, banned)

        total_removals += (d1 + d2 + d3 + d4 + d5 + d6)
        new_summary = Summary(
            what_it_is=what_it_is,
            good_things=good_things,
            watch_out=watch_out,
            suits=suits,
            avoid_or_ask_doctor=avoid,
            overall_note=overall_note,
        )

    # 2. QA
    new_qa = None
    if qa:
        ans, d_qa = filter_text(qa.answer, banned)
        total_removals += d_qa
        new_qa = QAAnswer(
            question=qa.question,
            answer=ans,
            source=qa.source,
            evidence=qa.evidence,
            downgraded=qa.downgraded,
        )

    # 3. Ratings reasons
    new_ratings: list[IngredientRating] = []
    for r in ratings:
        cleaned_reason, d_r = filter_text(r.reason, banned)
        total_removals += d_r
        new_ratings.append(
            IngredientRating(
                name=r.name,
                verified=r.verified,
                level=r.level,
                reason=cleaned_reason,
                source=r.source,
                ins_number=r.ins_number,
            )
        )

    if total_removals > 0:
        warnings.append(
            f"{total_removals} unsafe-sounding claims were removed from the explanation."
        )

    return new_summary, new_qa, new_ratings, warnings
