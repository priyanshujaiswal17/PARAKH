"""Tests for pipeline/ingredients.py."""

from pipeline.ingredients import split_top_level


def test_simple_split():
    text = "Sugar, Salt, Water"
    assert split_top_level(text) == ["Sugar", "Salt", "Water"]


def test_nested_parentheses():
    text = "Wheat flour (maida 60%, vitamins (B1, B2)), Sugar, Salt"
    assert split_top_level(text) == [
        "Wheat flour (maida 60%, vitamins (B1, B2))",
        "Sugar",
        "Salt",
    ]


def test_square_and_curly_brackets():
    text = "Ingredient A [sub 1, sub 2], Ingredient B {sub 3, sub 4}, Ingredient C"
    assert split_top_level(text) == [
        "Ingredient A [sub 1, sub 2]",
        "Ingredient B {sub 3, sub 4}",
        "Ingredient C",
    ]


def test_full_width_commas():
    text = "Refined wheat flour， Palm oil， Edible salt"
    assert split_top_level(text) == [
        "Refined wheat flour",
        "Palm oil",
        "Edible salt",
    ]


def test_semicolons():
    text = "Wheat flour; Sugar; Cocoa solids (8%); Salt"
    assert split_top_level(text) == [
        "Wheat flour",
        "Sugar",
        "Cocoa solids (8%)",
        "Salt",
    ]


def test_full_width_semicolons():
    text = "Flour； Sugar； Salt"
    assert split_top_level(text) == ["Flour", "Sugar", "Salt"]


def test_empty_and_whitespace():
    assert split_top_level("") == []
    assert split_top_level("   ") == []
