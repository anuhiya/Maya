"""Verify AI answers against the source: grounding, recomputation, consistency, dates (V1, V2, V3)."""
import re
from decimal import Decimal

from maya.ingest import normalise
from maya.models import Category, ChangeType, CheckResult, ExtractedFacts, Section
from maya.split import rule_text

# One number with an optional $ before, % after, or unit word after: "$16.00", "2.7%", "20 calendar days".
_NUMBER = re.compile(
    r"(?P<dollar>\$)?(?P<num>\d+(?:,\d{3})*(?:\.\d+)?)(?P<pct>%)?"
    r"(?:\s+(?P<unit>(?:calendar\s+|business\s+)?days?|hours?)\b)?",
    re.IGNORECASE,
)


def extract_numbers(text: str) -> set[tuple[str, Decimal]]:
    """Every number in the text as (kind, value). Kind: dollars, percent, days, hours or number.

    Done in code, never by the AI, so "$15" and "$15.00" are equal and nothing is guessed.
    """
    found = set()
    for m in _NUMBER.finditer(text):
        unit = (m["unit"] or "").lower()
        if m["dollar"]:
            kind = "dollars"
        elif m["pct"]:
            kind = "percent"
        elif "day" in unit:
            kind = "days"
        elif "hour" in unit:
            kind = "hours"
        else:
            kind = "number"
        found.add((kind, Decimal(m["num"].replace(",", ""))))
    return found


def _flat(text: str) -> str:
    """Normalised text with every run of whitespace, newlines included, as one space."""
    return re.sub(r"\s+", " ", normalise(text))


def _numbers(section: Section | None) -> set[tuple[str, Decimal]]:
    """Numbers in the rule sentence only: not the title, not the date line."""
    return extract_numbers(rule_text(section)) if section else set()


def _describe(numbers: set[tuple[str, Decimal]]) -> str:
    return ", ".join(f"{v:f} ({k})" for k, v in sorted(numbers, key=lambda n: (n[0], n[1]))) or "none"


def _reason(problems: list[str]) -> str:
    text = "; ".join(problems)
    return text[0].upper() + text[1:] + "."


def check_v1(section: Section, facts: ExtractedFacts) -> CheckResult:
    """V1: the quoted sentence, the date line and the value appear word for word in the section."""
    text = _flat(section.text)
    problems = []
    if _flat(facts.rule_quote) not in text:
        problems.append("the quoted rule sentence is not in the section")
    if facts.date_quote and _flat(facts.date_quote) not in text:
        problems.append("the quoted date line is not in the section")
    if facts.value is not None:
        as_written = str(facts.value)
        if not re.search(rf"(?<![\d.]){re.escape(as_written)}(?!\d)", text.replace(",", "")):
            problems.append(f"the value {as_written} does not appear in the section")
    if problems:
        return CheckResult(check="V1", passed=False, detail=_reason(problems))
    return CheckResult(check="V1", passed=True, detail="Quotes and value appear word for word in the section.")


def check_v2(old: Section | None, new: Section | None, old_value: Decimal | None,
             new_value: Decimal | None, facts_changed: list[str]) -> CheckResult:
    """V2: recompute the numbers in code and compare with what the AI claims."""
    old_nums, new_nums = _numbers(old), _numbers(new)
    problems = []
    for label, section, value, nums in (("old", old, old_value, old_nums), ("new", new, new_value, new_nums)):
        if value is not None and (section is None or value not in {v for _, v in nums}):
            problems.append(f"the AI's {label} value {value:f} is not a number in the {label} rule sentence "
                            f"(found: {_describe(nums)})")
    if old is not None and new is not None:
        if old_nums != new_nums and not facts_changed:
            problems.append("the numbers differ between versions "
                            f"(old: {_describe(old_nums)}; new: {_describe(new_nums)}) but the AI reports no change")
        if old_value is not None and new_value is not None and old_value != new_value and old_nums == new_nums:
            problems.append("the AI says the value changed but the numbers are identical in both versions")
    if problems:
        return CheckResult(check="V2", passed=False, detail=_reason(problems))
    return CheckResult(check="V2", passed=True, detail="Numbers recomputed in code agree with the AI.")


def check_v3(old: Section | None, new: Section | None, change_type: ChangeType,
             facts: ExtractedFacts, section: Section) -> CheckResult:
    """V3: wording_only needs identical facts; jurisdiction and category must be valid.

    `section` is the section the facts were read from.
    """
    problems = []
    if change_type == ChangeType.WORDING_ONLY:
        if old is None or new is None:
            problems.append("wording only needs both versions of the section")
        else:
            if _numbers(old) != _numbers(new):
                problems.append(f"wording only is rejected because a number differs "
                                f"(old: {_describe(_numbers(old))}; new: {_describe(_numbers(new))})")
            if _flat(old.effective_date or "") != _flat(new.effective_date or ""):
                problems.append("wording only is rejected because the effective date differs")
    if section.jurisdiction != facts.jurisdiction:
        problems.append(f"the AI's jurisdiction {facts.jurisdiction!r} does not match the section's "
                        f"Jurisdiction line {section.jurisdiction!r}")
    if str(facts.category) not in {c.value for c in Category}:
        problems.append(f"category {str(facts.category)!r} is not one of the five labels")
    if problems:
        return CheckResult(check="V3", passed=False, detail=_reason(problems))
    return CheckResult(check="V3", passed=True, detail="Change type, jurisdiction and category are consistent.")
