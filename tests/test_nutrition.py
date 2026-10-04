"""Tests for pipeline/nutrition.py."""

from pipeline.models import Nutrition, NutritionValues
from pipeline.nutrition import calculate_salt_g, evaluate_nutrition, flags


def test_salt_conversion():
    # 400 mg sodium * 2.5 / 1000 = 1.0 g salt
    assert calculate_salt_g(400) == 1.0
    assert calculate_salt_g(0) == 0.0
    assert calculate_salt_g(None) is None


def test_per_serving_gives_no_flags():
    n = Nutrition(
        basis="per_serving",
        values=NutritionValues(total_sugar_g=15.0, total_fat_g=8.0),
    )
    res_flags, notes = evaluate_nutrition(n)
    assert len(res_flags) == 0
    assert any("Flags need per-100g values; not shown." in note for note in notes)


def test_unknown_basis_gives_no_flags():
    n = Nutrition(
        basis="unknown",
        values=NutritionValues(total_sugar_g=10.0),
    )
    res_flags, notes = evaluate_nutrition(n)
    assert len(res_flags) == 0


def test_per_100g_sugar_boundaries():
    # Total sugar thresholds: <=5 low, >5 to <=22.5 medium, >22.5 high
    # Boundary: 5.0 -> low
    n_low = Nutrition(basis="per_100g", values=NutritionValues(total_sugar_g=5.0))
    f_low = flags(n_low)
    assert len(f_low) == 1
    assert f_low[0].nutrient == "sugar"
    assert f_low[0].level == "low"

    # Boundary: 5.1 -> medium
    n_med = Nutrition(basis="per_100g", values=NutritionValues(total_sugar_g=5.1))
    f_med = flags(n_med)
    assert f_med[0].level == "medium"

    # Boundary: 22.5 -> medium
    n_med2 = Nutrition(basis="per_100g", values=NutritionValues(total_sugar_g=22.5))
    f_med2 = flags(n_med2)
    assert f_med2[0].level == "medium"

    # Boundary: 22.6 -> high
    n_high = Nutrition(basis="per_100g", values=NutritionValues(total_sugar_g=22.6))
    f_high = flags(n_high)
    assert f_high[0].level == "high"


def test_per_100g_fat_boundaries():
    # Total fat: <=3 low, >3 to <=17.5 medium, >17.5 high
    n1 = Nutrition(basis="per_100g", values=NutritionValues(total_fat_g=3.0))
    assert flags(n1)[0].level == "low"

    n2 = Nutrition(basis="per_100g", values=NutritionValues(total_fat_g=17.5))
    assert flags(n2)[0].level == "medium"

    n3 = Nutrition(basis="per_100g", values=NutritionValues(total_fat_g=17.6))
    assert flags(n3)[0].level == "high"


def test_per_100g_saturated_fat_boundaries():
    # Saturated fat: <=1.5 low, >1.5 to <=5.0 medium, >5.0 high
    n1 = Nutrition(basis="per_100g", values=NutritionValues(saturated_fat_g=1.5))
    assert flags(n1)[0].level == "low"

    n2 = Nutrition(basis="per_100g", values=NutritionValues(saturated_fat_g=5.0))
    assert flags(n2)[0].level == "medium"

    n3 = Nutrition(basis="per_100g", values=NutritionValues(saturated_fat_g=5.1))
    assert flags(n3)[0].level == "high"


def test_per_100ml_table_drinks():
    # Per 100ml: total fat <=1.5 low, >8.75 high
    # total sugar <=2.5 low, >11.25 high
    n_drink = Nutrition(
        basis="per_100ml",
        values=NutritionValues(
            total_fat_g=1.5,
            total_sugar_g=12.0,
            sodium_mg=200.0,  # 0.5g salt -> medium (>0.3 to <=0.75)
        ),
    )
    res_flags, _ = evaluate_nutrition(n_drink)
    flag_dict = {f.nutrient: f.level for f in res_flags}
    assert flag_dict["total_fat"] == "low"
    assert flag_dict["sugar"] == "high"
    assert flag_dict["salt"] == "medium"


def test_claim_mismatch_warning():
    n = Nutrition(
        basis="per_100g",
        values=NutritionValues(total_sugar_g=12.0),
    )
    claims = ["100% Natural", "No added sugar!"]
    _, notes = evaluate_nutrition(n, claims=claims)
    assert any("Claim says no/low sugar" in note for note in notes)


def test_trans_fat_and_added_sugar_notes():
    n = Nutrition(
        basis="per_100g",
        values=NutritionValues(trans_fat_g=0.5, added_sugar_g=4.0),
    )
    _, notes = evaluate_nutrition(n)
    assert any("Contains trans fat according to the label." in note for note in notes)
    assert any("Added sugar present." in note for note in notes)
