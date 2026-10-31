"""Tests for maya/findings.py and maya/pipeline.py on saved replies and a fake client, no network (B1, B2, V1 to V3)."""
import json
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from maya.ai.llm import LLM
from maya.findings import CHECK_FAILED, finding_id
from maya.models import ChangeType, FlagName, Timing
from maya.pipeline import compare_documents
from maya.routing import REASON_UNTRUSTED_OR_FAILED, route
from maya.site import load_config

ROOT = Path(__file__).resolve().parent.parent
CFG = load_config()
JURISDICTIONS = CFG["jurisdictions"]
MAIN = CFG["policies"]["main_pair"]
COMPANY = CFG["policies"]["company_pair"]
OLD_DOC = "1.1 Minimum Wage\nJurisdiction: Avalon\nEffective Date: January 1, 2026\n" \
          "Every employer shall pay each covered employee a wage of not less than $16.00 per hour for all hours worked.\n"
NEW_DOC = OLD_DOC.replace("$16.00", "$17.25").replace("January 1, 2026", "November 1, 2026")


class Client:
    """A fake Groq client: `handler(kind, user)` returns the raw reply text for each call."""

    def __init__(self, handler):
        self.handler = handler
        self.calls = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        system, user = kwargs["messages"][0]["content"], kwargs["messages"][1]["content"]
        kind = "read_section" if system.startswith("You read") else "compare_section"
        self.calls.append((kind, user))
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=self.handler(kind, user)))])


def llm_for(handler):
    client = Client(handler)
    return LLM(cfg=CFG, env={"GROQ_API_KEY": "gsk_test"}, secrets_path=Path("/nonexistent.toml"), client=client), client


def replay_llm():
    cfg = {**CFG, "llm": {**CFG["llm"], "replay_dir": "tests/fixtures/ai"}}
    return LLM(cfg=cfg, env={"MAYA_LLM_PROVIDER": "replay", "MAYA_REPLAY_RUN": "main_pair"},
               secrets_path=Path("/nonexistent.toml"))


def facts(user, value=None):
    """A correct read_section answer for the one-section test documents."""
    old = "$16.00" in user
    value = value or ("16.00" if old else "17.25")
    date = "January 1, 2026" if old else "November 1, 2026"
    return json.dumps({
        "section": "1.1", "title": "Minimum Wage", "jurisdiction": "Avalon", "effective_date": date,
        "value": value, "unit": "dollars per hour", "day_type": None, "obligation": "shall",
        "category": "wages", "date_quote": f"Effective Date: {date}",
        "rule_quote": f"Every employer shall pay each covered employee a wage of not less than ${value} per hour for all hours worked.",
    })


def compare(change_type="substantive", changed=("value", "date")):
    return json.dumps({"change_type": change_type, "facts_changed": list(changed), "reason": "The wage rose."})


def good(kind, user):
    return facts(user) if kind == "read_section" else compare()


@pytest.fixture
def docs(tmp_path):
    old, new = tmp_path / "doc_v1.txt", tmp_path / "doc_v2.txt"
    old.write_text(OLD_DOC, encoding="utf-8")
    new.write_text(NEW_DOC, encoding="utf-8")
    return old, new


@pytest.fixture(scope="module")
def main_result():
    return compare_documents(ROOT / MAIN["old"], ROOT / MAIN["new"], llm=replay_llm(), cfg=CFG)


EXPECTED = {  # section: change type, timing, old value, new value (docs/expected.md)
    "1.1": ("substantive", "current", "16.00", "17.25"),
    "1.2": ("substantive", "future", "2.7", "3.1"),
    "1.3": ("substantive", "future", None, None),
    "1.4": ("added", "future", None, None),
    "2.1": ("substantive", "future", "14.50", "15.50"),
    "2.2": ("substantive", "future", "30", "20"),
    "2.3": ("substantive", "unknown", None, None),
    "3.2": ("wording_only", "current", None, None),
    "3.3": ("substantive", "unknown", "20", "10"),
}


def test_main_pair_gives_the_nine_expected_findings(main_result):
    found = {f.section: f for f in main_result.findings}
    assert sorted(found) == sorted(EXPECTED)
    for number, (change, timing, old, new) in EXPECTED.items():
        f = found[number]
        assert (f.change_type, f.timing) == (ChangeType(change), Timing(timing)), number
        assert f.old_value == (Decimal(old) if old else None) and f.new_value == (Decimal(new) if new else None), number
        assert all(c.passed for c in f.check_results), number
    assert len(main_result.findings) == 9
    assert (main_result.identical, main_result.total) == (1, 10)


def test_main_pair_flags(main_result):
    flags = {f.section: {x.name for x in f.flags} for f in main_result.findings}
    assert flags["1.1"] == flags["1.2"] == flags["2.1"] == flags["2.2"] == set()
    assert FlagName.NEW_WORDING in flags["1.3"] and FlagName.NEW_WORDING in flags["2.3"]
    assert FlagName.MISSING_DATE in flags["2.3"] and FlagName.UNCLEAR_DATE in flags["3.3"]


def test_routing_passes_only_1_1_1_2_2_1(main_result):
    assert main_result.trusted and main_result.source == "Government bulletins"
    ready = {f.section for f in main_result.findings
             if route(f, trusted=main_result.trusted, jurisdictions=JURISDICTIONS).ready}
    assert ready == {"1.1", "1.2", "2.1"}


def test_3_2_is_wording_only_and_3_1_is_identical(main_result):
    found = {f.section: f for f in main_result.findings}
    assert found["3.2"].change_type is ChangeType.WORDING_ONLY
    assert "3.1" not in found


def test_finding_ids_are_stable_and_distinct(main_result):
    again = compare_documents(ROOT / MAIN["old"], ROOT / MAIN["new"], llm=replay_llm(), cfg=CFG)
    ids = [f.finding_id for f in main_result.findings]
    assert ids == [f.finding_id for f in again.findings] and len(set(ids)) == 9
    assert ids[0] == finding_id("regional-dol-payroll-bulletin", "1.1", "wages")


def test_no_change_pair_gives_no_findings_and_no_ai_calls():
    llm, client = llm_for(lambda kind, user: pytest.fail("identical sections must not call the AI"))
    result = compare_documents(ROOT / COMPANY["old"], ROOT / COMPANY["new"], llm=llm, cfg=CFG)
    assert result.findings == [] and result.summary == "6 of 6 sections identical" and client.calls == []


def test_invented_value_is_rejected_after_one_retry(docs):
    llm, client = llm_for(lambda kind, user: facts(user, "18.00") if kind == "read_section" and "$17.25" in user else good(kind, user))
    [finding] = compare_documents(*docs, llm=llm, cfg=CFG).findings
    checks = {c.check: c for c in finding.check_results}
    assert not checks["V1"].passed and "18.00" in checks["V1"].detail
    assert finding.ai_reason == CHECK_FAILED and finding.new_value is None
    assert len(client.calls) == 6  # three calls, one retry
    assert "failed these checks" in client.calls[3][1]


def test_retry_can_recover(docs):
    state = {"n": 0}

    def handler(kind, user):
        state["n"] += 1
        if kind == "read_section" and "$17.25" in user and "failed these checks" not in user:
            return facts(user, "18.00")
        return good(kind, user)

    [finding] = compare_documents(*docs, llm=llm_for(handler)[0], cfg=CFG).findings
    assert finding.new_value == Decimal("17.25") and all(c.passed for c in finding.check_results)


def test_bad_json_is_retried_once_then_routed_to_the_reviewer(tmp_path):
    old, new = tmp_path / "doc_v1.txt", tmp_path / "doc_v2.txt"
    old.write_text(OLD_DOC, encoding="utf-8")
    new.write_text(NEW_DOC, encoding="utf-8")
    llm, client = llm_for(lambda kind, user: "not json")
    result = compare_documents(old, new, llm=llm, cfg=CFG)
    [finding] = result.findings
    assert len(client.calls) == 2 and finding.ai_reason == CHECK_FAILED
    assert not route(finding, trusted=True, jurisdictions=JURISDICTIONS).ready
    assert REASON_UNTRUSTED_OR_FAILED in route(finding, trusted=True, jurisdictions=JURISDICTIONS).reasons


def test_wording_only_is_rejected_when_facts_differ(docs):
    handler = lambda kind, user: facts(user) if kind == "read_section" else compare("wording_only", ())  # noqa: E731
    [finding] = compare_documents(*docs, llm=llm_for(handler)[0], cfg=CFG).findings
    checks = {c.check: c for c in finding.check_results}
    assert not checks["V3"].passed and "wording only is rejected" in checks["V3"].detail
    assert finding.ai_reason == CHECK_FAILED


def test_file_outside_every_source_is_untrusted_and_cannot_auto_approve(docs):
    result = compare_documents(*docs, llm=llm_for(good)[0], cfg=CFG)
    [finding] = result.findings
    assert all(c.passed for c in finding.check_results)  # a clean finding...
    assert result.trusted is False and result.source is None
    r = route(finding, trusted=result.trusted, jurisdictions=JURISDICTIONS)
    assert not r.ready and REASON_UNTRUSTED_OR_FAILED in r.reasons  # ...still goes to a person
    trusted = route(finding, trusted=True, jurisdictions=JURISDICTIONS)
    assert trusted.ready  # the same finding passes once its source is trusted
