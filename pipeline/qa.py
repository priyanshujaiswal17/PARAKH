"""Question Answering module enforcing Honesty Rule H8 with evidence verification and source downgrading."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any
from rapidfuzz import fuzz

from config import BASE_DIR
from llm import generate
from pipeline.models import ExtractResult, QAAnswer, VerifiedItem
from pipeline.safety_filter import filter_text

logger = logging.getLogger("label_reader.qa")

QA_PROMPT_PATH = BASE_DIR / "prompts" / "qa.txt"


def verify_evidence_quotes(evidence_quotes: list[str], raw_transcription: str) -> list[str]:
    """Verifies that each evidence quote has partial_ratio >= 90 against the raw transcription."""
    surviving_quotes: list[str] = []
    lower_trans = raw_transcription.lower()

    for quote in evidence_quotes:
        clean_q = quote.strip()
        if not clean_q:
            continue
        # Direct substring check
        if clean_q.lower() in lower_trans:
            surviving_quotes.append(clean_q)
            continue
        # Fuzzy check: partial_ratio >= 90
        score = fuzz.partial_ratio(clean_q.lower(), lower_trans)
        if score >= 90.0:
            surviving_quotes.append(clean_q)

    return surviving_quotes


def answer_question(
    question: str,
    extract: ExtractResult,
    verified_ingredients: list[VerifiedItem],
    language: str = "English",
    backend: str | None = None,
    api_key: str | None = None,
) -> QAAnswer | None:
    """Answers user question with label evidence validation and H8 downgrading."""
    clean_q = question.strip()
    if not clean_q:
        return None

    if QA_PROMPT_PATH.exists():
        with open(QA_PROMPT_PATH, "r", encoding="utf-8") as f:
            template = f.read()
    else:
        template = (
            "Answer the question based on the label data in {language}.\n"
            "<label_data>\n{label_data_json}\n</label_data>\n"
            "<user_question>\n{user_question}\n</user_question>\n"
            "Return ONLY JSON: {{\"answer\": \"...\", \"source\": \"label|general|both|cannot_tell\", \"evidence\": [\"...\"]}}"
        )

    label_payload = {
        "product_name": extract.product_name,
        "brand": extract.brand,
        "veg_mark": extract.veg_mark,
        "is_supplement": extract.is_supplement,
        "raw_transcription": extract.raw_transcription,
        "verified_ingredients": [v.text for v in verified_ingredients],
        "claims": extract.claims,
    }
    label_json_str = json.dumps(label_payload, indent=2, ensure_ascii=False)

    prompt = (
        template.replace("{label_data_json}", label_json_str)
        .replace("{user_question}", clean_q)
        .replace("{language}", language)
    )

    schema = {
        "type": "object",
        "properties": {
            "answer": {"type": "string"},
            "source": {"type": "string", "enum": ["label", "general", "both", "cannot_tell"]},
            "evidence": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["answer", "source", "evidence"],
    }

    raw_answer = "Could not generate an answer at this time."
    source = "cannot_tell"
    evidence_list: list[str] = []

    try:
        resp = generate(
            images=[],
            prompt=prompt,
            schema=schema,
            backend=backend,
            api_key=api_key,
            temperature=0.2,
            max_tokens=1000,
        )
        if isinstance(resp, dict):
            raw_answer = resp.get("answer", raw_answer)
            source = resp.get("source", "cannot_tell")
            evidence_list = resp.get("evidence", [])
            if not isinstance(evidence_list, list):
                evidence_list = []
    except Exception as exc:
        logger.warning("QA model call failed: %s", exc)
        return QAAnswer(
            question=clean_q,
            answer="Could not answer the question due to a model error.",
            source="cannot_tell",
            evidence=[],
        )

    # Cap answer length to 80 words
    words = raw_answer.split()
    if len(words) > 80:
        raw_answer = " ".join(words[:80]) + "..."

    # Code checks (H8)
    # 1. Verify evidence quotes against raw_transcription
    surviving_evidence = verify_evidence_quotes(evidence_list, extract.raw_transcription)
    downgraded = False

    # 2. If source is 'label' or 'both' and no evidence survived, downgrade to 'general'
    if source in ("label", "both") and not surviving_evidence:
        source = "general"
        downgraded = True
        prefix = "Based on general knowledge, not this label: "
        if not raw_answer.startswith(prefix):
            raw_answer = f"{prefix}{raw_answer}"

    # 3. Apply safety filter
    clean_ans, _ = filter_text(raw_answer)

    return QAAnswer(
        question=clean_q,
        answer=clean_ans,
        source=source,
        evidence=surviving_evidence,
        downgraded=downgraded,
    )
