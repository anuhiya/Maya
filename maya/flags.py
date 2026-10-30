"""Flag rules for missing, unclear and conflicting information (B2, V3)."""
import re

from maya.checks import extract_numbers
from maya.models import Flag, FlagName, Section
from maya.split import rule_text
from maya.timing import parse_date

_UNCLEAR = re.compile(r"\b(to be determined|tbd|pending)\b", re.IGNORECASE)


def date_flag(effective_date: str | None) -> Flag | None:
    """Flag a date line that is missing, unclear or in a format we do not accept."""
    text = (effective_date or "").strip()
    if not text or text.lower() == "missing":
        return Flag(name=FlagName.MISSING_DATE, reason="No effective date found in the section.")
    if parse_date(text):
        return None
    if _UNCLEAR.search(text):
        return Flag(name=FlagName.UNCLEAR_DATE,
                    reason=f'The effective date is not decided yet: "{text}".')
    return Flag(name=FlagName.UNREADABLE_DATE_FORMAT,
                reason=f'The effective date "{text}" is not in an accepted format '
                       "(2027-01-01, January 1, 2027 or Jan 1, 2027).")


def conflicting_values(rule_sentence: str) -> Flag | None:
    """Flag a rule sentence that states two different dollar amounts."""
    amounts = sorted({v for kind, v in extract_numbers(rule_sentence) if kind == "dollars"})
    if len(amounts) < 2:
        return None
    shown = " and ".join(f"${a:.2f}" for a in amounts)
    return Flag(name=FlagName.CONFLICTING_VALUES,
                reason=f"The rule sentence states two different dollar amounts: {shown}.")


def new_wording(old: Section | None, new: Section | None) -> Flag | None:
    """Flag changed rule wording, only when both versions of the section exist."""
    if old is None or new is None or rule_text(old) == rule_text(new):
        return None
    return Flag(name=FlagName.NEW_WORDING,
                reason="The rule sentence is worded differently from the previous version.")
