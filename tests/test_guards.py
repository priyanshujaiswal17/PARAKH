"""Tests for pipeline/guards.py."""

from pipeline.guards import check_medicine, check_supplement
from pipeline.models import ExtractResult


def test_model_flag_alone_refuses():
    ext = ExtractResult(
        is_medicine=True,
        raw_transcription="Paracetamol 500mg",
    )
    refused, reason = check_medicine(ext, language="English")
    assert refused is True
    assert "Label Reader only explains packaged food" in (reason or "")


def test_model_flag_hinglish():
    ext = ExtractResult(
        is_medicine=True,
        raw_transcription="Paracetamol 500mg",
    )
    refused, reason = check_medicine(ext, language="Hinglish")
    assert refused is True
    assert "Yeh medicine ka label lagta hai" in (reason or "")


def test_strong_keyword_refuses():
    ext = ExtractResult(
        is_medicine=False,
        raw_transcription="Schedule H Prescription Drug - Warning: To be sold by retail...",
    )
    refused, reason = check_medicine(ext)
    assert refused is True
    assert reason is not None


def test_hindi_medicine_keyword_refuses():
    ext = ExtractResult(
        is_medicine=False,
        raw_transcription="खुराक: दिन में दो बार पानी के साथ लें।",
    )
    refused, reason = check_medicine(ext)
    assert refused is True


def test_two_weak_keywords_refuse():
    ext = ExtractResult(
        is_medicine=False,
        raw_transcription="Each tablet contains active pharma ingredients. Take one dose daily.",
    )
    refused, reason = check_medicine(ext)
    assert refused is True


def test_consult_your_doctor_on_biscuit_not_refused():
    ext = ExtractResult(
        is_medicine=False,
        raw_transcription="High fiber whole wheat digestive biscuits. For specific dietary requirements, consult your doctor. Keep in cool dry place.",
    )
    refused, reason = check_medicine(ext)
    assert refused is False
    assert reason is None


def test_supplement_continues_with_warning():
    ext = ExtractResult(
        is_medicine=False,
        is_supplement=True,
        raw_transcription="100% Whey Protein Isolate Chocolate Flavor",
    )
    refused, _ = check_medicine(ext)
    assert refused is False

    supp_warning = check_supplement(ext)
    assert supp_warning is not None
    assert "This looks like a supplement" in supp_warning


def test_food_label_refuses_when_is_food_label_false():
    from pipeline.guards import check_food_label
    ext = ExtractResult(
        is_food_label=False,
        non_food_reason="Detected store bill or receipt",
        raw_transcription="Total: Rs 450",
    )
    refused, reason = check_food_label(ext, language="English")
    assert refused is True
    assert "This does not appear to be a packaged food label" in (reason or "")
    assert "store bill" in (reason or "")


def test_food_label_refuses_when_is_food_label_false_hinglish():
    from pipeline.guards import check_food_label
    ext = ExtractResult(
        is_food_label=False,
        raw_transcription="Subtotal: 200",
    )
    refused, reason = check_food_label(ext, language="Hinglish")
    assert refused is True
    assert "Yeh packaged food ka label nahi lagta" in (reason or "")


def test_food_label_refuses_tax_invoice_bill():
    from pipeline.guards import check_food_label
    ext = ExtractResult(
        is_food_label=True,
        raw_transcription="RETAIL TAX INVOICE - GSTIN: 27AAAAA0000A1Z5 - Subtotal: 1200 - CGST: 60 - SGST: 60 - Payment Mode: Credit Card",
        ingredients=[],
    )
    refused, reason = check_food_label(ext)
    assert refused is True
    assert "This does not appear to be a packaged food label" in (reason or "")


def test_food_label_refuses_non_food_prescription():
    from pipeline.guards import check_food_label
    ext = ExtractResult(
        is_food_label=True,
        raw_transcription="Medical Prescription - Patient Name: Ramesh Kumar - Clinic Address: Sector 4",
        ingredients=[],
    )
    refused, reason = check_food_label(ext)
    assert refused is True


def test_food_label_accepts_valid_food_package():
    from pipeline.guards import check_food_label
    ext = ExtractResult(
        is_food_label=True,
        product_name="Dark Chocolate Biscuit",
        ingredients=["Wheat Flour", "Sugar", "Cocoa Butter"],
        raw_transcription="Ingredients: Wheat Flour, Sugar, Cocoa Butter. Net Qty: 150g.",
        veg_mark="veg",
    )
    refused, reason = check_food_label(ext)
    assert refused is False
    assert reason is None

