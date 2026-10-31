"""Compare two documents into findings (B1, B2)."""
import hashlib
from dataclasses import dataclass

from maya.models import (Category, ChangeType, CheckResult, ExtractedFacts, Finding, Flag, Section,
                         Timing)

CHECK_FAILED = "AI answer failed its check."


@dataclass
class CompareResult:
    """Everything one document comparison produced."""

    findings: list[Finding]
    identical: int
    total: int
    trusted: bool  # the new file comes from a source marked trusted in maya.config.yaml
    source: str | None  # name of that source, None when the file is outside every configured source

    @property
    def summary(self) -> str:
        return f"{self.identical} of {self.total} sections identical"


def finding_id(policy: str, section: str, category: Category | str) -> str:
    """Stable hash of policy, section and category: the same change keeps the same ID on every run."""
    key = f"{policy}|{section}|{Category(category).value}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:12]


def merge_checks(results: list[CheckResult]) -> list[CheckResult]:
    """One result per check name (routing reads them by name): it passes only if every side passed."""
    order: list[str] = []
    by_name: dict[str, list[CheckResult]] = {}
    for result in results:
        if result.check not in by_name:
            order.append(result.check)
        by_name.setdefault(result.check, []).append(result)
    merged = []
    for name in order:
        group = by_name[name]
        failed = [r for r in group if not r.passed]
        if failed:
            merged.append(CheckResult(check=name, passed=False, detail=" ".join(r.detail for r in failed)))
        else:
            merged.append(CheckResult(check=name, passed=True, detail=group[0].detail))
    return merged


def _given_date(facts: ExtractedFacts | None) -> str | None:
    if facts is None or facts.effective_date.strip().lower() == "missing":
        return None
    return facts.effective_date


def build_finding(*, policy: str, source_file: str, old: Section | None, new: Section | None,
                  old_facts: ExtractedFacts | None, new_facts: ExtractedFacts | None,
                  change_type: ChangeType, reason: str, flags: list[Flag], timing: Timing,
                  checks: list[CheckResult]) -> Finding:
    """A finding from checked AI answers. Facts of the side that does not exist are None."""
    base = new_facts or old_facts
    return Finding(
        finding_id=finding_id(policy, (new or old).number, base.category),
        section=(new or old).number,
        jurisdiction=base.jurisdiction,
        category=base.category,
        change_type=change_type,
        old_rule=old_facts.rule_quote if old_facts else None,
        new_rule=new_facts.rule_quote if new_facts else None,
        old_value=old_facts.value if old_facts else None,
        new_value=new_facts.value if new_facts else None,
        unit=base.unit,
        effective_date=_given_date(base),
        timing=timing,
        old_excerpt=old.text if old else None,
        new_excerpt=new.text if new else None,
        source_file=source_file,
        flags=flags,
        ai_reason=reason,
        check_results=checks,
    )


def failed_finding(*, policy: str, source_file: str, old: Section | None, new: Section | None,
                   checks: list[CheckResult]) -> Finding:
    """No AI answer is trusted: carry only what code knows from the text, and the failed checks."""
    section = new or old
    if old is None:
        change_type = ChangeType.ADDED
    elif new is None:
        change_type = ChangeType.REMOVED
    else:
        change_type = ChangeType.SUBSTANTIVE
    return Finding(
        finding_id=finding_id(policy, section.number, Category.UNCLEAR),
        section=section.number,
        jurisdiction=section.jurisdiction or "unknown",
        category=Category.UNCLEAR,
        change_type=change_type,
        timing=Timing.UNKNOWN,
        old_excerpt=old.text if old else None,
        new_excerpt=new.text if new else None,
        source_file=source_file,
        ai_reason=CHECK_FAILED,
        check_results=merge_checks(checks),
    )
