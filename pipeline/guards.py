"""Guards for medicine label refusal, dietary supplement notices, and non-food / bill refusal."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from config import BASE_DIR
from pipeline.models import ExtractResult

logger = logging.getLogger("label_reader.guards")

DATA_PATH = BASE_DIR / "data" / "medicine_keywords.json"

MEDICINE_REFUSAL_EN = (
    "This looks like a medicine label. Label Reader only explains packaged food, "
    "so it will not analyse it. Please read the leaflet or ask a pharmacist or doctor."
)

MEDICINE_REFUSAL_HINGLISH = (
    "Yeh medicine ka label lagta hai. Label Reader sirf packaged food samjhata hai, "
    "isliye main ise analyse nahi karunga. Kripya leaflet padhein ya pharmacist/doctor se poochein."
)

SUPPLEMENT_WARNING = (
    "This looks like a supplement. Dose and suitability depend on your health. "
    "Ask a doctor or dietitian, especially if pregnant, on medication or with a medical condition."
)

NON_FOOD_REFUSAL_EN = (
    "This does not appear to be a packaged food label (detected a bill, receipt, invoice, or non-food item). "
    "PARAKH only analyzes packaged food product labels. Please upload a clear photo of food packaging."
)

NON_FOOD_REFUSAL_HINGLISH = (
    "Yeh packaged food ka label nahi lagta (bill, receipt, invoice ya non-food document detect hua hai). "
    "PARAKH sirf packaged food products ke labels ko analyse karta hai. Kripya packaged food pack ki photo upload karein."
)

BILL_STRONG_KEYWORDS = [
    "tax invoice", "retail invoice", "cash memo", "bill of supply", "gstin",
    "subtotal", "sub total", "grand total", "total amount", "payment mode",
    "credit card", "pos terminal", "invoice no", "table no", "cashier",
    "amount paid", "change due", "order id", "balance due", "gst no",
    "cgst", "sgst", "igst", "receipt no", "total qty", "bill no", "invoice #",
    "bill #", "merchant copy", "customer copy", "bill amount", "tax invoice/bill",
    "upi ref", "tax summary", "hsn code", "payment method", "sales receipt",
]

NON_FOOD_DOC_KEYWORDS = [
    "prescription", "patient name", "doctor name", "hospital", "clinic",
    "resume", "curriculum vitae", "salary slip", "boarding pass", "id card",
    "driving licence", "passport", "aadhaar", "pan card", "terms and conditions",
]


def _load_keywords() -> dict[str, list[str]]:
    if not DATA_PATH.exists():
        return {"strong": ["schedule h", "rx only", "dosage:"], "weak": ["tablet", "capsule"]}
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def calculate_medicine_score(text: str) -> int:
    """Calculates medicine keyword score on text."""
    if not text:
        return 0
    lower = text.lower()
    kw_data = _load_keywords()
    score = 0

    for strong_kw in kw_data.get("strong", []):
        if strong_kw.lower() in lower:
            score += 2
            # One strong match is enough (score >= 2)
            return score

    for weak_kw in kw_data.get("weak", []):
        if weak_kw.lower() in lower:
            score += 1

    return score


def check_food_label(
    extract: ExtractResult,
    language: str = "English",
) -> tuple[bool, str | None]:
    """Determines whether the uploaded image is a valid packaged food label.
    
    Refuses if:
    1. Vision model explicitly identified is_food_label == False
    2. Transcription contains strong bill / receipt / invoice / tax indicators and no genuine food ingredients
    3. Transcription contains non-food document markers (prescriptions, boarding passes, etc.)
    
    Returns (is_refused, refusal_reason).
    """
    refusal_msg = NON_FOOD_REFUSAL_HINGLISH if language == "Hinglish" else NON_FOOD_REFUSAL_EN

    # 1. Model flag check
    if not extract.is_food_label:
        custom_reason = extract.non_food_reason
        if custom_reason:
            reason = f"{refusal_msg}\n({custom_reason})"
        else:
            reason = refusal_msg
        return True, reason

    # 2. Heuristic check on transcription
    text_lower = (extract.raw_transcription or "").lower()
    has_food_ingredients = "ingredient" in text_lower or bool(extract.ingredients)

    # Check non-food documents (prescriptions, boarding passes, etc.)
    for kw in NON_FOOD_DOC_KEYWORDS:
        if kw in text_lower:
            return True, refusal_msg

    # Check strong bill/receipt markers
    for strong_kw in BILL_STRONG_KEYWORDS:
        if strong_kw in text_lower:
            # If a bill keyword is found and there are no food ingredients or veg marks, refuse
            if not has_food_ingredients or extract.veg_mark == "unknown":
                return True, refusal_msg

    return False, None


def check_medicine(
    extract: ExtractResult,
    language: str = "English",
) -> tuple[bool, str | None]:
    """Determines whether the product is a medicine and returns refusal status & message."""
    if extract.is_medicine:
        reason = MEDICINE_REFUSAL_HINGLISH if language == "Hinglish" else MEDICINE_REFUSAL_EN
        return True, reason

    score = calculate_medicine_score(extract.raw_transcription)
    if score >= 2:
        reason = MEDICINE_REFUSAL_HINGLISH if language == "Hinglish" else MEDICINE_REFUSAL_EN
        return True, reason

    return False, None


def check_supplement(extract: ExtractResult) -> str | None:
    """Returns a warning string if the product is marked as a supplement, else None."""
    if extract.is_supplement:
        return SUPPLEMENT_WARNING
    return None
