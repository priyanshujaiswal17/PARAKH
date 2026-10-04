"""Nutrition evaluation and flag calculation based on UK FSA traffic-light thresholds."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from config import BASE_DIR
from pipeline.models import Nutrition, NutritionFlag

# Formula: Salt (g) = Sodium (mg) * 2.5 / 1000
# Sodium to salt conversion factor: sodium chloride is approx 40% sodium and 60% chloride
SODIUM_MG_TO_SALT_G = 2.5 / 1000.0

DATA_PATH = BASE_DIR / "data" / "thresholds.json"


def _load_thresholds() -> dict[str, Any]:
    if not DATA_PATH.exists():
        # Fallback inline thresholds if file is not found
        return {
            "per_100g": {
                "total_fat": {"low": 3.0, "high": 17.5, "unit": "g"},
                "saturated_fat": {"low": 1.5, "high": 5.0, "unit": "g"},
                "total_sugar": {"low": 5.0, "high": 22.5, "unit": "g"},
                "salt": {"low": 0.3, "high": 1.5, "unit": "g"},
            },
            "per_100ml": {
                "total_fat": {"low": 1.5, "high": 8.75, "unit": "g"},
                "saturated_fat": {"low": 0.75, "high": 2.5, "unit": "g"},
                "total_sugar": {"low": 2.5, "high": 11.25, "unit": "g"},
                "salt": {"low": 0.3, "high": 0.75, "unit": "g"},
            },
        }
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def calculate_salt_g(sodium_mg: float | None) -> float | None:
    """Converts sodium in mg to grams of salt."""
    if sodium_mg is None:
        return None
    return round(sodium_mg * SODIUM_MG_TO_SALT_G, 3)


def flags(nutrition: Nutrition, claims: list[str] | None = None) -> list[NutritionFlag]:
    """Computes traffic light flags for total fat, saturated fat, total sugar, and salt.
    
    Only computes flags if basis is 'per_100g' or 'per_100ml'.
    """
    flag_list, _ = evaluate_nutrition(nutrition, claims)
    return flag_list


def evaluate_nutrition(
    nutrition: Nutrition,
    claims: list[str] | None = None,
) -> tuple[list[NutritionFlag], list[str]]:
    """Evaluates nutrition values, generating flags and consumer catch notes."""
    result_flags: list[NutritionFlag] = []
    notes: list[str] = []

    basis = nutrition.basis
    values = nutrition.values

    # Notes on trans fat and added sugar
    if values.trans_fat_g is not None and values.trans_fat_g > 0:
        notes.append("Contains trans fat according to the label.")

    if values.added_sugar_g is not None and values.added_sugar_g > 0:
        notes.append("Added sugar present.")

    # Claim cross-check
    if claims and values.total_sugar_g is not None:
        sugar_val = values.total_sugar_g
        lower_claims = [c.lower() for c in claims]
        has_no_sugar_claim = any(
            "no added sugar" in c or "sugar free" in c or "zero sugar" in c
            for c in lower_claims
        )
        if has_no_sugar_claim and sugar_val > 5.0 and basis in ("per_100g", "per_100ml"):
            notes.append(
                f"Claim says no/low sugar, but the table shows {sugar_val:g} g sugar per {basis.replace('per_', '')}. Check the pack."
            )

    # Flags only calculated for per_100g or per_100ml
    if basis not in ("per_100g", "per_100ml"):
        notes.append("Flags need per-100g values; not shown.")
        return result_flags, notes

    thresholds = _load_thresholds()
    table = thresholds.get(basis, {})

    salt_val = calculate_salt_g(values.sodium_mg)

    nutrients_to_check: list[tuple[str, str, float | None, str]] = [
        ("total_fat", "total_fat", values.total_fat_g, "g"),
        ("saturated_fat", "saturated_fat", values.saturated_fat_g, "g"),
        ("total_sugar", "sugar", values.total_sugar_g, "g"),
        ("salt", "salt", salt_val, "g"),
    ]

    for key, output_name, val, default_unit in nutrients_to_check:
        if val is None:
            continue
        limits = table.get(key)
        if not limits:
            continue

        low_cut = limits["low"]
        high_cut = limits["high"]
        unit = limits.get("unit", default_unit)

        if val <= low_cut:
            level = "low"
            note = f"≤ {low_cut:g} {unit} is low"
        elif val > high_cut:
            level = "high"
            note = f"> {high_cut:g} {unit} is high"
        else:
            level = "medium"
            note = f"> {low_cut:g} to ≤ {high_cut:g} {unit} is medium"

        result_flags.append(
            NutritionFlag(
                nutrient=output_name,
                level=level,
                value=float(val),
                unit=unit,
                threshold_note=note,
            )
        )

    return result_flags, notes
