"""Tests for pipeline/safety_filter.py."""

from pipeline.models import QAAnswer, Summary
from pipeline.safety_filter import FALLBACK_TEXT, apply_safety_filter, filter_text


def test_banned_phrase_removed_in_context():
    text = "This biscuit contains whole wheat. It is 100% safe for consumption. Rich in dietary fiber."
    cleaned, dropped = filter_text(text)
    assert dropped == 1
    assert "100% safe" not in cleaned
    assert "This biscuit contains whole wheat." in cleaned
    assert "Rich in dietary fiber." in cleaned


def test_empty_fallback():
    text = "This product is completely safe. It cures diabetes."
    cleaned, dropped = filter_text(text)
    assert dropped == 2
    assert cleaned == FALLBACK_TEXT


def test_hinglish_banned_phrases():
    text = "Yeh biscuit bilkul safe hai. Isme koi side effect nahi hai. Kha sakte hain."
    cleaned, dropped = filter_text(text)
    assert dropped >= 1
    assert "bilkul safe" not in cleaned
    assert "koi side effect nahi" not in cleaned


def test_apply_safety_filter_on_models():
    summary = Summary(
        what_it_is="A healthy cereal that cures heart disease.",
        good_things=["Contains whole oats", "Totally safe for children"],
        watch_out=["High in sugar"],
        suits=["Active adults"],
        avoid_or_ask_doctor=["Diabetics"],
        overall_note="Best breakfast.",
    )
    qa = QAAnswer(
        question="Is it safe?",
        answer="Yes, it has no side effects whatsoever. Eat in moderation.",
        source="general",
    )
    new_sum, new_qa, _, warnings = apply_safety_filter(summary, qa, [])
    assert new_sum is not None
    assert "cures" not in new_sum.what_it_is
    assert len(new_sum.good_things) == 1
    assert "Totally safe" not in new_sum.good_things[0]
    assert new_qa is not None
    assert "no side effects" not in new_qa.answer
    assert any("unsafe-sounding claims were removed" in w for w in warnings)
