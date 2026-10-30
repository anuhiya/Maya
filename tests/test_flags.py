"""Flags for missing, unclear and conflicting information (B2, V3)."""
from pathlib import Path

import pytest

from maya.flags import conflicting_values, date_flag, new_wording
from maya.models import FlagName
from maya.split import read_sections

ROOT = Path(__file__).resolve().parent.parent
V1 = {s.number: s for s in read_sections(ROOT / "data/policies/gov_rules_v1.txt")}
V2 = {s.number: s for s in read_sections(ROOT / "data/policies/gov_rules_v2.txt")}


@pytest.mark.parametrize("text, name", [
    (None, FlagName.MISSING_DATE),
    ("", FlagName.MISSING_DATE),
    ("missing", FlagName.MISSING_DATE),
    ("To be determined", FlagName.UNCLEAR_DATE),
    ("TBD", FlagName.UNCLEAR_DATE),
    ("Pending", FlagName.UNCLEAR_DATE),
    ("03/04/2027", FlagName.UNREADABLE_DATE_FORMAT),
    ("1 January 2027", FlagName.UNREADABLE_DATE_FORMAT),
])
def test_date_flags(text, name):
    flag = date_flag(text)
    assert flag.name is name
    assert flag.reason


@pytest.mark.parametrize("text", ["2027-01-01", "January 1, 2027", "Jan 1, 2027"])
def test_good_dates_have_no_flag(text):
    assert date_flag(text) is None


def test_real_bulletins_date_flags():
    assert date_flag(V2["2.3"].effective_date).name is FlagName.MISSING_DATE
    assert date_flag(V2["3.3"].effective_date).name is FlagName.UNCLEAR_DATE
    assert date_flag(V2["1.1"].effective_date) is None


def test_conflicting_values():
    assert conflicting_values("Pay not less than $16.00 per hour, or $17.25 per hour.").name is FlagName.CONFLICTING_VALUES
    assert conflicting_values("Pay not less than $16 per hour; that is $16.00 per hour.") is None
    assert conflicting_values("Pay $16.00 per hour within 20 days.") is None


def test_new_wording_needs_both_versions():
    assert new_wording(None, V2["1.3"]) is None
    assert new_wording(V1["1.1"], None) is None
    assert new_wording(V1["3.2"], V2["3.2"]).name is FlagName.NEW_WORDING
    assert new_wording(V1["3.1"], V2["3.1"]) is None  # identical rule text
