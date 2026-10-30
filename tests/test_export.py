"""CSV exports on the saved main-pair run (B7)."""
import csv
import io
from datetime import date
from decimal import Decimal

import pytest

from maya import db, export, routing
from maya.models import FINDINGS_EXPORT_COLUMNS, IMPACT_EXPORT_COLUMNS, ImpactResult, Status, Timing
from maya.site import load_config
from maya.employees import load_employees
from maya.ai.llm import LLM
from maya.pipeline import compare_documents
from maya.timing import classify
from maya.impact import match_finding


@pytest.fixture
def data(tmp_path):
    cfg = load_config()
    cfg["llm"] = {**cfg["llm"], "replay_dir": "tests/fixtures/ai"}
    pair = policy_pairs_main(cfg)
    llm = LLM(cfg=cfg, env={"MAYA_LLM_PROVIDER": "replay", "MAYA_REPLAY_RUN": "main_pair"})
    result = compare_documents(pair[0], pair[1], llm=llm, cfg=cfg)
    employees = load_employees(cfg=cfg).employees
    conn = db.connect(tmp_path / "t.db")
    return cfg, result.findings, employees, conn


def policy_pairs_main(cfg):
    entry = next(iter(cfg["policies"].values()))
    return cfg["_root"] / entry["old"], cfg["_root"] / entry["new"]


def rows_at(cfg, findings, employees, as_of):
    out = []
    for f in findings:
        f = f.model_copy(update={"timing": classify(f.effective_date, as_of)})
        out += match_finding(f, employees, cfg)
    return out


def parse(text):
    return list(csv.DictReader(io.StringIO(text)))


def total(rows, timing):
    return sum((Decimal(r["weekly_increase"]) for r in rows if r["timing"] == timing.value and r["weekly_increase"]
                and r["result"] == ImpactResult.AFFECTED.value), Decimal("0"))


def test_columns_are_exact(data):
    cfg, findings, employees, conn = data
    f = export.findings_csv(findings, conn)
    i = export.impact_csv(rows_at(cfg, findings, employees, date(2026, 11, 2)))
    assert tuple(f.splitlines()[0].split(",")) == FINDINGS_EXPORT_COLUMNS
    assert tuple(i.splitlines()[0].split(",")) == IMPACT_EXPORT_COLUMNS
    assert len(parse(f)) == 9


def test_impact_totals_match_expected(data):
    cfg, findings, employees, conn = data
    rows = parse(export.impact_csv(rows_at(cfg, findings, employees, date(2026, 11, 2))))
    assert total(rows, Timing.CURRENT) == Decimal("273.19")
    assert total(rows, Timing.FUTURE) == Decimal("142.80")
    later = parse(export.impact_csv(rows_at(cfg, findings, employees, date(2027, 1, 1))))
    assert total(later, Timing.CURRENT) == Decimal("415.99")
    assert total(later, Timing.FUTURE) == Decimal("0")


def test_plain_decimals_no_scientific_notation(data):
    cfg, findings, employees, conn = data
    text = export.impact_csv(rows_at(cfg, findings, employees, date(2026, 11, 2))) + export.findings_csv(findings, conn)
    assert "E+" not in text and "e+" not in text
    assert export._cell(Decimal("1E+2")) == "100"
    assert export._cell(Decimal("0.00")) == "0.00"


def test_decision_appears_in_findings_csv(data):
    cfg, findings, employees, conn = data
    fid = findings[0].finding_id
    routing.decide(conn, fid, Status.DISMISSED, "Pavan", "wrong section")
    row = next(r for r in parse(export.findings_csv(findings, conn)) if r["finding_id"] == fid)
    assert (row["review_status"], row["last_comment"], row["decided_by"]) == ("dismissed", "wrong section", "Pavan")
    assert row["decided_at"].endswith("+00:00")


def test_no_rows_gives_headers_only(data):
    _, _, _, conn = data
    assert export.findings_csv([], conn).strip() == ",".join(FINDINGS_EXPORT_COLUMNS)
    assert export.impact_csv([]).strip() == ",".join(IMPACT_EXPORT_COLUMNS)


def test_file_name_has_as_of_date():
    assert export.file_name("findings", date(2026, 11, 2)) == "maya_findings_2026-11-02.csv"
