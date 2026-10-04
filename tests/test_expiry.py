"""Tests for pipeline/expiry.py (>= 25 test cases)."""

from datetime import date
import pytest
from pipeline.models import DateString
from pipeline.expiry import evaluate


def test_empty_date_strings():
    res = evaluate([])
    assert res.status == "not_found"
    assert res.expiry_date is None
    assert res.days_left is None
    assert "No expiry or best-before date was found" in res.explanation


def test_exp_month_year_future():
    # EXP 12/2026 with today 2026-01-01 -> last day 2026-12-31
    ds = [DateString(kind="expiry", text="EXP 12/2026")]
    res = evaluate(ds, today=date(2026, 1, 1))
    assert res.status == "ok"
    assert res.expiry_date == date(2026, 12, 31)
    assert res.days_left == 364


def test_day_first_format():
    # 12-01-26 is read as 12 Jan 2026
    ds = [DateString(kind="expiry", text="12-01-26")]
    res = evaluate(ds, today=date(2026, 1, 1))
    assert res.status == "expires_soon"
    assert res.expiry_date == date(2026, 1, 12)
    assert res.days_left == 11
    assert "read as day/month" in res.explanation


def test_slash_day_first_format():
    ds = [DateString(kind="expiry", text="EXP 12/01/2026")]
    res = evaluate(ds, today=date(2026, 1, 1))
    assert res.expiry_date == date(2026, 1, 12)


def test_dot_day_first_format():
    ds = [DateString(kind="expiry", text="12.01.2026")]
    res = evaluate(ds, today=date(2026, 1, 1))
    assert res.expiry_date == date(2026, 1, 12)


def test_iso_format():
    ds = [DateString(kind="expiry", text="2026-01-12")]
    res = evaluate(ds, today=date(2026, 1, 1))
    assert res.status == "expires_soon"
    assert res.expiry_date == date(2026, 1, 12)


def test_impossible_date():
    # 31/02/2026 gives unreadable
    ds = [DateString(kind="expiry", text="31/02/2026")]
    res = evaluate(ds, today=date(2026, 1, 1))
    assert res.status == "unreadable"
    assert res.expiry_date is None
    assert "could not be read reliably" in res.explanation


def test_expired_item():
    ds = [DateString(kind="expiry", text="15/05/2025")]
    res = evaluate(ds, today=date(2026, 1, 1))
    assert res.status == "expired"
    assert res.days_left is not None and res.days_left < 0
    assert "expired" in res.explanation


def test_earliest_candidate_selected():
    # Two expiry candidates gives the earliest
    ds = [
        DateString(kind="expiry", text="EXP 15/06/2026"),
        DateString(kind="best_before", text="BB 10/03/2026"),
    ]
    res = evaluate(ds, today=date(2026, 1, 1))
    assert res.expiry_date == date(2026, 3, 10)


def test_duration_from_mfg():
    # Best before 9 months from MFG + MFG 03/25
    ds = [
        DateString(kind="mfg", text="MFG 03/25"),
        DateString(kind="best_before", text="Best before 9 months from MFG"),
    ]
    res = evaluate(ds, today=date(2025, 1, 1))
    # 2025-03-01 + 9 months = 2025-12-01
    assert res.expiry_date == date(2025, 12, 1)


def test_duration_from_packing():
    # Use within 6 months of packing + PKD 15 JAN 2026
    ds = [
        DateString(kind="packed", text="PKD 15 JAN 2026"),
        DateString(kind="use_within", text="Use within 6 months of packing"),
    ]
    res = evaluate(ds, today=date(2026, 1, 1))
    # 2026-01-15 + 6 months = 2026-07-15
    assert res.expiry_date == date(2026, 7, 15)
    assert res.status == "ok"


def test_named_month_jan_26():
    ds = [DateString(kind="expiry", text="JAN-26")]
    res = evaluate(ds, today=date(2026, 1, 1))
    assert res.expiry_date == date(2026, 1, 31)


def test_named_month_jan_2026():
    ds = [DateString(kind="expiry", text="JAN 2026")]
    res = evaluate(ds, today=date(2026, 1, 1))
    assert res.expiry_date == date(2026, 1, 31)


def test_named_month_with_day_12_jan_2026():
    ds = [DateString(kind="expiry", text="12 JAN 2026")]
    res = evaluate(ds, today=date(2026, 1, 1))
    assert res.expiry_date == date(2026, 1, 12)


def test_named_month_jan_12_2026():
    ds = [DateString(kind="expiry", text="JAN 12 2026")]
    res = evaluate(ds, today=date(2026, 1, 1))
    assert res.expiry_date == date(2026, 1, 12)


def test_short_token_jan26():
    ds = [DateString(kind="expiry", text="JAN26")]
    res = evaluate(ds, today=date(2026, 1, 1))
    assert res.expiry_date == date(2026, 1, 31)


def test_short_num_month_year_01_26():
    ds = [DateString(kind="expiry", text="01/26")]
    res = evaluate(ds, today=date(2026, 1, 1))
    assert res.expiry_date == date(2026, 1, 31)


def test_days_duration():
    ds = [
        DateString(kind="mfg", text="MFG 01/01/2026"),
        DateString(kind="best_before", text="Best before 180 days"),
    ]
    res = evaluate(ds, today=date(2026, 1, 1))
    assert res.expiry_date == date(2026, 6, 30)


def test_weeks_duration():
    ds = [
        DateString(kind="mfg", text="MFG 01/01/2026"),
        DateString(kind="best_before", text="Best before 4 weeks"),
    ]
    res = evaluate(ds, today=date(2026, 1, 1))
    assert res.expiry_date == date(2026, 1, 29)


def test_expires_today():
    ds = [DateString(kind="expiry", text="01/01/2026")]
    res = evaluate(ds, today=date(2026, 1, 1))
    assert res.status == "expires_soon"
    assert res.days_left == 0


def test_expires_tomorrow():
    ds = [DateString(kind="expiry", text="02/01/2026")]
    res = evaluate(ds, today=date(2026, 1, 1))
    assert res.status == "expires_soon"
    assert res.days_left == 1


def test_expires_in_30_days():
    ds = [DateString(kind="expiry", text="31/01/2026")]
    res = evaluate(ds, today=date(2026, 1, 1))
    assert res.status == "expires_soon"
    assert res.days_left == 30


def test_expires_in_31_days():
    ds = [DateString(kind="expiry", text="01/02/2026")]
    res = evaluate(ds, today=date(2026, 1, 1))
    assert res.status == "ok"
    assert res.days_left == 31


def test_expired_yesterday():
    ds = [DateString(kind="expiry", text="31/12/2025")]
    res = evaluate(ds, today=date(2026, 1, 1))
    assert res.status == "expired"
    assert res.days_left == -1


def test_unambiguous_day_month():
    # Day > 12 is unambiguous
    ds = [DateString(kind="expiry", text="25/08/2026")]
    res = evaluate(ds, today=date(2026, 1, 1))
    assert res.expiry_date == date(2026, 8, 25)
    assert "read as day/month" not in res.explanation


def test_unparseable_duration_without_ref():
    # Duration given with no MFG or PKD date
    ds = [DateString(kind="best_before", text="Best before 9 months from manufacture")]
    res = evaluate(ds, today=date(2026, 1, 1))
    assert res.status == "unreadable"
    assert res.expiry_date is None


def test_disclaimer_always_present():
    ds = [DateString(kind="expiry", text="2026-05-15")]
    res = evaluate(ds, today=date(2026, 1, 1))
    assert "Dates are read from the photo. Please check the printed date on the pack." in res.explanation
