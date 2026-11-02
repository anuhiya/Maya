"""Employee CSV loading and validation (B3, P8, V4)."""
from decimal import Decimal
from pathlib import Path

import pytest

from maya.employees import load_employees
from maya.models import EmploymentType
from maya.site import load_config

ROOT = Path(__file__).resolve().parent.parent
HEADER = ("employee_id,jurisdiction,hourly_wage,weekly_hours,employment_type,"
          "work_arrangement,office_location,secondary_jurisdiction,residence_jurisdiction")
GOOD = "E1,New York City,17.00,40,hourly_full_time,onsite,New York City,,New York City"

FT, PT = "hourly_full_time", "hourly_part_time"
SAL, CON = "salaried_exempt", "contractor"

# employee_id: (jurisdiction, type, wage, hours, arrangement, secondary, residence), from docs/expected.md
EDGE = {
    "E017": ("New York City", FT, "16.00", "38", None, None, None),
    "E020": ("New York City", FT, "17.24", "40", None, None, None),
    "E004": ("New York City", FT, "17.25", "40", None, None, None),
    "E013": ("New York City", PT, "17.25", "30", None, None, None),
    "E077": ("New York City", FT, "17.60", "40", "hybrid", "Chicago", None),
    "E001": ("New York City", FT, "17.06", "42", None, None, None),
    "E015": ("New York City", PT, "16.86", "20", None, None, None),
    "E002": ("New York City", FT, "16.36", "40", "onsite", None, "Los Angeles"),
    "E073": ("New York City", FT, "16.80", "40", "remote", None, "New York City"),
    "E079": ("New York City", FT, "16.10", "40", "hybrid", None, None),
    "E016": ("New York City", SAL, "16.35", "45", None, None, None),
    "E023": ("New York City", CON, "15.00", "20", None, None, None),
    "E076": ("Los Angeles", FT, "15.80", "40", "hybrid", "New York City", None),
    "E025": ("Los Angeles", PT, "14.55", "22", None, None, None),
    "E071": ("Los Angeles", FT, "15.10", "40", "remote", None, "Los Angeles"),
    "E047": ("Los Angeles", CON, "14.00", "20", None, None, None),
    "E078": ("Chicago", PT, "15.20", "24", "hybrid", "Los Angeles", None),
    "E080": ("Chicago", FT, "14.80", "44", None, None, None),
    "E068": ("Chicago", FT, "15.00", "45", None, None, "Los Angeles"),
}


@pytest.fixture(scope="module")
def real():
    return load_employees()


def write(tmp_path, *lines, header=HEADER):
    p = tmp_path / "employees.csv"
    p.write_text("\n".join([header, *lines]) + "\n", encoding="utf-8")
    return p


def test_all_80_rows_load_without_problems(real):
    assert real.problems == []
    assert len(real.employees) == 80
    assert len({e.employee_id for e in real.employees}) == 80


def test_exactly_three_jurisdictions(real):
    cfg = load_config()
    assert len(cfg["jurisdictions"]) == 3
    assert {e.jurisdiction for e in real.employees} == set(cfg["jurisdictions"])


@pytest.mark.parametrize("eid", EDGE)
def test_edge_case_employee_loads_with_expected_values(real, eid):
    juris, etype, wage, hours, arrangement, secondary, residence = EDGE[eid]
    emp = next(e for e in real.employees if e.employee_id == eid)
    assert emp.jurisdiction == juris
    assert emp.employment_type == EmploymentType(etype)
    assert emp.hourly_wage == Decimal(wage)
    assert emp.weekly_hours == Decimal(hours)
    if arrangement:
        assert emp.work_arrangement == arrangement
    if arrangement == "hybrid":
        assert emp.secondary_jurisdiction == secondary
    if residence:
        assert emp.residence_jurisdiction == residence


def test_clean_file_has_no_problems(tmp_path):
    result = load_employees(write(tmp_path, GOOD))
    assert result.ok and len(result.employees) == 1


def test_missing_required_column_is_reported(tmp_path):
    header = "employee_id,jurisdiction,hourly_wage,employment_type"
    result = load_employees(write(tmp_path, "E1,New York City,17.00,hourly_full_time", header=header))
    assert [p.column for p in result.problems] == ["weekly_hours"]
    assert result.problems[0].row is None


def test_duplicate_id_is_reported_and_both_rows_kept(tmp_path):
    result = load_employees(write(tmp_path, GOOD, GOOD))
    assert len(result.employees) == 2
    assert [(p.row, p.column) for p in result.problems] == [(3, "employee_id")]


def test_unknown_jurisdiction_is_reported_and_row_kept(tmp_path):
    result = load_employees(write(tmp_path, "E1,Narnia,17.00,40,hourly_full_time,remote,New York City,,Narnia"))
    assert len(result.employees) == 1
    assert [(p.row, p.employee_id, p.column) for p in result.problems] == [(2, "E1", "jurisdiction")]


def test_negative_wage_is_reported_and_row_kept(tmp_path):
    result = load_employees(write(tmp_path, "E1,New York City,-1.00,40,hourly_full_time,onsite,New York City,,New York City"))
    assert len(result.employees) == 1
    assert [p.column for p in result.problems] == ["hourly_wage"]


def test_remote_residence_differing_from_jurisdiction_is_reported(tmp_path):
    result = load_employees(write(tmp_path, "E1,New York City,17.00,40,hourly_full_time,remote,Chicago,,Los Angeles"))
    assert [p.column for p in result.problems] == ["residence_jurisdiction"]


def test_secondary_jurisdiction_on_onsite_row_is_reported(tmp_path):
    result = load_employees(write(tmp_path, "E1,New York City,17.00,40,hourly_full_time,onsite,New York City,Los Angeles,New York City"))
    assert [p.column for p in result.problems] == ["secondary_jurisdiction"]


def test_zero_hours_and_unknown_type_are_reported(tmp_path):
    result = load_employees(write(tmp_path,
                                  "E1,New York City,17.00,0,hourly_full_time,onsite,New York City,,New York City",
                                  "E2,New York City,17.00,40,intern,onsite,New York City,,New York City"))
    assert [(p.row, p.column) for p in result.problems] == [(2, "weekly_hours"), (3, "employment_type")]


def test_without_location_columns_no_location_checks(tmp_path):
    header = "employee_id,jurisdiction,hourly_wage,weekly_hours,employment_type"
    result = load_employees(write(tmp_path, "E1,New York City,17.00,40,hourly_full_time", header=header))
    assert result.ok
