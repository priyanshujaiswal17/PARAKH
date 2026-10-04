"""Expiry date parser and evaluator for packaged-food labels."""

from __future__ import annotations

import calendar
import re
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta

from pipeline.models import DateString, ExpiryResult

MONTHS = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "september": 9, "sept": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}

DISCLAIMER = " Dates are read from the photo. Please check the printed date on the pack."


def _clean_text(text: str) -> str:
    cleaned = text.strip()
    # Normalize slashes, hyphens, dots
    return cleaned


def _last_day_of_month(year: int, month: int) -> date:
    _, last_day = calendar.monthrange(year, month)
    return date(year, month, last_day)


def _safe_date(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _parse_duration(text: str) -> relativedelta | timedelta | None:
    """Extracts duration like '9 months', '180 days', '6 weeks', '1 year'."""
    pattern = re.compile(
        r"(\d+)\s*(days?|weeks?|months?|yrs?|years?)",
        re.IGNORECASE,
    )
    match = pattern.search(text)
    if not match:
        return None
    val = int(match.group(1))
    unit = match.group(2).lower()

    if "day" in unit:
        return timedelta(days=val)
    elif "week" in unit:
        return timedelta(weeks=val)
    elif "month" in unit:
        return relativedelta(months=val)
    elif "yr" in unit or "year" in unit:
        return relativedelta(years=val)
    return None


def _parse_absolute_date(text: str) -> tuple[date | None, bool, bool]:
    """Attempts to parse an absolute date or month-only date from text.
    
    Returns (parsed_date, is_month_only, is_ambiguous_dd_mm).
    If impossible date detected, returns (None, False, False) with error flag.
    """
    clean = text.upper()
    # Remove common prefix keywords
    clean = re.sub(
        r"\b(EXP|EXPIRY|EXP\.?|USE\s*BY|BEST\s*BEFORE|BB|MFG|MFD|PACKED|PKD|PKGD|DATE|OF|MFG\.?|ON)\b[:.]?",
        " ",
        clean,
    )
    clean = clean.strip()

    # Check ISO format: YYYY-MM-DD
    iso_match = re.search(r"\b(20\d\d)[-/.](0[1-9]|1[0-2])[-/.](0[1-9]|[12]\d|3[01])\b", clean)
    if iso_match:
        y, m, d = int(iso_match.group(1)), int(iso_match.group(2)), int(iso_match.group(3))
        dt = _safe_date(y, m, d)
        return dt, False, False

    # Check named month patterns:
    # e.g., 12 JAN 2026, 12-JAN-26, 12/JAN/2026, JAN 12 2026
    month_regex = r"(JAN(?:UARY)?|FEB(?:RUARY)?|MAR(?:CH)?|APR(?:IL)?|MAY|JUN(?:E)?|JUL(?:Y)?|AUG(?:UST)?|SEP(?:TEMBER)?|SEPT|OCT(?:OBER)?|NOV(?:EMBER)?|DEC(?:EMBER)?)"
    
    # Day Month Year: 12 JAN 2026 or 12-JAN-26
    d_m_y = re.search(rf"\b(0?[1-9]|[12]\d|3[01])\s*[-/.\s]?\s*{month_regex}\s*[-/.\s]?\s*(20\d\d|\d\d)\b", clean)
    if d_m_y:
        d = int(d_m_y.group(1))
        m = MONTHS[d_m_y.group(2).lower()]
        y_str = d_m_y.group(3)
        y = int(y_str) if len(y_str) == 4 else 2000 + int(y_str)
        dt = _safe_date(y, m, d)
        return dt, False, False

    # Month Day Year: JAN 12 2026 or JAN 12, 2026
    m_d_y = re.search(rf"\b{month_regex}\s*[-/.\s]\s*(0?[1-9]|[12]\d|3[01])\s*(?:,\s*|[-/.\s]\s*)(20\d\d|\d\d)\b", clean)
    if m_d_y:
        m = MONTHS[m_d_y.group(1).lower()]
        d = int(m_d_y.group(2))
        y_str = m_d_y.group(3)
        y = int(y_str) if len(y_str) == 4 else 2000 + int(y_str)
        dt = _safe_date(y, m, d)
        return dt, False, False

    # Month Year: JAN 2026, JAN-26, JAN26
    m_y = re.search(rf"\b{month_regex}\s*[-/.]?\s*(20\d\d|\d\d)\b", clean)
    if m_y:
        m = MONTHS[m_y.group(1).lower()]
        y_str = m_y.group(2)
        y = int(y_str) if len(y_str) == 4 else 2000 + int(y_str)
        try:
            return _last_day_of_month(y, m), True, False
        except ValueError:
            return None, False, False

    # Numeric formats: DD/MM/YYYY or DD/MM/YY
    # e.g., 12/01/2026, 12-01-26, 12.01.2026
    num_match = re.search(r"\b(\d{1,2})[-/.](\d{1,2})[-/.](\d{2,4})\b", clean)
    if num_match:
        n1, n2, y_str = int(num_match.group(1)), int(num_match.group(2)), num_match.group(3)
        y = int(y_str) if len(y_str) == 4 else 2000 + int(y_str)

        # In India, day-first is standard: n1 = day, n2 = month
        is_ambiguous = (1 <= n1 <= 12 and 1 <= n2 <= 12)
        d, m = n1, n2

        dt = _safe_date(y, m, d)
        if dt:
            return dt, False, is_ambiguous
        else:
            # If impossible date, like 31/02
            return None, False, False

    # Month/Year numeric: MM/YYYY or MM/YY e.g., 01/2026, 01/26, 12/2026
    m_y_num = re.search(r"\b(0?[1-9]|1[0-2])[-/.](\d{2,4})\b", clean)
    if m_y_num:
        m = int(m_y_num.group(1))
        y_str = m_y_num.group(2)
        y = int(y_str) if len(y_str) == 4 else 2000 + int(y_str)
        try:
            return _last_day_of_month(y, m), True, False
        except ValueError:
            return None, False, False

    return None, False, False


def evaluate(date_strings: list[DateString], today: date | None = None) -> ExpiryResult:
    """Evaluates expiry status from a list of DateString models."""
    if today is None:
        today = date.today()

    if not date_strings:
        return ExpiryResult(
            status="not_found",
            expiry_date=None,
            days_left=None,
            explanation="No expiry or best-before date was found in the photos. Check the pack." + DISCLAIMER,
        )

    # 1. Collect references (mfg / packed)
    mfg_dates: list[date] = []
    packed_dates: list[date] = []
    
    # Store candidates and tracking
    # tuple: (candidate_date, is_ambiguous_dd_mm)
    candidates: list[tuple[date, bool]] = []
    has_unparseable_expiry = False

    for ds in date_strings:
        text = ds.text.strip()
        kind = ds.kind

        # Check if duration string
        dur = _parse_duration(text)

        # Check absolute date
        abs_date, is_month_only, is_ambig = _parse_absolute_date(text)

        if kind in ("mfg", "packed"):
            if abs_date:
                # If month-only, reference starts at 1st of month per DECISIONS.md
                ref_date = date(abs_date.year, abs_date.month, 1) if is_month_only else abs_date
                if kind == "mfg":
                    mfg_dates.append(ref_date)
                else:
                    packed_dates.append(ref_date)
            else:
                # Check impossible date in mfg/packed
                if re.search(r"\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}", text):
                    has_unparseable_expiry = True

        elif kind in ("expiry", "best_before", "use_by", "use_within", "other"):
            if abs_date:
                candidates.append((abs_date, is_ambig))
            elif dur:
                # Need reference date
                ref = None
                if kind == "use_within" or "pack" in text.lower():
                    ref = min(packed_dates) if packed_dates else (min(mfg_dates) if mfg_dates else None)
                else:
                    ref = min(mfg_dates) if mfg_dates else (min(packed_dates) if packed_dates else None)

                if ref:
                    computed_date = ref + dur
                    candidates.append((computed_date, False))
                else:
                    # Duration found but no reference date available
                    has_unparseable_expiry = True
            else:
                # Text looks like it had a date/expiry claim but failed to parse
                has_unparseable_expiry = True

    # If no candidates parsed, check if any date string was unreadable
    if not candidates:
        if has_unparseable_expiry:
            return ExpiryResult(
                status="unreadable",
                expiry_date=None,
                days_left=None,
                explanation="A date was found but could not be read reliably. Check the pack." + DISCLAIMER,
            )
        return ExpiryResult(
            status="not_found",
            expiry_date=None,
            days_left=None,
            explanation="No expiry or best-before date was found in the photos. Check the pack." + DISCLAIMER,
        )

    # 4. Pick earliest candidate
    candidates.sort(key=lambda c: c[0])
    best_date, is_ambiguous = candidates[0]

    days_left = (best_date - today).days

    if days_left < 0:
        status = "expired"
        explanation = f"This product appears to have expired {abs(days_left)} days ago."
    elif 0 <= days_left <= 30:
        status = "expires_soon"
        explanation = f"Expires on {best_date.strftime('%d %b %Y')}, which is {days_left} days from today (expires soon)."
    else:
        status = "ok"
        explanation = f"Expires on {best_date.strftime('%d %b %Y')}, which is {days_left} days from today."

    if is_ambiguous:
        explanation += " (Date read as day/month)."

    explanation += DISCLAIMER

    return ExpiryResult(
        status=status,
        expiry_date=best_date,
        days_left=days_left,
        explanation=explanation,
    )
