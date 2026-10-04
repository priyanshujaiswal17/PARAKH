"""Ingredient ratings engine: curated table lookup with batched model fallback."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any
from rapidfuzz import fuzz

from config import BASE_DIR
from pipeline.models import IngredientRating, VerifiedItem

logger = logging.getLogger("label_reader.ratings")

DATA_PATH = BASE_DIR / "data" / "additives.json"
FALLBACK_PROMPT_PATH = BASE_DIR / "prompts" / "ratings_fallback.txt"

# Regex for INS / E numbers per SPEC 12.2
INS_REGEX = re.compile(
    r"(?:INS|E)\s*-?\s*(\d{3,4}[a-z]?)(?:\s*\(\s*([ivx]+)\s*\))?",
    re.IGNORECASE,
)


def _load_additives() -> list[dict[str, Any]]:
    if not DATA_PATH.exists():
        return []
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def normalize_ingredient_name(name: str) -> str:
    """Normalises ingredient: lowercases, strips percentages and brackets, collapses spaces."""
    cleaned = name.lower()
    # Remove percentage numbers e.g. 60%, 8.5%
    cleaned = re.sub(r"\d+(\.\d+)?%", "", cleaned)
    # Remove bracket contents or brackets themselves
    cleaned = re.sub(r"[()\[\]{}]", " ", cleaned)
    # Remove common filler prefixes
    cleaned = re.sub(r"\b(contains|edible|nature-identical|artificial|flavouring|substances|agents?)\b", " ", cleaned)
    # Collapse spaces
    return " ".join(cleaned.split())


def extract_ins_number(text: str) -> str | None:
    """Extracts normalized INS number from ingredient text e.g. 'INS 100(i)' -> '100i'."""
    match = INS_REGEX.search(text)
    if not match:
        return None
    num = match.group(1).lower()
    subpart = match.group(2)
    if subpart:
        return f"{num}{subpart.lower()}"
    return num


def lookup_in_table(raw_name: str, additives: list[dict[str, Any]] | None = None) -> IngredientRating | None:
    """Looks up ingredient in the curated table by INS number, exact name, or fuzzy match."""
    table = additives if additives is not None else _load_additives()
    if not table:
        return None

    # 1. Try INS match
    ins_no = extract_ins_number(raw_name)
    if ins_no:
        for entry in table:
            entry_ins = str(entry.get("ins", "")).lower()
            if entry_ins == ins_no or entry_ins.replace("(", "").replace(")", "") == ins_no:
                return IngredientRating(
                    name=raw_name,
                    verified=True,
                    level=entry["level"],
                    reason=entry["reason"],
                    source="table",
                    ins_number=ins_no,
                )

    # 2. Normalized name lookup
    norm_name = normalize_ingredient_name(raw_name)
    if not norm_name:
        return None

    # Exact match across names/aliases
    for entry in table:
        for alias in entry.get("names", []):
            if norm_name == alias.lower():
                return IngredientRating(
                    name=raw_name,
                    verified=True,
                    level=entry["level"],
                    reason=entry["reason"],
                    source="table",
                    ins_number=entry.get("ins"),
                )

    # 3. Fuzzy match: rapidfuzz.fuzz.WRatio >= 90
    best_entry = None
    best_score = 0.0

    for entry in table:
        for alias in entry.get("names", []):
            score = float(fuzz.WRatio(norm_name, alias.lower()))
            if score >= 90.0 and score > best_score:
                best_score = score
                best_entry = entry

    if best_entry:
        return IngredientRating(
            name=raw_name,
            verified=True,
            level=best_entry["level"],
            reason=best_entry["reason"],
            source="table",
            ins_number=best_entry.get("ins"),
        )

    return None


def rate_ingredients(
    items: list[VerifiedItem],
    backend: str | None = None,
    api_key: str | None = None,
) -> list[IngredientRating]:
    """Rates ingredients: curated table first, then batched model fallback for remaining items."""
    table = _load_additives()
    ratings: list[IngredientRating] = []
    unrated_items: list[tuple[int, VerifiedItem]] = []

    for idx, item in enumerate(items):
        is_verified = (item.status == "verified")
        # Remove [unverified] marker if present for lookup
        clean_text = item.text.replace("[unverified]", "").strip()

        table_res = lookup_in_table(clean_text, table)
        if table_res:
            table_res.verified = is_verified
            if not is_verified and "[unverified]" not in table_res.name:
                table_res.name = f"{table_res.name} [unverified]"
            ratings.append(table_res)
        else:
            # Placeholder to fill after model fallback
            unrated_items.append((idx, item))
            ratings.append(
                IngredientRating(
                    name=item.text,
                    verified=is_verified,
                    level="not_rated",
                    reason="Not rated in database.",
                    source="none",
                )
            )

    if not unrated_items:
        return ratings

    # Cap at 25 items for model fallback
    items_to_model = unrated_items[:25]
    ingredient_names = [item.text.replace("[unverified]", "").strip() for _, item in items_to_model]

    try:
        from llm import generate

        prompt_template = ""
        if FALLBACK_PROMPT_PATH.exists():
            with open(FALLBACK_PROMPT_PATH, "r", encoding="utf-8") as pf:
                prompt_template = pf.read()
        else:
            prompt_template = (
                "Rate each food ingredient using general nutrition knowledge. Levels: good, neutral, watch, limit.\n"
                "Return ONLY JSON: {{\"ratings\":[{{\"name\":\"...\",\"level\":\"...\",\"reason\":\"...\"}}]}}\n"
                "Ingredients:\n{ingredient_list}"
            )

        formatted_list = "\n".join(f"- {name}" for name in ingredient_names)
        prompt = prompt_template.replace("{ingredient_list}", formatted_list)

        schema = {
            "type": "object",
            "properties": {
                "ratings": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "level": {"type": "string", "enum": ["good", "neutral", "watch", "limit"]},
                            "reason": {"type": "string"},
                        },
                        "required": ["name", "level", "reason"],
                    },
                }
            },
            "required": ["ratings"],
        }

        resp = generate(
            images=[],
            prompt=prompt,
            schema=schema,
            backend=backend,
            api_key=api_key,
            temperature=0.0,
            max_tokens=1500,
        )

        if isinstance(resp, list):
            ratings_items = resp
        elif isinstance(resp, dict):
            # Handle {'ratings': [...]} or {'items': [...]} from jsonutil array wrap
            ratings_items = resp.get("ratings") or resp.get("items") or []
        else:
            ratings_items = []

        if isinstance(ratings_items, list) and ratings_items:
            model_ratings_map = {
                r.get("name", "").lower(): r
                for r in ratings_items
                if isinstance(r, dict) and "name" in r
            }
            for pos, (orig_idx, v_item) in enumerate(items_to_model):
                ing_name = ingredient_names[pos]
                clean_lookup = ing_name.lower()

                # Find match in model ratings
                matched_r = model_ratings_map.get(clean_lookup)
                if not matched_r:
                    # Fuzzy match against returned names
                    for k, val in model_ratings_map.items():
                        if fuzz.ratio(clean_lookup, k) >= 80:
                            matched_r = val
                            break

                if matched_r:
                    lvl = matched_r.get("level", "neutral")
                    if lvl not in ("good", "neutral", "watch", "limit"):
                        lvl = "neutral"
                    reason_words = matched_r.get("reason", "").split()
                    short_reason = " ".join(reason_words[:15]) if reason_words else "General food ingredient."
                    
                    is_ver = (v_item.status == "verified")
                    display_name = v_item.text

                    ratings[orig_idx] = IngredientRating(
                        name=display_name,
                        verified=is_ver,
                        level=lvl,
                        reason=short_reason,
                        source="general_knowledge",
                    )
    except Exception as exc:
        logger.warning("Ratings fallback model call failed: %s. Keeping default 'not_rated'.", exc)

    return ratings
