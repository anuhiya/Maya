"""Tests for the shared data contract (B2, B3, B6, B7)."""

import csv
from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from maya.models import (
    FINDINGS_EXPORT_COLUMNS,
    IMPACT_EXPORT_COLUMNS,
    Category,
    ChangeType,
    Decision,
    Employee,
    EmploymentType,
    FlagName,
    ImpactResult,
    ImpactRow,
    LogTag,
    Section,
    Status,
    Timing,
    WorkArrangement,
    finding_id,
)

ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.parametrize(
    "enum, labels",
    [
        (Category, {"wages", "tax_rate", "filing_deadline", "reporting", "unclear"}),
        (ChangeType, {"substantive", "wording_only", "added", "removed"}),
        (Timing, {"current", "future", "unknown"}),
        (Status, {"pending", "approved", "dismissed"}),
        (
            EmploymentType,
            {"hourly_full_time", "hourly_part_time", "salaried_exempt", "contractor"},
        ),
        (
            ImpactResult,
            {"affected", "not_affected", "excluded", "matched_no_estimate", "needs_review"},
        ),
        (
            FlagName,
            {
                "missing_date", "unclear_date", "unreadable_date_format",
                "conflicting_values", "new_wording", "classification_warning",
            },
        ),
        (WorkArrangement, {"onsite", "hybrid", "remote"}),
        (LogTag, {"PLAN", "TOOL", "AI", "CHECK", "RESULT"}),
    ],
)
def test_enum_has_exactly_the_shared_labels(enum, labels):
    assert {member.value for member in enum} == labels


def test_every_employee_row_parses():
    with open(ROOT / "data" / "employees.csv", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) >= 50
    employees = [Employee(**row) for row in rows]
    assert len({e.employee_id for e in employees}) == len(rows)


def test_blank_optional_cells_become_none():
    emp = Employee(
        employee_id="X1", jurisdiction="Avalon", hourly_wage="15.00",
        weekly_hours="40", employment_type="hourly_full_time",
        annual_salary="", secondary_jurisdiction="", overtime_eligible="yes",
    )
    assert emp.annual_salary is None
    assert emp.secondary_jurisdiction is None
    assert emp.overtime_eligible is True


def test_employee_rejects_non_positive_wage():
    with pytest.raises(ValidationError):
        Employee(
            employee_id="X1", jurisdiction="Avalon", hourly_wage="0",
            weekly_hours="40", employment_type="contractor",
        )


def test_export_column_lists():
    assert len(FINDINGS_EXPORT_COLUMNS) == 19
    assert len(IMPACT_EXPORT_COLUMNS) == 13
    assert len(set(FINDINGS_EXPORT_COLUMNS)) == 19
    assert list(ImpactRow.model_fields) == list(IMPACT_EXPORT_COLUMNS)


def test_dismiss_requires_comment():
    now = datetime.now(timezone.utc)
    with pytest.raises(ValidationError):
        Decision(finding_id="abc", status="dismissed", comment="  ",
                 decided_at=now, decided_by="Anu")
    Decision(finding_id="abc", status="approved", decided_at=now, decided_by="Anu")


def test_finding_id_is_stable_and_sensitive():
    base = finding_id("psb", "1.1", Category.WAGES)
    assert base == finding_id("psb", "1.1", "wages")
    assert base != finding_id("psb", "1.2", Category.WAGES)
    assert base != finding_id("psb", "1.1", Category.TAX_RATE)
    assert base != finding_id("other", "1.1", Category.WAGES)


def test_same_section_in_v2_and_v3_gets_same_id():
    """The ID uses the policy family, never the file name or version."""
    family = "payroll_standards_bulletin"
    in_gov_rules_v2 = finding_id(family, "3.1", Category.WAGES)
    in_gov_rules_v3 = finding_id(family, "3.1", Category.WAGES)
    assert in_gov_rules_v2 == in_gov_rules_v3


def test_section_jurisdiction_and_effective_date():
    dated = Section(
        number="1.1", title="Wages", text="x",
        jurisdiction="Ontario", effective_date="1 Jan 2026",
    )
    assert dated.jurisdiction == "Ontario"
    assert dated.effective_date == "1 Jan 2026"
    undated = Section(number="1.2", title="Tax", text="y", jurisdiction="Ontario")
    assert undated.effective_date is None
    assert Section(number="1.3", title="T", text="z").jurisdiction is None
