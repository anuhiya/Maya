"""Matching rules R1 to R4 against the real employee CSV (B3, B4, V4). No AI is called."""
from decimal import Decimal

import pytest

from maya.cost import annualized, sum_by_timing
from maya.employees import load_employees
from maya.impact import match_finding
from maya.models import (Category, ChangeType, Finding, FlagName, ImpactResult as R,
                         Timing, finding_id)

D = Decimal


@pytest.fixture(scope="module")
def employees():
    return load_employees().employees


def finding(juris, category, new_value=None, timing=Timing.CURRENT,
            change=ChangeType.SUBSTANTIVE, new_rule="", section="1.1"):
    return Finding(
        finding_id=finding_id("fam", f"{section}{juris}", category), section=section,
        jurisdiction=juris, category=category, change_type=change,
        new_value=None if new_value is None else D(new_value), new_rule=new_rule,
        timing=timing, source_file="x.txt")


def rows_for(f, employees):
    return {r.employee_id: r for r in match_finding(f, employees)}


def wage(juris, value, timing):
    return finding(juris, Category.WAGES, value, timing)


def test_avalon_minimum_wage(employees):
    rows = match_finding(wage("Avalon", "17.25", Timing.CURRENT), employees)
    affected = [r for r in rows if r.result is R.AFFECTED]
    assert len(affected) == 10
    assert sum_by_timing(rows)[Timing.CURRENT] == D("273.19")
    assert annualized(D("273.19"))[0] == D("14205.88")
    assert all(r.jurisdiction == "Avalon" for r in rows if r.result is not R.NEEDS_REVIEW)
    assert [r.employee_id for r in rows if r.result is R.NEEDS_REVIEW] == ["E076"]
    assert all(r.reason and r.rule_id == "R1" for r in rows)


def test_calder_minimum_wage_is_future(employees):
    rows = match_finding(wage("Calder", "15.50", Timing.FUTURE), employees)
    assert len([r for r in rows if r.result is R.AFFECTED]) == 7
    totals = sum_by_timing(rows)
    assert totals[Timing.FUTURE] == D("142.80")
    assert totals[Timing.CURRENT] == D("0.00")
    assert annualized(totals[Timing.FUTURE])[0] == D("7425.60")


def test_meridian_live_demo(employees):
    rows = rows_for(wage("Meridian", "15.00", Timing.FUTURE), employees)
    got = {k: r.weekly_increase for k, r in rows.items() if r.result is R.AFFECTED}
    assert got == {"E048": D("36.00"), "E055": D("31.25"), "E064": D("9.98"),
                   "E065": D("0.22"), "E072": D("12.00"), "E080": D("9.20")}
    assert sum(got.values()) == D("98.65")


def test_every_employee_in_jurisdiction_gets_a_row(employees):
    for juris in ("Avalon", "Calder", "Meridian"):
        expected = {e.employee_id for e in employees if e.jurisdiction == juris}
        rows = match_finding(wage(juris, "99", Timing.CURRENT), employees)
        assert expected <= {r.employee_id for r in rows}
        assert {r.employee_id for r in rows if r.jurisdiction == juris} == expected


# employee_id: (finding value, result, weekly increase, calculation)
CASES = {
    "E017": ("17.25", R.AFFECTED, "47.50", "1.25 x 38 h = $47.50"),
    "E020": ("17.25", R.AFFECTED, "0.40", "0.01 x 40 h = $0.40"),
    "E004": ("17.25", R.NOT_AFFECTED, None, ""),
    "E013": ("17.25", R.NOT_AFFECTED, None, ""),
    "E077": ("17.25", R.NOT_AFFECTED, None, ""),
    "E001": ("17.25", R.AFFECTED, "8.17", "0.19 x 40 h + 0.19 x 1.5 x 2 h = $8.17"),
    "E015": ("17.25", R.AFFECTED, "7.80", "0.39 x 20 h = $7.80"),
    "E002": ("17.25", R.AFFECTED, "35.60", "0.89 x 40 h = $35.60"),
    "E073": ("17.25", R.AFFECTED, "18.00", "0.45 x 40 h = $18.00"),
    "E079": ("17.25", R.AFFECTED, "46.00", "1.15 x 40 h = $46.00"),
}


@pytest.mark.parametrize("eid", CASES)
def test_avalon_edge_cases(employees, eid):
    value, result, amount, calc = CASES[eid]
    row = rows_for(wage("Avalon", value, Timing.CURRENT), employees)[eid]
    assert row.result is result
    assert row.weekly_increase == (None if amount is None else D(amount))
    assert row.calculation == calc
    assert row.new_minimum == D(value)


def test_calder_and_meridian_edge_cases(employees):
    calder = rows_for(wage("Calder", "15.50", Timing.FUTURE), employees)
    assert calder["E025"].weekly_increase == D("20.90")
    assert calder["E025"].timing is Timing.FUTURE
    assert calder["E071"].weekly_increase == D("16.00")
    assert calder["E076"].result is R.NOT_AFFECTED  # hybrid, above $15.50
    mer = rows_for(wage("Meridian", "15.00", Timing.FUTURE), employees)
    assert mer["E080"].weekly_increase == D("9.20")
    assert mer["E078"].result is R.NOT_AFFECTED
    assert mer["E068"].result is R.NOT_AFFECTED  # exactly at the minimum


def test_remote_calder_worker_with_avalon_office_not_hit_by_avalon(employees):
    avalon = rows_for(wage("Avalon", "17.25", Timing.CURRENT), employees)
    assert "E071" not in avalon  # works in Calder; only the primary jurisdiction matches


def test_hybrid_employee_is_matched_by_primary_jurisdiction_only(employees):
    avalon = rows_for(wage("Avalon", "17.25", Timing.CURRENT), employees)
    assert avalon["E076"].jurisdiction == "Calder"  # only a hybrid review row, see below
    assert avalon["E076"].result is R.NEEDS_REVIEW
    assert "E078" not in avalon  # secondary is Calder, not Avalon
    assert avalon["E077"].result is R.NOT_AFFECTED


def test_hybrid_below_secondary_minimum_needs_review_with_upper_bound(employees):
    row = rows_for(wage("Avalon", "17.25", Timing.CURRENT), employees)["E076"]
    assert row.result is R.NEEDS_REVIEW
    assert row.reason == "Needs review: works part of the week in Avalon"
    assert row.weekly_increase is None
    assert "1.45 x 40 h = $58.00" in row.calculation and "upper bound" in row.calculation.lower()
    assert row.new_minimum == D("17.25")
    row = rows_for(wage("Calder", "15.50", Timing.FUTURE), employees)["E078"]
    assert row.result is R.NEEDS_REVIEW
    assert row.reason == "Needs review: works part of the week in Calder"
    assert "0.30 x 24 h = $7.20" in row.calculation and row.timing is Timing.FUTURE


def test_hybrid_review_rows_never_enter_totals(employees):
    for juris, value, timing, total in (("Avalon", "17.25", Timing.CURRENT, "273.19"),
                                        ("Calder", "15.50", Timing.FUTURE, "142.80")):
        rows = match_finding(wage(juris, value, timing), employees)
        assert any(r.result is R.NEEDS_REVIEW for r in rows)
        assert sum_by_timing(rows)[timing] == D(total)


def test_hybrid_at_or_above_secondary_minimum_gets_no_row(employees):
    assert "E076" not in rows_for(wage("Avalon", "15.80", Timing.CURRENT), employees)
    assert "E076" not in rows_for(wage("Avalon", "15.00", Timing.CURRENT), employees)


def test_hybrid_review_only_for_wage_findings(employees):
    f = finding("Avalon", Category.TAX_RATE, "3.1", Timing.FUTURE)
    assert "E076" not in rows_for(f, employees)


def test_exempt_is_excluded_without_warning_and_reason_names_implied_rate(employees):
    row = rows_for(wage("Avalon", "17.25", Timing.CURRENT), employees)["E016"]
    assert row.result is R.EXCLUDED
    assert row.flags == []
    assert "below" in row.reason and "17.25" in row.reason
    assert row.weekly_increase is None


def test_exempt_above_minimum_has_plain_reason(employees):
    rows = rows_for(wage("Avalon", "10.00", Timing.CURRENT), employees)
    exempt = [r for r in rows.values() if r.employment_type.value == "salaried_exempt"]
    assert exempt and all(r.result is R.EXCLUDED and "below" not in r.reason for r in exempt)


@pytest.mark.parametrize("eid,juris,value,timing", [
    ("E023", "Avalon", "17.25", Timing.CURRENT),
    ("E047", "Calder", "15.50", Timing.FUTURE),
])
def test_contractor_below_minimum_gets_classification_warning(employees, eid, juris, value, timing):
    row = rows_for(wage(juris, value, timing), employees)[eid]
    assert row.result is R.EXCLUDED
    assert row.reason.startswith("Classification warning:")
    assert [f.name for f in row.flags] == [FlagName.CLASSIFICATION_WARNING]
    assert row.flags[0].reason
    assert row.weekly_increase is None


def test_contractor_at_or_above_minimum_has_no_warning(employees):
    rows = rows_for(wage("Avalon", "10.00", Timing.CURRENT), employees)
    assert rows["E023"].result is R.EXCLUDED
    assert rows["E023"].flags == []


def test_tax_rate_r2(employees):
    rows = match_finding(finding("Avalon", Category.TAX_RATE, "3.1", Timing.FUTURE,
                                 section="1.2"), employees)
    matched = [r for r in rows if r.result is R.MATCHED_NO_ESTIMATE]
    assert len(matched) == 25
    assert all(r.rule_id == "R2" and r.weekly_increase is None and r.new_minimum is None
               for r in rows)
    assert all(r.result is R.EXCLUDED for r in rows if r.employment_type.value == "contractor")
    assert sum_by_timing(rows)[Timing.FUTURE] == D("0.00")


def test_filing_deadline_r3(employees):
    rows = match_finding(finding("Calder", Category.FILING_DEADLINE, "20", Timing.FUTURE,
                                 section="2.2"), employees)
    assert len([r for r in rows if r.result is R.MATCHED_NO_ESTIMATE]) == 24
    assert {r.rule_id for r in rows} == {"R3"}


def test_reporting_other_than_new_hire_r4(employees):
    f = finding("Calder", Category.REPORTING, timing=Timing.UNKNOWN, section="2.3",
                new_rule="Every employer shall file an earnings report twice each calendar year.")
    rows = match_finding(f, employees)
    assert len([r for r in rows if r.result is R.MATCHED_NO_ESTIMATE]) == 24
    assert {r.rule_id for r in rows} == {"R4"}


def test_pay_statement_reporting_r4_reaches_25_in_avalon(employees):
    f = finding("Avalon", Category.REPORTING, timing=Timing.FUTURE, section="1.3",
                new_rule="Pay statements shall show the hours worked at each rate of pay.")
    assert len([r for r in match_finding(f, employees) if r.result is R.MATCHED_NO_ESTIMATE]) == 25


@pytest.mark.parametrize("juris,section,change,text", [
    ("Avalon", "1.4", ChangeType.ADDED,
     "Every employer shall give each newly hired employee a written notice."),
    ("Meridian", "3.3", ChangeType.SUBSTANTIVE,
     "Every employer shall report each NEWLY HIRED or rehired employee within 10 days."),
])
def test_new_hire_reporting_matches_no_current_employee(employees, juris, section, change, text):
    f = finding(juris, Category.REPORTING, timing=Timing.UNKNOWN, change=change,
                section=section, new_rule=text)
    rows = match_finding(f, employees)
    assert rows and {r.result for r in rows} == {R.NOT_AFFECTED}
    assert all("future hires only" in r.reason and r.rule_id == "R4" for r in rows)


def test_new_hire_terms_come_from_config(employees):
    f = finding("Calder", Category.REPORTING, new_rule="Report each new starter promptly.")
    cfg = {"matching": {"new_hire_terms": ["new starter"]}}
    rows = match_finding(f, employees, cfg=cfg)
    assert {r.result for r in rows} == {R.NOT_AFFECTED}


def test_wording_only_matches_nobody(employees):
    f = finding("Meridian", Category.WAGES, change=ChangeType.WORDING_ONLY, section="3.2")
    rows = match_finding(f, employees)
    assert rows and {r.result for r in rows} == {R.NOT_AFFECTED}
    assert {r.rule_id for r in rows} == {"none"}
    assert all(r.weekly_increase is None for r in rows)


def test_unclear_category_needs_review_for_non_contractors(employees):
    rows = match_finding(finding("Avalon", Category.UNCLEAR), employees)
    for r in rows:
        if r.employment_type.value == "contractor":
            assert r.result is R.EXCLUDED
        else:
            assert r.result is R.NEEDS_REVIEW
            assert r.rule_id == "none"
            assert r.reason == "category unclear, a reviewer decides"
    assert R.NOT_AFFECTED not in {r.result for r in rows}


def test_wage_finding_without_a_value_gives_no_estimate(employees):
    f = finding("Avalon", Category.WAGES, None)
    rows = match_finding(f, employees)
    hourly = [r for r in rows if r.employment_type.value.startswith("hourly")]
    assert hourly and {r.result for r in hourly} == {R.MATCHED_NO_ESTIMATE}
    assert all(r.weekly_increase is None for r in rows)


def test_rows_carry_finding_id_and_timing(employees):
    f = wage("Calder", "15.50", Timing.FUTURE)
    rows = match_finding(f, employees)
    assert {r.finding_id for r in rows} == {f.finding_id}
    assert {r.timing for r in rows} == {Timing.FUTURE}
