"""Weekly cost, overtime and totals in exact decimal math (B4, X1)."""
from decimal import ROUND_HALF_UP, Decimal

from maya.models import ImpactResult, ImpactRow, Timing

CENT = Decimal("0.01")
STANDARD_WEEK = Decimal("40")
OVERTIME_FACTOR = Decimal("1.5")
WEEKS_PER_YEAR = Decimal("52")
HOURS_PER_YEAR = Decimal("2080")
ANNUALIZED_LABEL = "annualized (52 weeks)"


def cents(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def _plain(value: Decimal) -> str:
    """Hours as written: 40, 37.5 (no exponent, no trailing zeros)."""
    text = format(value.normalize(), "f")
    return text


def weekly_increase(wage: Decimal, hours: Decimal, new_minimum: Decimal) -> tuple[Decimal, str]:
    """Weekly cost of lifting one hourly wage to the new minimum, with the math as text."""
    gap = new_minimum - wage
    if gap <= 0:
        raise ValueError("wage is not below the new minimum")
    regular = min(hours, STANDARD_WEEK)
    overtime = max(hours - STANDARD_WEEK, Decimal("0"))
    amount = cents(gap * regular + gap * OVERTIME_FACTOR * overtime)
    g = f"{gap:.2f}"
    text = f"{g} x {_plain(regular)} h"
    if overtime > 0:
        text += f" + {g} x 1.5 x {_plain(overtime)} h"
    return amount, f"{text} = ${amount:.2f}"


def implied_hourly_rate(annual_salary: Decimal) -> Decimal:
    """Annual salary over 2,080 hours, for the exempt-employee reason only."""
    return cents(annual_salary / HOURS_PER_YEAR)


def sum_by_timing(rows: list[ImpactRow]) -> dict[Timing, Decimal]:
    """Totals of affected rows only. Current, future and unknown are never mixed."""
    totals = {t: Decimal("0.00") for t in Timing}
    for row in rows:
        if row.result is ImpactResult.AFFECTED and row.weekly_increase is not None:
            totals[row.timing] += row.weekly_increase
    return totals


def annualized(weekly_total: Decimal) -> tuple[Decimal, str]:
    return cents(weekly_total * WEEKS_PER_YEAR), ANNUALIZED_LABEL
