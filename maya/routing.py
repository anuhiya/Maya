"""Auto-approval rule, approval mode and review reasons (A3, V6)."""
import sqlite3
from dataclasses import dataclass, field
from enum import StrEnum

from maya import db
from maya.models import Category, ChangeType, Decision, Finding, FlagName, Status
from maya.timing import parse_date

READY_LABEL = "Ready to approve"
AUTO_APPROVED = "Auto-approved"

REASON_NO_DATE = "No effective date found"
REASON_UNCLEAR_DATE = "Effective date is unclear"
REASON_WORDING = "New or changed wording that no value check covers"
REASON_TWO_AMOUNTS = "Two different amounts in one section"
REASON_ADDED_REMOVED = "Section added or removed"
REASON_DEADLINE = "Filing deadline or reporting change"
REASON_UNTRUSTED_OR_FAILED = "Source not trusted, an AI answer failed its check, or two runs disagree"


class ApprovalMode(StrEnum):
    PRE_APPROVE = "pre_approve"  # default and recommended: a person signs off
    AUTO_APPROVE = "auto_approve"  # optional: findings that pass the rule are approved straight away


def approval_mode(cfg: dict) -> ApprovalMode:
    """The mode set in maya.config.yaml (routing.approval_mode); Pre-approve when unset."""
    return ApprovalMode((cfg.get("routing") or {}).get("approval_mode", ApprovalMode.PRE_APPROVE))


@dataclass
class RuleResult:
    passed: bool
    conditions: list[tuple[str, bool]]

    @property
    def passed_conditions(self) -> list[str]:
        return [name for name, ok in self.conditions if ok]


@dataclass
class Route:
    ready: bool
    label: str | None  # READY_LABEL on a pending finding that passed the rule, otherwise None
    reasons: list[str] = field(default_factory=list)  # why a reviewer must decide
    passed_conditions: list[str] = field(default_factory=list)


def _flagged(finding: Finding, *names: FlagName) -> bool:
    return any(f.name in names for f in finding.flags)


def check_auto_approval(finding: Finding, *, trusted: bool, jurisdictions: list[str],
                        runs_agree: bool | None = None) -> RuleResult:
    """The eight conditions. runs_agree is None when repeat run is off."""
    checks = {c.check: c.passed for c in finding.check_results}
    conditions = [
        ("category is wages or tax rate", finding.category in (Category.WAGES, Category.TAX_RATE)),
        ("one old value and one new value",
         finding.old_value is not None and finding.new_value is not None
         and not _flagged(finding, FlagName.CONFLICTING_VALUES)),
        ("values match the source excerpts and the recomputation", checks.get("V1") is True and checks.get("V2") is True),
        ("effective date present and in an accepted format",
         parse_date(finding.effective_date) is not None
         and not _flagged(finding, FlagName.MISSING_DATE, FlagName.UNCLEAR_DATE, FlagName.UNREADABLE_DATE_FORMAT)),
        ("jurisdiction is known", finding.jurisdiction in jurisdictions),
        ("source is trusted", trusted),
        ("every AI answer passed its checks",
         bool(finding.check_results) and all(checks.values()) and runs_agree is not False),
        ("nothing else in the section changed",
         finding.change_type == ChangeType.SUBSTANTIVE and not _flagged(finding, FlagName.NEW_WORDING)),
    ]
    return RuleResult(passed=all(ok for _, ok in conditions), conditions=conditions)


def review_reasons(finding: Finding, rule: RuleResult) -> list[str]:
    """Why a person must decide, in the words of the plan's reasons table. Empty when the rule passed."""
    if rule.passed:
        return []
    reasons = []
    if _flagged(finding, FlagName.MISSING_DATE):
        reasons.append(REASON_NO_DATE)
    if _flagged(finding, FlagName.UNCLEAR_DATE, FlagName.UNREADABLE_DATE_FORMAT):
        reasons.append(REASON_UNCLEAR_DATE)
    wording = _flagged(finding, FlagName.NEW_WORDING)
    if wording:
        reasons.append(REASON_WORDING)
    if _flagged(finding, FlagName.CONFLICTING_VALUES):
        reasons.append(REASON_TWO_AMOUNTS)
    if finding.change_type in (ChangeType.ADDED, ChangeType.REMOVED):
        reasons.append(REASON_ADDED_REMOVED)
    failed = {name for name, ok in rule.conditions if not ok}
    if failed & {"source is trusted", "every AI answer passed its checks",
                 "values match the source excerpts and the recomputation"}:
        reasons.append(REASON_UNTRUSTED_OR_FAILED)
    if not reasons and finding.category in (Category.FILING_DEADLINE, Category.REPORTING):
        reasons.append(REASON_DEADLINE)  # named only when no more specific reason applies
    return reasons or [REASON_WORDING]


def route(finding: Finding, *, trusted: bool, jurisdictions: list[str],
          runs_agree: bool | None = None) -> Route:
    """Pre-approve: a passing finding stays pending and is labelled; anything else shows its reasons."""
    rule = check_auto_approval(finding, trusted=trusted, jurisdictions=jurisdictions, runs_agree=runs_agree)
    return Route(ready=rule.passed, label=READY_LABEL if rule.passed else None,
                 reasons=review_reasons(finding, rule), passed_conditions=rule.passed_conditions)


def decide(conn: sqlite3.Connection, finding_id: str, status: Status, reviewer: str, comment: str = "") -> int:
    """Record one human decision. Dismiss needs a comment; reversing is just another row."""
    return db.add_decision(conn, Decision(finding_id=finding_id, status=status, comment=comment,
                                          decided_at=db.utcnow(), decided_by=reviewer))


def sign_off(conn: sqlite3.Connection, routes: dict[str, Route], reviewer: str) -> list[int]:
    """One-click sign-off of Ready to approve findings, all or nothing.

    The passed conditions are the comment. Refuses a finding that is not ready or not pending.
    """
    for finding_id, r in routes.items():
        if not r.ready:
            raise ValueError(f"finding {finding_id} is not ready to approve")
        if db.current_status(conn, finding_id) is not Status.PENDING:
            raise ValueError(f"finding {finding_id} is not pending")
    return [decide(conn, fid, Status.APPROVED, reviewer, "; ".join(r.passed_conditions))
            for fid, r in routes.items()]


def auto_approve(conn: sqlite3.Connection, routes: dict[str, Route]) -> list[int]:
    """Auto-approve mode: approve ready findings that have no history yet, as "Auto-approved".

    A finding a person has touched (any history row, including a reversal) is left alone.
    The passed conditions are the comment.
    """
    return [decide(conn, fid, Status.APPROVED, AUTO_APPROVED, "; ".join(r.passed_conditions))
            for fid, r in routes.items() if r.ready and not db.history(conn, fid)]


def apply_mode(conn: sqlite3.Connection, mode: ApprovalMode, routes: dict[str, Route]) -> list[int]:
    """Pre-approve writes nothing; Auto-approve records the rule-passing findings."""
    return auto_approve(conn, routes) if mode is ApprovalMode.AUTO_APPROVE else []
