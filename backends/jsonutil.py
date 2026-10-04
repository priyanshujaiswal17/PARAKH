"""Tolerant JSON parser shared by backends."""

from __future__ import annotations

import json
import re
from typing import Any


def parse_json(text: str) -> dict[str, Any]:
    """Tolerantly parses JSON from model output text.

    Strips markdown code fences, isolates outer braces or brackets,
    removes trailing commas if needed. If the result is a list, wraps it
    as {"items": [...]} so callers always get a dict.
    """
    if not text or not isinstance(text, str):
        raise ValueError("Empty or non-string input provided to parse_json")

    cleaned = text.strip()

    # Remove markdown code fences ```json ... ``` or ``` ... ```
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        cleaned = cleaned.strip()

    # --- Try to isolate a JSON object first ---
    first_brace = cleaned.find("{")
    last_brace = cleaned.rfind("}")
    first_bracket = cleaned.find("[")

    # Determine if there's a leading array before any object
    has_object = first_brace != -1 and last_brace != -1 and last_brace >= first_brace
    has_array = first_bracket != -1

    if has_object:
        json_str = cleaned[first_brace: last_brace + 1]
        parsed = _try_parse(json_str)
        if parsed is not None:
            if isinstance(parsed, dict):
                return parsed
            if isinstance(parsed, list):
                return {"items": parsed}

    if has_array:
        last_bracket = cleaned.rfind("]")
        if last_bracket > first_bracket:
            json_str = cleaned[first_bracket: last_bracket + 1]
            parsed = _try_parse(json_str)
            if parsed is not None:
                if isinstance(parsed, list):
                    return {"items": parsed}
                if isinstance(parsed, dict):
                    return parsed

    raise ValueError(f"No JSON object or array found in text: {text[:300]}")


def _try_parse(json_str: str) -> Any:
    """Attempt 1: standard parse. Attempt 2: strip trailing commas."""
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        pass
    # Remove trailing commas before } or ]
    fixed = re.sub(r",\s*([}\]])", r"\1", json_str)
    try:
        return json.loads(fixed)
    except json.JSONDecodeError:
        return None
