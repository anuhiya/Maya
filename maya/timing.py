"""Classify a change as current, future or unknown against the as-of date (B8)."""
import re
from datetime import date

from maya.models import Timing

_MONTHS = ["january", "february", "march", "april", "may", "june", "july",
           "august", "september", "october", "november", "december"]
_ISO = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
_NAMED = re.compile(r"([A-Za-z]+) (\d{1,2}), (\d{4})")


def parse_date(text: str | None) -> date | None:
    """Parse the three accepted formats (any year); anything else is None."""
    if not text:
        return None
    text = text.strip()
    try:
        m = _ISO.fullmatch(text)
        if m:
            return date(int(m[1]), int(m[2]), int(m[3]))
        m = _NAMED.fullmatch(text)
        if m:
            name = m[1].lower()
            # Full month name, or its first three letters (Jan 1, 2027).
            for index, month in enumerate(_MONTHS, start=1):
                if name == month or (len(name) == 3 and month.startswith(name)):
                    return date(int(m[3]), index, int(m[2]))
    except ValueError:  # impossible day or month, such as February 30
        return None
    return None


def classify(effective_date: str | None, as_of: date) -> Timing:
    """No usable date is unknown; on or before the as-of date is current; after it is future."""
    when = parse_date(effective_date)
    if when is None:
        return Timing.UNKNOWN
    return Timing.CURRENT if when <= as_of else Timing.FUTURE
