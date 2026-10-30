"""Shared data contract: Finding, Employee, ImpactRow, Decision and enums (B2, B3, B6, B7).

Labels match docs/project-rules.md exactly. Jurisdictions are plain strings because
maya.config.yaml defines them (P8). This module holds shapes only: no matching, no money
arithmetic, no checks.
"""

from __future__ import annotations

import hashlib
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, field_validator, model_validator
from pydantic import Field


class Category(StrEnum):
    WAGES = "wages"
    TAX_RATE = "tax_rate"
    FILING_DEADLINE = "filing_deadline"
    REPORTING = "reporting"
    UNCLEAR = "unclear"


class ChangeType(StrEnum):
    SUBSTANTIVE = "substantive"
    WORDING_ONLY = "wording_only"
    ADDED = "added"
    REMOVED = "removed"


class Timing(StrEnum):
    CURRENT = "current"
    FUTURE = "future"
    UNKNOWN = "unknown"


class Status(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    DISMISSED = "dismissed"


class EmploymentType(StrEnum):
    HOURLY_FULL_TIME = "hourly_full_time"
    HOURLY_PART_TIME = "hourly_part_time"
    SALARIED_EXEMPT = "salaried_exempt"
    CONTRACTOR = "contractor"


class ImpactResult(StrEnum):
    AFFECTED = "affected"
    NOT_AFFECTED = "not_affected"
    EXCLUDED = "excluded"
    MATCHED_NO_ESTIMATE = "matched_no_estimate"
    NEEDS_REVIEW = "needs_review"  # hybrid only


class FlagName(StrEnum):
    MISSING_DATE = "missing_date"
    UNCLEAR_DATE = "unclear_date"
    UNREADABLE_DATE_FORMAT = "unreadable_date_format"
    CONFLICTING_VALUES = "conflicting_values"
    NEW_WORDING = "new_wording"
    CLASSIFICATION_WARNING = "classification_warning"


class WorkArrangement(StrEnum):
    ONSITE = "onsite"
    HYBRID = "hybrid"
    REMOTE = "remote"


class LogTag(StrEnum):
    PLAN = "PLAN"
    TOOL = "TOOL"
    AI = "AI"
    CHECK = "CHECK"
    RESULT = "RESULT"


# Export columns (B7), in file order, from docs/plan.md "Export columns".
FINDINGS_EXPORT_COLUMNS: tuple[str, ...] = (
    "finding_id", "section", "jurisdiction", "category", "change_type",
    "old_rule", "new_rule", "old_value", "new_value", "effective_date",
    "timing", "flags", "old_excerpt", "new_excerpt", "source_file",
    "review_status", "last_comment", "decided_at", "decided_by",
)

IMPACT_EXPORT_COLUMNS: tuple[str, ...] = (
    "finding_id", "employee_id", "jurisdiction", "employment_type",
    "hourly_wage", "weekly_hours", "rule_id", "result", "reason",
    "new_minimum", "weekly_increase", "calculation", "timing",
)


def finding_id(policy_family: str, section: str, category: Category | str) -> str:
    """Stable ID for a finding (decision 002).

    The policy family is a name from maya.config.yaml shared by every version of a
    bulletin. File names and versions are never part of it, so the same section keeps
    its ID when a newer version arrives and its review history stays attached.
    """
    family = policy_family.strip()
    sec = section.strip()
    cat = Category(category).value
    if not family or not sec:
        raise ValueError("policy family and section are required")
    digest = hashlib.sha256(f"{family}|{sec}|{cat}".encode("utf-8")).hexdigest()
    return digest[:12]


class Section(BaseModel):
    """One numbered section of a policy document."""

    number: str
    title: str
    text: str


class ExtractedFacts(BaseModel):
    """What the AI reads from one section (plan: Reading and comparing, step 2)."""

    section: str
    title: str
    jurisdiction: str
    effective_date: str  # exactly as written, or "missing"
    value: Decimal | None = None
    unit: str | None = None  # dollars per hour, percent, days
    day_type: str | None = None  # calendar or business
    obligation: str | None = None  # shall, must, may
    category: Category
    rule_quote: str
    date_quote: str | None = None


class Flag(BaseModel):
    name: FlagName
    reason: str  # plain English, shown to the reviewer


class CheckResult(BaseModel):
    """Outcome of one verification layer on one AI answer."""

    check: str  # for example V1, V2, V3
    passed: bool
    detail: str = ""


class Finding(BaseModel):
    """Every field under "Each finding stores" in docs/plan.md."""

    finding_id: str
    section: str
    jurisdiction: str
    category: Category
    change_type: ChangeType
    old_rule: str | None = None
    new_rule: str | None = None
    old_value: Decimal | None = None
    new_value: Decimal | None = None
    unit: str | None = None
    effective_date: str | None = None
    timing: Timing
    old_excerpt: str | None = None
    new_excerpt: str | None = None
    source_file: str
    flags: list[Flag] = Field(default_factory=list)
    ai_reason: str = ""
    check_results: list[CheckResult] = Field(default_factory=list)
    recommended_action: str = ""
    owner: str = ""


def _blank_to_none(value: Any) -> Any:
    if isinstance(value, str) and value.strip() == "":
        return None
    return value


class Employee(BaseModel):
    """One row of data/employees.csv: five required columns, then optional payroll ones."""

    employee_id: str
    jurisdiction: str  # work location
    hourly_wage: Decimal = Field(gt=0)
    weekly_hours: Decimal = Field(gt=0)
    employment_type: EmploymentType

    full_name: str | None = None
    job_title: str | None = None
    department: str | None = None
    hire_date: date | None = None
    pay_frequency: str | None = None
    flsa_status: str | None = None
    overtime_eligible: bool | None = None
    annual_salary: Decimal | None = None
    work_arrangement: WorkArrangement | None = None
    office_location: str | None = None
    secondary_jurisdiction: str | None = None
    residence_jurisdiction: str | None = None

    @field_validator(
        "full_name", "job_title", "department", "hire_date", "pay_frequency",
        "flsa_status", "overtime_eligible", "annual_salary", "work_arrangement",
        "office_location", "secondary_jurisdiction", "residence_jurisdiction",
        mode="before",
    )
    @classmethod
    def _empty_cell_is_none(cls, value: Any) -> Any:
        return _blank_to_none(value)

    @field_validator("overtime_eligible", mode="before")
    @classmethod
    def _yes_no(cls, value: Any) -> Any:
        if isinstance(value, str):
            return {"yes": True, "no": False}.get(value.strip().lower(), value)
        return value


class ImpactRow(BaseModel):
    """One employee's result for one finding. Field order equals IMPACT_EXPORT_COLUMNS."""

    finding_id: str
    employee_id: str
    jurisdiction: str
    employment_type: EmploymentType
    hourly_wage: Decimal
    weekly_hours: Decimal
    rule_id: str  # R1 to R4, or "none"
    result: ImpactResult
    reason: str
    new_minimum: Decimal | None = None
    weekly_increase: Decimal | None = None
    calculation: str = ""
    timing: Timing


class Decision(BaseModel):
    """One row of the append-only review history (B6)."""

    finding_id: str
    status: Status
    comment: str = ""
    decided_at: datetime
    decided_by: str  # a reviewer name, or "Auto-approved"

    @model_validator(mode="after")
    def _dismiss_needs_comment(self) -> "Decision":
        if self.status is Status.DISMISSED and not self.comment.strip():
            raise ValueError("a comment is required to dismiss a finding")
        return self


class AgentLogLine(BaseModel):
    """One line of the live agent log (A4)."""

    tag: LogTag
    text: str
    at: datetime
    replayed: bool = False  # True when the line comes from a saved run
