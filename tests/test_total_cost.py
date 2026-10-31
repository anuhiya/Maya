"""Total cost panel and per-employee totals against docs/expected.md (X1, V4)."""
import csv
import io
from datetime import date
from decimal import Decimal

import pytest

from maya import cost, export
from maya.ai.llm import LLM
from maya.employees import load_employees
from maya.impact import match_finding
from maya.pipeline import compare_documents
from maya.site import load_config
from maya.timing import classify

D = Decimal


@pytest.fixture(scope="module")
def data():
    cfg = load_config()
    cfg["llm"] = {**cfg["llm"], "replay_dir": "tests/fixtures/ai"}
    entry = next(iter(cfg["policies"].values()))
    llm = LLM(cfg=cfg, env={"MAYA_LLM_PROVIDER": "replay", "MAYA_REPLAY_RUN": "main_pair"})
    result = compare_documents(cfg["_root"] / entry["old"], cfg["_root"] / entry["new"], llm=llm, cfg=cfg)
    return cfg, result.findings, load_employees(cfg=cfg).employees


def pairs_at(data, as_of):
    cfg, findings, employees = data
    out = []
    for f in findings:
        f = f.model_copy(update={"timing": classify(f.effective_date, as_of)})
        out.append((f, match_finding(f, employees, cfg)))
    return out


def line(panel, start):
    return next(x for x in panel.lines if x.label.startswith(start))


def test_panel_matches_expected(data):
    panel = cost.total_cost(pairs_at(data, date(2026, 11, 2)))
    wages = line(panel, "Wage increases in effect")
    assert (wages.weekly, wages.yearly) == (D("273.19"), D("14205.88"))
    tax = line(panel, "Employer Social Security and Medicare")
    assert tax.weekly == D("20.90")
    assert tax.yearly == D("1086.75")  # from the annualized total, rounded once, not 20.90 x 52
    assert tax.status == "Estimate" and "wage base" in tax.note
    total = line(panel, "Total in effect")
    assert (total.weekly, total.yearly) == (D("294.09"), D("15292.63"))


def test_coming_is_apart_and_not_in_total(data):
    panel = cost.total_cost(pairs_at(data, date(2026, 11, 2)))
    coming = line(panel, "Wage increases coming")
    assert (coming.weekly, coming.yearly) == (D("142.80"), D("7425.60"))
    assert "2027-01-01" in coming.label
    assert line(panel, "Total in effect").weekly == D("294.09")


def test_future_increase_joins_in_effect_on_its_date(data):
    panel = cost.total_cost(pairs_at(data, date(2027, 1, 1)))
    assert line(panel, "Wage increases in effect").weekly == D("415.99")
    assert line(panel, "Wage increases coming").weekly == D("0.00")


def test_uncalculable_lines_are_flagged_with_no_number(data):
    panel = cost.total_cost(pairs_at(data, date(2026, 11, 2)))
    unemployment = line(panel, "Unemployment tax change")
    assert unemployment.weekly is None and unemployment.yearly is None
    assert unemployment.status == "Flagged" and "wage base" in unemployment.note
    back = line(panel, "Back pay")
    assert back.weekly is None and back.yearly is None
    assert back.status == "Needs reviewer input"
    filing = line(panel, "Filing and reporting changes")
    assert filing.weekly == D("0.00")


def test_employee_rows_add_up_to_the_panel(data):
    panel = cost.total_cost(pairs_at(data, date(2026, 11, 2)))
    assert sum(e.now for e in panel.employees) == D("273.19")
    assert sum(e.tax for e in panel.employees) == D("20.90")
    assert sum(e.total for e in panel.employees) == line(panel, "Total in effect").weekly
    assert sum(e.coming for e in panel.employees) == D("142.80")
    assert all(e.total == e.now + e.tax for e in panel.employees)


def test_employee_rows_for_edge_cases(data):
    panel = cost.total_cost(pairs_at(data, date(2026, 11, 2)))
    by_id = {e.employee_id: e for e in panel.employees}
    assert by_id["E001"].now == D("8.17") and "1.1 Avalon" in by_id["E001"].changes
    assert by_id["E025"].now == D("0.00") and by_id["E025"].coming == D("20.90")
    assert "2027-01-01" in by_id["E025"].coming_dates
    assert "E004" not in by_id  # exactly at the minimum
    assert "Classification warning" in by_id["E023"].flags and by_id["E023"].total == D("0.00")
    for hybrid in ("E076", "E078"):  # shown with their flag, never in totals
        assert "Needs review" in by_id[hybrid].flags
        assert by_id[hybrid].now == D("0.00") and by_id[hybrid].coming == D("0.00")


def test_tax_spread_by_largest_remainder():
    shares = cost.spread_tax({"A": D("0.10"), "B": D("0.10"), "C": D("0.10")})
    assert sum(shares.values()) == cost.employer_tax(D("0.30")) == D("0.02")
    assert shares == {"A": D("0.01"), "B": D("0.01"), "C": D("0.00")}  # ties go to the lower ID
    shares = cost.spread_tax({"A": D("8.17"), "B": D("47.50")})
    assert sum(shares.values()) == cost.employer_tax(D("55.67"))


def test_no_increase_means_zero_tax(data):
    assert cost.employer_tax(D("0.00")) == D("0.00")
    assert cost.spread_tax({}) == {}


def test_employee_totals_csv_keeps_required_columns_apart(data):
    panel = cost.total_cost(pairs_at(data, date(2026, 11, 2)))
    text = export.employee_totals_csv(panel.employees)
    rows = list(csv.DictReader(io.StringIO(text)))
    assert tuple(text.splitlines()[0].split(",")) == export.EMPLOYEE_TOTALS_COLUMNS
    assert sum(D(r["employer_tax"]) for r in rows) == D("20.90")
    assert "E+" not in text
