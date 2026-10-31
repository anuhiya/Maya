"""Weekly cost, overtime and totals in exact decimal math (B4, X1)."""
from dataclasses import dataclass, field
from decimal import ROUND_FLOOR, ROUND_HALF_UP, Decimal

from maya.models import Category, Finding, ImpactResult, ImpactRow, Timing
from maya.timing import parse_date

CENT = Decimal("0.01")
STANDARD_WEEK = Decimal("40")
OVERTIME_FACTOR = Decimal("1.5")
WEEKS_PER_YEAR = Decimal("52")
HOURS_PER_YEAR = Decimal("2080")
ANNUALIZED_LABEL = "annualized (52 weeks)"
TAX_RATE = Decimal("0.0765")  # employer Social Security and Medicare


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


def employer_tax(amount: Decimal) -> Decimal:
    return cents(amount * TAX_RATE)


def spread_tax(amounts: dict[str, Decimal]) -> dict[str, Decimal]:
    """The panel tax is worked out once, then handed out by largest remainder so shares add up to it."""
    panel = employer_tax(sum(amounts.values(), Decimal("0")))
    exact = {k: v * TAX_RATE for k, v in amounts.items()}
    shares = {k: x.quantize(CENT, rounding=ROUND_FLOOR) for k, x in exact.items()}
    left = int((panel - sum(shares.values())) / CENT)
    for k in sorted(exact, key=lambda k: (shares[k] - exact[k], k))[:left]:
        shares[k] += CENT
    return shares


@dataclass(frozen=True)
class CostLine:
    """One panel line. weekly and yearly are None when Maya cannot calculate it."""

    label: str
    weekly: Decimal | None
    yearly: Decimal | None
    status: str
    note: str = ""


@dataclass(frozen=True)
class EmployeeTotal:
    employee_id: str
    changes: str
    now: Decimal
    coming: Decimal
    coming_dates: str
    tax: Decimal
    total: Decimal
    flags: str


@dataclass(frozen=True)
class TotalCost:
    lines: list[CostLine]
    employees: list[EmployeeTotal]


@dataclass
class _Acc:
    changes: list[str] = field(default_factory=list)
    now: Decimal = Decimal("0.00")
    coming: Decimal = Decimal("0.00")
    dates: list[str] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)


def _once(items: list[str], item: str) -> None:
    if item not in items:
        items.append(item)


def _sections(pairs: list[tuple[Finding, list[ImpactRow]]], *categories: Category) -> str:
    return ", ".join(f"{f.section} {f.jurisdiction}" for f, _ in pairs if f.category in categories)


def _employee_totals(pairs: list[tuple[Finding, list[ImpactRow]]]) -> list[EmployeeTotal]:
    accs: dict[str, _Acc] = {}
    for f, rows in pairs:
        for r in rows:
            affected = r.result is ImpactResult.AFFECTED and r.weekly_increase is not None
            if not (affected or r.result is ImpactResult.NEEDS_REVIEW or r.flags):
                continue
            acc = accs.setdefault(r.employee_id, _Acc())
            _once(acc.changes, f"{f.section} {f.jurisdiction}")
            if r.result is ImpactResult.NEEDS_REVIEW:
                _once(acc.flags, r.reason)
            for flag in r.flags:
                _once(acc.flags, flag.reason)
            if not affected:
                continue
            if r.timing is Timing.CURRENT:
                acc.now += r.weekly_increase
            elif r.timing is Timing.FUTURE:
                acc.coming += r.weekly_increase
                when = parse_date(f.effective_date)
                _once(acc.dates, when.isoformat() if when else "date unclear")
            else:
                _once(acc.flags, f"Date unclear for {f.section} {f.jurisdiction}, not in totals")
    taxes = spread_tax({k: a.now for k, a in accs.items()})
    return [EmployeeTotal(k, "; ".join(a.changes), a.now, a.coming, "; ".join(a.dates), taxes[k],
                          a.now + taxes[k], "; ".join(a.flags))
            for k, a in sorted(accs.items())]


def total_cost(pairs: list[tuple[Finding, list[ImpactRow]]]) -> TotalCost:
    """The X1 panel: calculated lines with numbers, everything else flagged with no number."""
    rows = [r for _, rs in pairs for r in rs]
    now = sum_by_timing(rows)[Timing.CURRENT]
    year, _ = annualized(now)
    tax, year_tax = employer_tax(now), employer_tax(year)
    lines = [
        CostLine("Wage increases in effect", now, year, "Calculated"),
        CostLine("Employer Social Security and Medicare", tax, year_tax, "Estimate",
                 "7.65% of the increase; assumes everyone is under the wage base"),
        CostLine("Total in effect", now + tax, year + year_tax, "Calculated"),
    ]
    coming: dict = {}
    for f, rs in pairs:
        amount = sum((r.weekly_increase for r in rs if r.result is ImpactResult.AFFECTED
                      and r.timing is Timing.FUTURE and r.weekly_increase is not None), Decimal("0.00"))
        if amount:
            when = parse_date(f.effective_date)
            coming[when] = coming.get(when, Decimal("0.00")) + amount
    for when, amount in sorted(coming.items()):
        lines.append(CostLine(f"Wage increases coming, effective {when.isoformat()}", amount,
                              annualized(amount)[0], "Calculated", "Shown apart, not added to in effect"))
    if not coming:
        lines.append(CostLine("Wage increases coming", Decimal("0.00"), Decimal("0.00"), "Calculated",
                              "Shown apart, not added to in effect"))
    tax_rate = _sections(pairs, Category.TAX_RATE)
    if tax_rate:
        lines.append(CostLine("Unemployment tax change", None, None, "Flagged",
                              f"{tax_rate}: the rate changes on taxable wages and the wage base is not stated"))
    if _sections(pairs, Category.WAGES):
        lines.append(CostLine("Back pay", None, None, "Needs reviewer input",
                              "Depends on the date pay was updated, which the documents do not give"))
    filing = _sections(pairs, Category.FILING_DEADLINE, Category.REPORTING)
    if filing:
        lines.append(CostLine("Filing and reporting changes", Decimal("0.00"), Decimal("0.00"), "Listed",
                              f"{filing}: process changes, no pay impact"))
    return TotalCost(lines, _employee_totals(pairs))
