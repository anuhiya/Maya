"""Proposed law (A9): code numbers equal the hand values in docs/expected.md, totals stay separate (V1, V4)."""
import shutil
from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest
from streamlit.testing.v1 import AppTest

from maya import scenario
from maya.employees import load_employees
from maya.site import load_config

ROOT = Path(__file__).resolve().parent.parent
HAND = {  # worked out by hand in docs/expected.md ("Proposed law scenario")
    "E025": "33.00", "E030": "12.96", "E034": "60.00", "E037": "60.00", "E039": "57.00",
    "E042": "71.25", "E044": "60.00", "E046": "30.00", "E071": "60.00", "E076": "48.00"}
EXPECTED = ROOT / "docs" / "expected.md"


def temp_cfg(tmp_path, bills=True):
    shutil.copytree(ROOT / "data", tmp_path / "data", ignore=shutil.ignore_patterns("replays", "uploads", "_fetched"))
    shutil.copy(ROOT / "maya.config.yaml", tmp_path / "maya.config.yaml")
    if not bills:
        shutil.rmtree(tmp_path / "data/policies/proposed")
    return load_config(tmp_path / "maya.config.yaml")


@pytest.fixture
def sc(tmp_path):
    cfg = temp_cfg(tmp_path)
    bill = scenario.load_bill(scenario.list_bills(cfg)[0], cfg)
    return scenario.compute(cfg, bill, date(2026, 11, 2))


def test_bill_facts_come_from_the_document(sc):
    b = sc.bill
    assert (b.jurisdiction, b.effective_date, b.new_value, b.section, b.title) == (
        "Los Angeles", "July 1, 2027", Decimal("17.00"), "1.1", "Minimum Wage")
    assert b.trusted and len(b.fingerprint) == 64 and b.source_file == "data/policies/proposed/proposed_bill_v1.txt"
    assert b.stage == "Proposed, not enacted" and sc.timing.value == "future"


def test_code_numbers_equal_the_hand_values(sc):
    assert {r.employee_id: str(r.weekly_increase) for r in sc.affected} == HAND
    assert (sc.weekly, sc.yearly) == (Decimal("492.21"), Decimal("25594.92"))
    assert (sc.tax_weekly, sc.tax_yearly) == (Decimal("37.65"), Decimal("1958.01"))
    assert (sc.total_weekly, sc.total_yearly) == (Decimal("529.86"), Decimal("27552.93"))
    assert sc.by_jurisdiction == {"Los Angeles": 10}
    written = EXPECTED.read_text()
    for text in ("$492.21 a week", "$25,594.92", "$37.65 a week", "$1,958.01", "$529.86 a week", "$27,552.93"):
        assert text in written


def test_the_wage_after_existing_changes_avoids_counting_the_coming_total_twice(tmp_path):
    cfg = temp_cfg(tmp_path)
    bill = scenario.load_bill(scenario.list_bills(cfg)[0], cfg)
    after = scenario.compute(cfg, bill, date(2026, 11, 2))
    assert after.baseline.value == Decimal("15.50") and after.baseline.effective_date == "January 1, 2027"
    assert after.wage_now["E042"] == Decimal("14.50") and after.wage_after["E042"] == Decimal("15.50")
    assert after.wage_after["E076"] == Decimal("15.80")  # already above, unchanged
    no_baseline = scenario.compute(cfg, bill, date(2026, 11, 2))
    no_baseline.baseline = None
    employees = load_employees(cfg=cfg).employees
    from maya.impact import match_finding
    from maya.models import ImpactResult
    raw = match_finding(_finding(bill), employees, cfg)
    from_today = sum((r.weekly_increase for r in raw if r.result is ImpactResult.AFFECTED), Decimal("0.00"))
    assert from_today == Decimal("635.01") and from_today - after.weekly == Decimal("142.80")  # the coming total


def _finding(bill):
    from maya.models import Category, ChangeType, Finding, Timing
    return Finding(finding_id="x", section=bill.section, jurisdiction=bill.jurisdiction, category=Category.WAGES,
                   change_type=ChangeType.SUBSTANTIVE, new_value=bill.new_value, unit="dollars per hour",
                   effective_date=bill.effective_date, timing=Timing.FUTURE, source_file="x")


def test_hybrid_and_contractor_rules(sc):
    ids = {r.employee_id for r in sc.affected}
    assert "E076" in ids and "E078" not in ids  # E076 works in Los Angeles; E078 only part of the week
    review = {r.employee_id: r for r in sc.review}
    assert set(review) == {"E078"} and review["E078"].calculation.endswith("1.80 x 24 h = $43.20")
    assert [r.employee_id for r in sc.flags] == ["E047"]
    assert sc.weekly == sum(r.weekly_increase for r in sc.affected)  # review and flagged rows are never in a total


def test_what_to_prepare_is_derived_from_the_bill_and_the_numbers(sc):
    items = scenario.prepare_list(sc)
    assert "rate table to $17.00 from July 1, 2027" in items[0]
    assert "10 affected Los Angeles employees" in items[1] and "July 1, 2027 in payroll" in items[2]
    assert "$529.86 a week ($27,552.93 a year)" in items[3]
    assert any("E078" in i for i in items) and any("E047" in i for i in items)


def test_quotes_are_verified_word_for_word_and_bad_numbers_are_replaced(sc):
    text = sc.bill.text
    quote = "Every employer shall pay each covered employee a wage of not less than $17.00 per hour for all hours worked."
    checked = dict(scenario.verify_quotes(text, [quote, "Every employer shall pay $99.00.", "  "]))
    assert checked[quote] and not checked["Every employer shall pay $99.00."] and not checked["  "]
    allowed = scenario.facts(sc)
    assert scenario.summary_problem("It sets $17.00 from July 1, 2027 for 10 employees.", allowed, text) is None
    assert "number 99" in scenario.summary_problem("It costs $99 a week.", allowed, text)
    assert "approved" in scenario.summary_problem("The bill is approved.", allowed, text)

    class Fake:
        def call(self, kind, system, user, role="reader"):
            assert kind == "scenario_summary" and "Facts calculated by code" in user
            return SimpleNamespace(answer=SimpleNamespace(
                summary="The bill would raise the Los Angeles minimum to $17.00.", quotes=[quote, "A sentence the bill never says."]))

    result = scenario.ai_summary(Fake(), sc)
    assert result["verified"] == [quote] and result["flagged"] == ["A sentence the bill never says."] and not result["replaced"]

    class Wrong(Fake):
        def call(self, *a, **k):
            return SimpleNamespace(answer=SimpleNamespace(summary="It will cost $12345 a week.", quotes=[]))

    replaced = scenario.ai_summary(Wrong(), sc)
    assert replaced["replaced"] and replaced["text"] == scenario.built_summary(sc) and "12345" not in replaced["text"]


def test_csv_and_markdown_exports_carry_the_numbers_and_the_separate_totals_line(sc):
    csv_text = scenario.scenario_csv(sc)
    assert "E042,affected,14.50,15.50,17.00,45,71.25" in csv_text and "total_weekly,492.21" in csv_text
    assert "E078,needs_review" in csv_text and "E047" in csv_text and scenario.TOTALS_NOTE in csv_text
    md_text = scenario.scenario_markdown(sc, {"text": "A summary.", "verified": ["q"], "flagged": ["bad"]}, "my note")
    assert "Proposed, not yet law." in md_text and "$529.86 a week, $27,552.93 a year" in md_text
    assert scenario.AI_LABEL in md_text and "Reviewer note: my note" in md_text and "Needs reviewer input" in md_text
    assert "Not shown as a quote" in md_text


# ---- the page ---------------------------------------------------------------------------------

def page(cfg):
    from maya.ui import proposed_law, style
    style.inject_css()
    proposed_law.render(cfg=cfg)


def shown(at):
    return " ".join([m.value for m in at.markdown] + [i.value for i in at.info] + [c.value for c in at.caption]
                    + [e.value for e in at.error] + [w.value for w in at.warning])


def test_page_with_the_bill_has_every_section_and_keeps_totals_apart(tmp_path):
    cfg = temp_cfg(tmp_path)
    at = AppTest.from_function(page, kwargs={"cfg": cfg}, default_timeout=60).run()
    at.radio(key="bill_kind").set_value("Illustrative bill").run()
    assert not at.exception
    body = shown(at).replace("&#36;", "$")
    for word in ("Proposed law", "Illustrative bill", "What a proposed bill would do", "Proposed, not yet law", "As of 2026-11-02",
                 "Proposed bill HB-2026-117", "Los Angeles", "July 1, 2027", "proposed_bill_v1.txt", "Trusted source",
                 "If it is enacted", "If it is not enacted", "$492.21", "$37.65", "$529.86", "$27,552.93",
                 "Wage after existing changes", "Upper bound $43.20, not in totals", "Classification flag",
                 "Needs reviewer input", "What to prepare", scenario.AI_LABEL, scenario.TOTALS_NOTE, "$0.00"):
        assert word in body, word
    assert "$273.19" not in body and "$142.80" not in body and "$635.01" not in body  # never mixed in
    assert at.text_area(key=[t.key for t in at.text_area][0]) is not None
    assert [b.proto.label for b in at.get("download_button")] == ["Download scenario (CSV)", "Download scenario summary (Markdown)"]
    assert len([c for c in at.checkbox if c.key.startswith("prep_")]) >= 6


def test_page_with_no_bill_shows_the_empty_state(tmp_path):
    cfg = temp_cfg(tmp_path, bills=False)
    at = AppTest.from_function(page, kwargs={"cfg": cfg}, default_timeout=60).run()
    assert not at.exception and any("No proposed bill found" in i.value for i in at.info)


def test_page_shows_an_error_for_an_unreadable_bill_and_a_selector_for_two(tmp_path):
    cfg = temp_cfg(tmp_path)
    folder = cfg["_root"] / "data/policies/proposed"
    (folder / "a_bad_bill.txt").write_text("no numbered sections here\n")
    at = AppTest.from_function(page, kwargs={"cfg": cfg}, default_timeout=60).run()
    at.radio(key="bill_kind").set_value("Illustrative bill").run()
    assert at.selectbox(key="bill_file") is not None  # two bills now
    at.selectbox(key="bill_file").select_index(0).run()
    assert any("Could not read a_bad_bill.txt" in e.value for e in at.error)
    at.selectbox(key="bill_file").select_index(1).run()
    assert not at.exception and "Proposed bill HB-2026-117" in shown(at)


def test_a_bill_is_a_document_stage_not_a_review_status():
    from maya.models import Status
    assert {s.value for s in Status} == {"pending", "approved", "dismissed"}
    app_text = (ROOT / "app.py").read_text()
    order = [app_text.index(f'"{name}"') for name in ("employee-impact", "proposed-law", "review-history")]
    assert order == sorted(order)


# ---- real proposed bills (A9) -------------------------------------------------------------------

REAL_HAND = {  # worked out by hand in docs/expected.md ("Real proposed bills")
    "E001": "75.25", "E002": "70.00", "E004": "70.00", "E012": "27.60", "E013": "52.50", "E014": "91.00",
    "E015": "35.00", "E017": "66.50", "E018": "0.76", "E020": "70.00", "E021": "83.13", "E024": "70.00",
    "E073": "70.00", "E077": "56.00", "E079": "70.00"}


def real(tmp_path, name):
    cfg = temp_cfg(tmp_path)
    return cfg, scenario.load_real_bill(scenario.real_dir(cfg) / name, cfg)


def test_real_bill_files_are_saved_with_a_header_and_every_fact_is_quoted_from_the_text(tmp_path):
    cfg = temp_cfg(tmp_path)
    folders = scenario.list_real_bills(cfg)
    assert [f.name for f in folders] == ["int_0757_2026", "la_initiative_2026", "a6086_2025"]  # config places first
    for folder in folders:
        rb = scenario.load_real_bill(folder, cfg)
        h = rb.header
        assert h["trust"] == "informational only" and h["date_retrieved"] == "2026-11-01"
        assert h["official_url"].startswith(("https://legistar.council.nyc.gov/", "https://www.nysenate.gov/", "https://clerk.lacity.gov/"))
        assert h["bill_number"] and h["title"] and h["sponsor"] and h["status_as_of_retrieval"]
        assert (folder / h["original_file"]).is_file() and len(rb.fingerprint) == 64
        assert rb.quotes and all(ok for _, ok in rb.quotes)  # V1: every quote is in the saved text


def test_a_fact_whose_quote_is_not_in_the_saved_text_is_flagged(tmp_path):
    import json
    cfg, rb = real(tmp_path, "int_0757_2026")
    facts_path = rb.folder / "facts.json"
    facts = json.loads(facts_path.read_text())
    facts["rule"]["quote"] = "On or after January 1, 2027, $99 an hour;"
    facts_path.write_text(json.dumps(facts))
    bad = scenario.load_real_bill(rb.folder, cfg)
    assert [q for q, ok in bad.quotes if not ok] == ["On or after January 1, 2027, $99 an hour;"]


def test_nyc_int_0757_numbers_equal_the_hand_values(tmp_path):
    cfg, rb = real(tmp_path, "int_0757_2026")
    assert rb.applicable and rb.bill.kind == "real" and rb.bill.jurisdiction == "New York City"
    assert (rb.bill.new_value, rb.bill.effective_date) == (Decimal("19.00"), "January 1, 2027")
    sc = scenario.compute(cfg, rb.bill, date(2026, 11, 2))
    assert {r.employee_id: str(r.weekly_increase) for r in sc.affected} == REAL_HAND
    assert sc.baseline.value == Decimal("17.25") and sc.timing.value == "future"
    assert (sc.weekly, sc.yearly) == (Decimal("907.74"), Decimal("47202.48"))
    assert (sc.tax_weekly, sc.tax_yearly) == (Decimal("69.44"), Decimal("3610.99"))
    assert (sc.total_weekly, sc.total_yearly) == (Decimal("977.18"), Decimal("50813.47"))
    assert sc.by_jurisdiction == {"New York City": 15}
    assert {r.employee_id: r.calculation.endswith("3.20 x 40 h = $128.00") for r in sc.review} == {"E076": True}
    assert [r.employee_id for r in sc.flags] == ["E023"]
    written = EXPECTED.read_text()
    for text in ("$907.74 a week", "$47,202.48", "$69.44 a week", "$3,610.99", "$977.18 a week", "$50,813.47", "$128.00"):
        assert text in written


def test_real_bill_totals_are_separate_from_the_main_totals(tmp_path):
    cfg, rb = real(tmp_path, "int_0757_2026")
    sc = scenario.compute(cfg, rb.bill, date(2026, 11, 2))
    csv_text = scenario.scenario_csv(sc)
    assert "total_weekly,907.74" in csv_text and scenario.TOTALS_NOTE in csv_text
    md_text = scenario.scenario_markdown(sc, None, "")
    assert "Real bill:" in md_text and "legistar.council.nyc.gov" in md_text and "Retrieved: 2026-11-01" in md_text
    assert "Bill text is real; the workforce is synthetic; status may have changed since retrieval." in md_text


def test_state_bill_that_covers_other_places_is_not_applicable_and_has_no_cost(tmp_path):
    cfg, rb = real(tmp_path, "a6086_2025")
    assert not rb.applicable and rb.bill is None
    assert rb.scope == "outside the city of New York and the counties of Nassau, Suffolk, and Westchester"
    assert rb.header["status_as_of_retrieval"].startswith("In Assembly Committee")


def test_ai_summary_quotes_are_verified_against_the_saved_real_text(tmp_path):
    cfg, rb = real(tmp_path, "int_0757_2026")
    sc = scenario.compute(cfg, rb.bill, date(2026, 11, 2))
    real_sentence = "This local law takes effect 180 days after it becomes law."

    class Fake:
        def call(self, kind, system, user, role="reader"):
            assert "Establishment of the minimum wage" in user or "establishment of the minimum wage" in user
            return SimpleNamespace(answer=SimpleNamespace(summary="The bill would set $19.00 from January 1, 2027.",
                                                          quotes=[real_sentence, "The council abolishes tipping."]))

    out = scenario.ai_summary(Fake(), sc)
    assert out["verified"] == [real_sentence] and out["flagged"] == ["The council abolishes tipping."]


def test_page_shows_the_real_bill_with_official_link_and_the_honest_line(tmp_path):
    cfg = temp_cfg(tmp_path)
    at = AppTest.from_function(page, kwargs={"cfg": cfg}, default_timeout=60).run()
    assert not at.exception and at.radio(key="bill_kind").value == "Real proposed bills"
    at.selectbox(key="real_bill").select_index(0).run()
    body = shown(at).replace("&#36;", "$")
    for word in ("Real bill", "Int 0757-2026", "Sandy Nurse", "https://legistar.council.nyc.gov/LegislationDetail.aspx",
                 "2026-11-01", "Committee. Last action: Referred to Comm by Council", "Informational only",
                 "5 of 5 quotes found word for word", "Bill text is real; the workforce is synthetic; status may have changed since retrieval.",
                 "If it is enacted", "If it is not enacted", "$907.74", "$977.18", "$50,813.47", "Upper bound $128.00, not in totals",
                 "Needs reviewer input", "Schedule 2", scenario.AI_LABEL, scenario.TOTALS_NOTE):
        assert word in body, word
    assert "$273.19" not in body and "$142.80" not in body


def test_page_shows_the_not_applicable_state_instead_of_a_cost(tmp_path):
    cfg = temp_cfg(tmp_path)
    at = AppTest.from_function(page, kwargs={"cfg": cfg}, default_timeout=60).run()
    at.selectbox(key="real_bill").select_index(2).run()
    body = shown(at)
    assert "Not applicable to this company, covers: outside the city of New York and the counties of Nassau, Suffolk, and Westchester" in body
    assert "If it is enacted" not in body and "Weekly cost" not in body and "No cost is calculated" in body
    assert not at.exception and not at.get("download_button")


def test_page_without_real_bills_shows_only_the_illustrative_bill(tmp_path):
    cfg = temp_cfg(tmp_path)
    shutil.rmtree(cfg["_root"] / "data/policies/proposed/real")
    at = AppTest.from_function(page, kwargs={"cfg": cfg}, default_timeout=60).run()
    assert not at.exception and not at.radio and "Illustrative bill" in shown(at)


def test_an_incomplete_real_bill_folder_is_an_error_not_a_crash(tmp_path):
    cfg = temp_cfg(tmp_path)
    (cfg["_root"] / "data/policies/proposed/real/int_0757_2026/facts.json").unlink()
    at = AppTest.from_function(page, kwargs={"cfg": cfg}, default_timeout=60).run()
    at.selectbox(key="real_bill").select("int_0757_2026").run()
    assert not at.exception and any("Could not read int_0757_2026" in e.value for e in at.error)


LA_HAND = {
    "E025": "209.00", "E026": "389.48", "E027": "30.36", "E028": "43.84", "E030": "108.96", "E033": "129.48",
    "E034": "380.00", "E035": "53.20", "E036": "223.88", "E037": "380.00", "E039": "361.00", "E040": "32.80",
    "E041": "141.38", "E042": "451.25", "E043": "27.60", "E044": "380.00", "E045": "207.20", "E046": "190.00",
    "E071": "380.00", "E076": "368.00"}


def test_la_initiative_numbers_equal_the_hand_values_and_the_date_is_unknown(tmp_path):
    cfg, rb = real(tmp_path, "la_initiative_2026")
    assert rb.applicable and rb.bill.jurisdiction == "Los Angeles" and rb.bill.new_value == Decimal("25.00")
    assert rb.bill.effective_date == "Not stated in the saved text" and all(ok for _, ok in rb.quotes)
    sc = scenario.compute(cfg, rb.bill, date(2026, 11, 2))
    assert {r.employee_id: str(r.weekly_increase) for r in sc.affected} == LA_HAND
    assert sc.timing.value == "unknown" and sc.baseline.value == Decimal("15.50")
    assert (sc.weekly, sc.yearly) == (Decimal("4487.43"), Decimal("233346.36"))
    assert (sc.tax_weekly, sc.tax_yearly) == (Decimal("343.29"), Decimal("17851.00"))
    assert (sc.total_weekly, sc.total_yearly) == (Decimal("4830.72"), Decimal("251197.36"))
    assert [r.calculation.endswith("9.80 x 24 h = $235.20") for r in sc.review] == [True] and [r.employee_id for r in sc.flags] == ["E047"]
    written = EXPECTED.read_text()
    for text in ("$4,487.43 a week", "$233,346.36", "$343.29 a week", "$17,851.00", "$4,830.72 a week", "$251,197.36", "$235.20"):
        assert text in written
    assert any("no effective date is stated" in i for i in scenario.prepare_list(sc))


def test_the_selector_shows_readable_labels_not_file_names(tmp_path):
    cfg = temp_cfg(tmp_path)
    labels = [scenario.real_label(f) for f in scenario.list_real_bills(cfg)]
    assert labels[0] == "New York City, Int 0757-2026, Establishment of the minimum wage"
    assert labels[1].startswith("Los Angeles, LA initiative 2026 (Olympic Wage), ")
    assert labels[2].startswith("New York State, A6086 (2025-2026 session), ")
    at = AppTest.from_function(page, kwargs={"cfg": cfg}, default_timeout=60).run()
    assert at.selectbox(key="real_bill").options == labels and not any("_" in o and "int_" in o for o in labels)


def test_a_bill_is_not_applicable_when_it_covers_no_place_the_company_has(tmp_path):
    import json
    cfg, rb = real(tmp_path, "int_0757_2026")
    facts = json.loads((rb.folder / "facts.json").read_text())
    facts["covers_jurisdictions"] = ["Houston"]
    (rb.folder / "facts.json").write_text(json.dumps(facts))
    assert not scenario.load_real_bill(rb.folder, cfg).applicable


def test_la_page_shows_unknown_date_and_the_official_status(tmp_path):
    cfg = temp_cfg(tmp_path)
    at = AppTest.from_function(page, kwargs={"cfg": cfg}, default_timeout=60).run()
    at.selectbox(key="real_bill").select_index(1).run()
    body = shown(at).replace("&#36;", "$")
    for word in ("Los Angeles", "Approved for Circulation on 1/21/2026", "https://clerk.lacity.gov/elections", "$4,487.43",
                 "$4,830.72", "Not stated in the saved text", "Upper bound $235.20, not in totals", "4 of 4 quotes found word for word"):
        assert word in body, word
