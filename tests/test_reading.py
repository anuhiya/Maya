"""Reading and splitting policy files (B1)."""
from pathlib import Path

import pytest

from maya.ingest import ReadingError, normalise, read_document
from maya.split import read_sections, rule_text, split_sections

ROOT = Path(__file__).resolve().parent.parent
V1 = ROOT / "data/policies/gov_rules_v1"
V2 = ROOT / "data/policies/gov_rules_v2"
COMPANY = ROOT / "data/company_policies/company_pay_policy"

BLANK_PDF = (
    b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
    b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]>>endobj\n"
    b"trailer<</Root 1 0 R>>\n%%EOF\n"
)


def by_number(sections):
    return {s.number: s for s in sections}


def test_section_counts():
    assert len(read_sections(V1.with_suffix(".txt"))) == 9
    assert len(read_sections(V2.with_suffix(".txt"))) == 10
    assert len(read_sections(COMPANY.parent / "company_pay_policy_v2.txt")) == 6


def test_company_pdf_matches_txt():
    pdf = read_sections(COMPANY.with_suffix(".pdf"))
    assert len(pdf) == 6
    assert pdf == read_sections(COMPANY.parent / "company_pay_policy_v2.txt")


def test_v2_txt_and_pdf_identical():
    assert read_sections(V2.with_suffix(".txt")) == read_sections(V2.with_suffix(".pdf"))


def test_missing_effective_date_is_none():
    s = by_number(read_sections(V2.with_suffix(".txt")))["2.3"]
    assert s.effective_date is None
    assert s.jurisdiction == "Calder"


def test_date_kept_as_written():
    s = by_number(read_sections(V2.with_suffix(".txt")))
    assert s["3.3"].effective_date == "To be determined"
    assert s["1.1"].effective_date == "November 1, 2026"
    assert s["1.1"].title == "Minimum Wage"
    assert s["1.1"].jurisdiction == "Avalon"


def test_front_matter_skipped():
    first = read_sections(V2.with_suffix(".txt"))[0]
    assert first.number == "1.1"
    assert "Commonwealth" not in first.text


def test_rule_text():
    s = by_number(read_sections(V2.with_suffix(".pdf")))["1.1"]
    assert rule_text(s) == ("Every employer shall pay each covered employee a wage of not less "
                            "than $17.25 per hour for all hours worked.")


def test_no_sections_raises(tmp_path):
    f = tmp_path / "plain.txt"
    f.write_text("Just a paragraph.\nNothing numbered here.\n", encoding="utf-8")
    with pytest.raises(ReadingError, match="no numbered sections"):
        read_sections(f)


def test_pdf_without_text_raises(tmp_path):
    f = tmp_path / "scan.pdf"
    f.write_bytes(BLANK_PDF)
    with pytest.raises(ReadingError):
        read_document(f)


def test_normalise():
    assert normalise("It’s  a “wage”") == "It's a \"wage\""
    assert normalise("pay-\nment due") == "payment due"
    assert normalise("one-half rate") == "one-half rate"


def test_split_without_config_names():
    text = "1.1 Wage\nJurisdiction: Zed\nEffective Date: May 1\nPay it."
    s = split_sections(text)[0]
    assert (s.jurisdiction, s.effective_date) == ("Zed", "May 1")
