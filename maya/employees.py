"""Load and validate employees.csv (B3, P8)."""
import csv
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path

from pydantic import ValidationError

from maya.models import Employee, EmploymentType, WorkArrangement
from maya.site import load_config

REQUIRED = ("employee_id", "jurisdiction", "hourly_wage", "weekly_hours", "employment_type")
PLACES = ("jurisdiction", "office_location", "secondary_jurisdiction")  # residence may be outside every jurisdiction


@dataclass(frozen=True)
class Problem:
    row: int | None  # CSV line number (header is line 1); None for a file-level problem
    employee_id: str | None
    column: str | None
    message: str


@dataclass
class LoadResult:
    employees: list[Employee] = field(default_factory=list)
    problems: list[Problem] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems


def load_employees(path=None, cfg=None) -> LoadResult:
    """Read the CSV into Employee objects. Bad rows are reported and kept, never dropped."""
    cfg = cfg or load_config()
    path = Path(path) if path else cfg["_root"] / cfg["employees"]
    known = set(cfg["jurisdictions"])
    result = LoadResult()

    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        columns = reader.fieldnames or []
        rows = list(reader)

    missing = [c for c in REQUIRED if c not in columns]
    if missing:
        result.problems.append(Problem(None, None, ", ".join(missing),
                                       "required column missing: " + ", ".join(missing)))
        return result

    seen: set[str] = set()
    for line, raw in enumerate(rows, start=2):
        row = {k: v for k, v in raw.items() if k is not None}
        eid = (row.get("employee_id") or "").strip()
        problems = _check_row(row, columns, known)
        if not eid:
            problems.append(("employee_id", "employee_id is empty"))
        elif eid in seen:
            problems.append(("employee_id", f"duplicate employee_id {eid}"))
        seen.add(eid)
        result.problems += [Problem(line, eid or None, col, msg) for col, msg in problems]
        result.employees.append(_build(row))
    return result


def _build(row: dict) -> Employee:
    try:
        return Employee(**row)
    except ValidationError:
        # Keep the row so it is not silently dropped; its problems are reported separately.
        return Employee.model_construct(**{k: (v.strip() or None) if isinstance(v, str) else v
                                           for k, v in row.items()})


def _check_row(row: dict, columns: list[str], known: set[str]) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for col in ("hourly_wage", "weekly_hours"):
        try:
            if Decimal((row.get(col) or "").strip()) <= 0:
                out.append((col, f"{col} must be positive"))
        except InvalidOperation:
            out.append((col, f"{col} is not a number: {row.get(col)!r}"))
    if (row.get("employment_type") or "").strip() not in {t.value for t in EmploymentType}:
        out.append(("employment_type", f"unknown employment_type {row.get('employment_type')!r}"))
    for col in PLACES:
        value = (row.get(col) or "").strip()
        if value and value not in known:
            out.append((col, f"unknown jurisdiction {value!r} in {col}"))
    if "work_arrangement" in columns:
        out += _check_location(row, columns)
    return out


def _check_location(row: dict, columns: list[str]) -> list[tuple[str, str]]:
    def get(col):
        return (row.get(col) or "").strip()

    out: list[tuple[str, str]] = []
    arrangement, juris, secondary = get("work_arrangement"), get("jurisdiction"), get("secondary_jurisdiction")
    if arrangement not in {a.value for a in WorkArrangement}:
        return [("work_arrangement", f"work_arrangement must be onsite, hybrid or remote, got {arrangement!r}")]
    if arrangement == "onsite" and "office_location" in columns and get("office_location") != juris:
        out.append(("office_location", "onsite row: office_location must equal jurisdiction"))
    if arrangement == "remote" and "residence_jurisdiction" in columns and get("residence_jurisdiction") != juris:
        out.append(("residence_jurisdiction", "remote row: residence_jurisdiction must equal jurisdiction"))
    if secondary:
        if arrangement != "hybrid":
            out.append(("secondary_jurisdiction", f"secondary_jurisdiction only allowed on hybrid rows, not {arrangement}"))
        if secondary == juris:
            out.append(("secondary_jurisdiction", "secondary_jurisdiction must differ from jurisdiction"))
    return out
