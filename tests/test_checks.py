"""Verification layers V1 to V3 (V1, V2, V3)."""
from decimal import Decimal
from pathlib import Path

from maya.checks import check_v1, check_v2, check_v3, extract_numbers
from maya.models import Category, ChangeType, ExtractedFacts, Section
from maya.split import read_sections

ROOT = Path(__file__).resolve().parent.parent
V1 = {s.number: s for s in read_sections(ROOT / "data/policies/gov_rules_v1.txt")}
V2 = {s.number: s for s in read_sections(ROOT / "data/policies/gov_rules_v2.txt")}


def facts_for(section, **over):
    base = dict(
        section=section.number, title=section.title, jurisdiction=section.jurisdiction,
        effective_date=section.effective_date or "missing", category=Category.WAGES,
        rule_quote=section.text.split("\n")[-1], date_quote=None,
    )
    base.update(over)
    return ExtractedFacts(**base)


def sec(text, jurisdiction="Avalon", date="January 1, 2027"):
    return Section(number="9.9", title="T", jurisdiction=jurisdiction, effective_date=date,
                   text=f"Jurisdiction: {jurisdiction}\nEffective Date: {date}\n{text}")


# extraction
def test_extract_numbers():
    nums = extract_numbers("Pay $1,016.00 or 2.7% within 20 calendar days or 40 hours.")
    assert nums == {("dollars", Decimal("1016")), ("percent", Decimal("2.7")),
                    ("days", Decimal("20")), ("hours", Decimal("40"))}
    assert extract_numbers("$15") == extract_numbers("$15.00")


# V1
def test_v1_passes_on_real_section():
    s = V2["1.1"]
    f = facts_for(s, value=Decimal("17.25"), date_quote="Effective Date: November 1, 2026")
    assert check_v1(s, f).passed


def test_v1_curly_quotes_and_spaces_are_normalised():
    s = sec("The employee’s  rate is $16.00 per hour.")
    f = facts_for(s, rule_quote="The employee's rate is $16.00 per hour.", value=Decimal("16.00"))
    assert check_v1(s, f).passed


def test_v1_fails_on_invented_quote_date_or_value():
    s = V2["1.1"]
    assert not check_v1(s, facts_for(s, rule_quote="Every employer shall pay $99.00.")).passed
    assert not check_v1(s, facts_for(s, date_quote="Effective Date: March 3, 2026")).passed
    r = check_v1(s, facts_for(s, value=Decimal("18.00")))
    assert not r.passed and "18.00" in r.detail


# V2
def test_v2_passes_for_real_wage_change():
    r = check_v2(V1["1.1"], V2["1.1"], Decimal("16.00"), Decimal("17.25"), ["value"])
    assert r.passed, r.detail


def test_v2_ignores_numbers_in_title_and_date_line():
    old, new = sec("Pay $16.00 per hour.", date="January 1, 2026"), sec("Pay $16.00 per hour.")
    assert check_v2(old, new, Decimal("16"), Decimal("16"), []).passed


def test_v2_fails_when_ai_value_not_in_section():
    r = check_v2(V1["1.1"], V2["1.1"], Decimal("16.00"), Decimal("17.50"), ["value"])
    assert not r.passed and "17.50" in r.detail


def test_v2_fails_when_numbers_differ_but_no_fact_changed():
    r = check_v2(V1["3.3"], V2["3.3"], Decimal("20"), Decimal("10"), [])
    assert not r.passed


def test_v2_fails_when_ai_claims_value_change_but_numbers_identical():
    r = check_v2(V1["3.1"], V2["3.1"], Decimal("13.75"), Decimal("15.00"), ["value"])
    assert not r.passed


def test_v2_added_section_checks_only_new_value():
    assert check_v2(None, V2["1.4"], None, None, ["section added"]).passed
    assert check_v2(None, V2["1.1"], None, Decimal("17.25"), ["section added"]).passed
    assert not check_v2(None, V2["1.1"], None, Decimal("1"), ["section added"]).passed


# V3
def test_v3_wording_only_passes_for_3_2():
    f = facts_for(V2["3.2"], category=Category.WAGES)
    assert check_v3(V1["3.2"], V2["3.2"], ChangeType.WORDING_ONLY, f, V2["3.2"]).passed


def test_v3_wording_only_fails_when_hours_change():
    old = sec("Pay one and one-half times the regular rate beyond 40 hours in a workweek.")
    new = sec("Pay one and one-half times the regular rate beyond 35 hours in a workweek.")
    r = check_v3(old, new, ChangeType.WORDING_ONLY, facts_for(new), new)
    assert not r.passed and "number" in r.detail


def test_v3_wording_only_fails_when_date_differs():
    old, new = sec("Pay $16.00.", date="January 1, 2026"), sec("Pay $16.00.", date="Jan 1, 2027")
    assert not check_v3(old, new, ChangeType.WORDING_ONLY, facts_for(new), new).passed


def test_v3_wording_only_needs_both_versions():
    f = facts_for(V2["1.4"])
    assert not check_v3(None, V2["1.4"], ChangeType.WORDING_ONLY, f, V2["1.4"]).passed


def test_v3_substantive_does_not_need_equal_numbers():
    f = facts_for(V2["1.1"])
    assert check_v3(V1["1.1"], V2["1.1"], ChangeType.SUBSTANTIVE, f, V2["1.1"]).passed


def test_v3_jurisdiction_must_match_section():
    f = facts_for(V2["1.1"], jurisdiction="Calder")
    r = check_v3(V1["1.1"], V2["1.1"], ChangeType.SUBSTANTIVE, f, V2["1.1"])
    assert not r.passed and "Avalon" in r.detail


def test_v3_category_must_be_a_label():
    f = facts_for(V2["1.1"]).model_copy(update={"category": "overtime"})
    assert not check_v3(V1["1.1"], V2["1.1"], ChangeType.SUBSTANTIVE, f, V2["1.1"]).passed
