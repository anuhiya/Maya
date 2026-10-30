"""Weekly cost, overtime and totals (B4, V4)."""
from decimal import Decimal

import pytest

from maya.cost import annualized, sum_by_timing, weekly_increase
from maya.models import (EmploymentType, ImpactResult, ImpactRow, Timing)

D = Decimal


@pytest.mark.parametrize("wage,hours,new_min,amount,text", [
    ("16.00", "38", "17.25", "47.50", "1.25 x 38 h = $47.50"),
    ("17.24", "40", "17.25", "0.40", "0.01 x 40 h = $0.40"),
    ("17.06", "42", "17.25", "8.17", "0.19 x 40 h + 0.19 x 1.5 x 2 h = $8.17"),
    ("16.86", "20", "17.25", "7.80", "0.39 x 20 h = $7.80"),
    ("16.80", "40", "17.25", "18.00", "0.45 x 40 h = $18.00"),
    ("14.80", "44", "15.00", "9.20", "0.20 x 40 h + 0.20 x 1.5 x 4 h = $9.20"),
    ("14.55", "22", "15.50", "20.90", "0.95 x 22 h = $20.90"),
])
def test_weekly_increase_and_written_math(wage, hours, new_min, amount, text):
    got, calc = weekly_increase(D(wage), D(hours), D(new_min))
    assert got == D(amount)
    assert calc == text


def test_exactly_forty_hours_has_no_overtime_part():
    _, calc = weekly_increase(D("10.00"), D("40"), D("11.00"))
    assert "1.5" not in calc


def test_half_cent_rounds_up():
    # 0.15 x 1.5 x 1 h = 0.225 overtime part; 0.15 x 40 = 6.00; total 6.225 rounds half up
    got, _ = weekly_increase(D("9.85"), D("41"), D("10.00"))
    assert got == D("6.23")


def test_fractional_hours_are_shown_plainly():
    got, calc = weekly_increase(D("10.00"), D("37.5"), D("11.00"))
    assert got == D("37.50")
    assert "37.5 h" in calc


def test_no_gap_is_an_error():
    with pytest.raises(ValueError):
        weekly_increase(D("17.25"), D("40"), D("17.25"))


def _row(result, amount, timing):
    return ImpactRow(
        finding_id="f", employee_id="E", jurisdiction="Avalon",
        employment_type=EmploymentType.HOURLY_FULL_TIME, hourly_wage=D("1"),
        weekly_hours=D("1"), rule_id="R1", result=result, reason="r",
        weekly_increase=amount, timing=timing)


def test_totals_keep_timing_apart_and_skip_non_affected():
    rows = [
        _row(ImpactResult.AFFECTED, D("10.10"), Timing.CURRENT),
        _row(ImpactResult.AFFECTED, D("5.05"), Timing.CURRENT),
        _row(ImpactResult.AFFECTED, D("2.00"), Timing.FUTURE),
        _row(ImpactResult.NEEDS_REVIEW, D("99.00"), Timing.CURRENT),
        _row(ImpactResult.NOT_AFFECTED, None, Timing.CURRENT),
    ]
    totals = sum_by_timing(rows)
    assert totals[Timing.CURRENT] == D("15.15")
    assert totals[Timing.FUTURE] == D("2.00")
    assert totals[Timing.UNKNOWN] == D("0.00")


def test_annualized_is_52_weeks_with_label():
    value, label = annualized(D("273.19"))
    assert value == D("14205.88")
    assert label == "annualized (52 weeks)"
    assert annualized(D("142.80"))[0] == D("7425.60")
