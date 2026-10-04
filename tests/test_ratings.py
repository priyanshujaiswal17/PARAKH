"""Tests for pipeline/ratings.py table lookup (model fallback stubbed/mocked)."""

from pipeline.models import VerifiedItem
from pipeline.ratings import extract_ins_number, lookup_in_table, normalize_ingredient_name, rate_ingredients


def test_extract_ins():
    assert extract_ins_number("INS 102") == "102"
    assert extract_ins_number("E100(i)") == "100i"
    assert extract_ins_number("INS-211") == "211"
    assert extract_ins_number("No INS here") is None


def test_normalize_ingredient():
    assert normalize_ingredient_name("Wheat flour (maida 60%)") == "wheat flour maida"
    assert normalize_ingredient_name("Edible Vegetable Oil (Palmolein)") == "palm oil" or "palmolein" in normalize_ingredient_name("Edible Vegetable Oil (Palmolein)")


def test_lookup_by_ins():
    # INS 102 is Tartrazine -> limit
    r1 = lookup_in_table("Colour (INS 102)")
    assert r1 is not None
    assert r1.level == "limit"
    assert r1.source == "table"
    assert "Tartrazine" in r1.reason or "Synthetic colour" in r1.reason

    # INS 330 is Citric acid -> good
    r2 = lookup_in_table("Acidity Regulator (INS 330)")
    assert r2 is not None
    assert r2.level == "good"
    assert r2.source == "table"


def test_lookup_by_name():
    # Whole wheat flour -> good
    r1 = lookup_in_table("Whole wheat flour")
    assert r1 is not None
    assert r1.level == "good"
    assert r1.source == "table"

    # Hydrogenated vegetable fat -> limit
    r2 = lookup_in_table("Hydrogenated vegetable fat")
    assert r2 is not None
    assert r2.level == "limit"
    assert r2.source == "table"


def test_lookup_fuzzy_alias():
    # Soya lecithin vs Soy lecithin
    r = lookup_in_table("Soya lecithin")
    assert r is not None
    assert r.level == "good"
    assert r.source == "table"


def test_rate_ingredients_unverified_flag():
    # Unverified items should retain unverified status in ratings
    items = [
        VerifiedItem(text="Whole wheat flour", status="verified", match_score=100.0),
        VerifiedItem(text="Sugar [unverified]", status="unverified", match_score=75.0),
    ]
    ratings = rate_ingredients(items)
    assert len(ratings) == 2
    assert ratings[0].verified is True
    assert ratings[1].verified is False
    assert "[unverified]" in ratings[1].name
