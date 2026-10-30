"""Date parsing and timing against the as-of date (B8)."""
from datetime import date

import pytest

from maya.models import Timing
from maya.timing import classify, parse_date


@pytest.mark.parametrize("text, expected", [
    ("2027-01-01", date(2027, 1, 1)),
    ("January 1, 2027", date(2027, 1, 1)),
    ("Jan 1, 2027", date(2027, 1, 1)),
    ("November 1, 2026", date(2026, 11, 1)),
    ("Dec 31, 2031", date(2031, 12, 31)),
])
def test_accepted_formats(text, expected):
    assert parse_date(text) == expected


@pytest.mark.parametrize("text", [
    "03/04/2027", "1 January 2027", "2027-13-01", "February 30, 2027",
    "To be determined", "", None, "missing",
])
def test_other_formats_are_not_dates(text):
    assert parse_date(text) is None


def test_classify_against_as_of():
    as_of = date(2026, 11, 2)
    assert classify("November 1, 2026", as_of) is Timing.CURRENT
    assert classify("2026-11-02", as_of) is Timing.CURRENT  # on the as-of date
    assert classify("January 1, 2027", as_of) is Timing.FUTURE
    assert classify("To be determined", as_of) is Timing.UNKNOWN
    assert classify(None, as_of) is Timing.UNKNOWN
    assert classify("January 1, 2027", date(2027, 1, 1)) is Timing.CURRENT
