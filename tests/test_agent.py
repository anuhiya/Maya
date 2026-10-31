"""Agent loop on a scripted planner, replayed AI, a temp site and database, a mocked Federal Register (A2, A4)."""
import json
import shutil
from decimal import Decimal
from pathlib import Path

import pytest

from maya import agent, db, site
from maya.ai import prompts
from maya.ai.llm import LLM, LLMError, Reply, prompt_hash
from maya.ai.schemas import RunSummary
from maya.models import ImpactResult, LogTag
from maya.split import read_sections

ROOT = Path(__file__).resolve().parent.parent
FLOW = ["watch_sources", "fetch_document", "split_sections", "read_sections", "check_answers",
        "match_employees", "price_changes", "route_findings", "search_federal_register", "finish"]
FR = {"results": [{"title": "Minimum wage rule", "publication_date": "2026-10-01", "html_url": "https://x/1"}]}


class Scripted(list):
    def next(self, messages, tools):
        if not self:
            raise LLMError("script ended")
        return self.pop(0)


def flow(n):
    each = [(name, {"plan": name, "change": f"c{i}"}) for name in FLOW[1:4] for i in range(1, n + 1)]
    return [("watch_sources", {"plan": "look"})] + each + [(name, {"plan": name}) for name in FLOW[4:]]


class ReplayLLM(LLM):
    def call(self, kind, system, user, **kw):
        if kind != "run_summary":
            return super().call(kind, system, user, **kw)
        reply = Reply(kind, RunSummary(summary=self.summary), system, user, "{}", "replay", "stub", replayed=True)
        self.records.append({"kind": kind, "model": "stub", "replayed": True})
        return reply


def record(kind, system, user, reply):
    return {"kind": kind, "prompt_hash": prompt_hash(system, user), "reply": json.dumps(reply),
            "provider": "groq", "model": "m"}


def v3_records(root):
    find = lambda path: next(s for s in read_sections(root / path) if s.number == "3.1")  # noqa: E731
    old, new = find("data/policy_site/gov_rules_v2.txt"), find("data/policy_site/_unpublished/gov_rules_v3.txt")
    read = lambda section, value, date: record("read_section", *prompts.read_section(section), {  # noqa: E731
        "section": "3.1", "title": "Minimum Wage", "jurisdiction": "Meridian", "effective_date": date,
        "value": value, "unit": "dollars per hour", "day_type": None, "obligation": "shall",
        "category": "wages", "date_quote": f"Effective Date: {date}",
        "rule_quote": f"Every employer shall pay each covered employee a wage of not less than ${value} per hour for all hours worked."})
    return [read(old, "13.75", "January 1, 2026"), read(new, "15.00", "January 1, 2027"),
            record("compare_section", *prompts.compare_section(old, new), {
                "change_type": "substantive", "facts_changed": ["value", "date"], "reason": "Rose to 15.00."})]


@pytest.fixture
def env(tmp_path):
    shutil.copytree(ROOT / "data", tmp_path / "data", ignore=shutil.ignore_patterns("replays", "uploads"))
    (tmp_path / "data/replays").mkdir()
    shutil.copy(ROOT / "maya.config.yaml", tmp_path / "maya.config.yaml")
    cfg = site.load_config(tmp_path / "maya.config.yaml")
    saved = json.loads((ROOT / "tests/fixtures/ai/main_pair.json").read_text())["records"]
    (tmp_path / "data/replays/run.json").write_text(json.dumps({"records": saved + v3_records(tmp_path)}))
    return cfg, db.connect(tmp_path / "maya.db")


def run(env, steps, get=lambda url, params: FR, summary="Compared the documents."):
    cfg, conn = env
    llm = ReplayLLM(cfg=cfg, env={"MAYA_LLM_PROVIDER": "replay", "MAYA_REPLAY_RUN": "run"})
    llm.summary = summary
    return agent.Agent(cfg, Scripted(steps), llm, conn, federal_register_get=get).run()


def test_first_run_gives_the_nine_findings(env):
    result = run(env, flow(2))
    assert result.status == "finished" and len(result.findings) == 9
    assert (result.in_effect, result.coming) == (Decimal("273.19"), Decimal("142.80"))
    assert sum(r.ready for r in result.routes.values()) == 3
    assert {line.tag for line in result.log} == set(LogTag)
    assert len(db.list_runs(env[1])[0]["log"]) == len(result.log)  # saved to agent_runs


def test_published_version_changes_only_meridian(env):
    run(env, flow(2))
    again = [(name, {"plan": "p"}) for name in ("watch_sources", "search_federal_register", "finish")]
    assert run(env, again).findings == []  # nothing new: sources skipped
    assert "gov_rules_v3.txt" in agent.publish_next_version(env[0])
    result = run(env, flow(1))
    assert [(f.section, f.jurisdiction) for f in result.findings] == [("3.1", "Meridian")]
    assert sum(r.result is ImpactResult.AFFECTED for r in result.rows) == 6
    assert (result.in_effect, result.coming) == (Decimal("0.00"), Decimal("98.65"))


def test_refused_step_logs_a_failed_check(env):
    steps = [("watch_sources", {"plan": "a"}), ("price_changes", {"plan": "too early"}),
             ("watch_sources", {"plan": "again"}), ("approve", {"plan": "no such tool"}), ("fetch_document", {})]
    log = run(env, steps).log
    refused = [line.text for line in log if line.tag is LogTag.CHECK and "Refused" in line.text]
    assert len(refused) == 4 and "no change is ready" in refused[0] and "needs a plan" in refused[3]


def test_federal_register_never_reaches_employees_or_cost(env):
    with_fr, cfg = run(env, flow(2)), env[0]
    site.reset(cfg)
    without = run((cfg, db.connect(cfg["_root"] / "maya.db")), flow(2), get=lambda url, params: {"results": []})
    assert len(with_fr.informational) == 1 and not without.informational
    assert with_fr.rows == without.rows and with_fr.in_effect == without.in_effect
    assert all("Minimum wage rule" not in f.model_dump_json() for f in with_fr.findings)


def test_summary_claiming_approval_is_replaced(env):
    result = run(env, flow(2), summary="All 9 findings were approved.")
    assert "approved" not in result.summary and "pending" in result.summary
    assert any(line.tag is LogTag.CHECK and "replaced" in line.text for line in result.log)


def test_saved_run_completes_offline_with_the_saved_federal_register(tmp_path, monkeypatch):
    """The saved demo run needs no network: nine findings, and the Federal Register items stay informational."""
    shutil.copytree(ROOT / "data", tmp_path / "data", ignore=shutil.ignore_patterns("uploads"))
    shutil.copy(ROOT / "maya.config.yaml", tmp_path / "maya.config.yaml")
    cfg = site.load_config(tmp_path / "maya.config.yaml")

    def blocked(*args, **kwargs):
        raise AssertionError("network used")

    monkeypatch.setattr("socket.socket.connect", blocked)
    monkeypatch.setattr("maya.sources._get", blocked)
    llm = LLM(cfg=cfg, env={"MAYA_LLM_PROVIDER": "replay", "MAYA_REPLAY_RUN": "agent_demo"})
    result = agent.Agent(cfg, agent.LLMPlanner(llm), llm, db.connect(tmp_path / "maya.db")).run()
    saved = json.loads((ROOT / "data/replays/agent_demo.json").read_text(encoding="utf-8"))["federal_register"]
    assert result.status == "finished" and len(result.findings) == 9
    assert [(i.title, i.date, i.url) for i in result.informational] == [(i["title"], i["date"], i["url"]) for i in saved]
    assert (result.in_effect, result.coming) == (Decimal("273.19"), Decimal("142.80"))  # items add no cost
    informational = [l for l in result.log if l.text.startswith("Informational:")]
    assert len(informational) == 5 and all(l.replayed for l in informational)
