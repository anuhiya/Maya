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
        "section": "3.1", "title": "Minimum Wage", "jurisdiction": "Chicago", "effective_date": date,
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


def test_published_version_changes_only_chicago(env):
    run(env, flow(2))
    again = [(name, {"plan": "p"}) for name in ("watch_sources", "search_federal_register", "finish")]
    assert run(env, again).findings == []  # nothing new: sources skipped
    assert "gov_rules_v3.txt" in agent.publish_next_version(env[0])
    result = run(env, flow(1))
    assert [(f.section, f.jurisdiction) for f in result.findings] == [("3.1", "Chicago")]
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
    cfg["site"]["server"]["enabled"] = False  # this test blocks every socket, so it reads the folder directly

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
    # none of the five saved titles names a wage or payroll term, so the log shows none of them
    assert not [l for l in result.log if l.text.startswith("Informational:")]
    assert any(l.text.startswith("No relevant items found.") and l.replayed for l in result.log)


# ---- custom changes (B8): scripted planner, mocked AI, code matches and prices ------------------------

import re  # noqa: E402
from datetime import date, timedelta  # noqa: E402

from maya.models import FlagName, Timing  # noqa: E402
from maya.split import rule_text  # noqa: E402

CATEGORY = {"minimum_wage": ("wages", "dollars per hour"), "filing_deadline": ("filing_deadline", "days"),
            "wording_only": ("wages", "dollars per hour")}


def custom_records(root, done, change_type):
    """What a correct reader would answer for the one changed section (old and new) and the comparison."""
    find = lambda name: next(s for s in read_sections(root / "data/policy_site" / name) if s.number == done.section)  # noqa: E731
    old, new = find("gov_rules_v2.txt"), find(done.files[0])
    category, unit = CATEGORY[change_type]

    def read(section):
        date_text = section.effective_date or "missing"
        return record("read_section", *prompts.read_section(section), {
            "section": section.number, "title": section.title, "jurisdiction": section.jurisdiction,
            "effective_date": date_text, "value": re.search(r"\d+(?:\.\d+)?", rule_text(section)).group(0),
            "unit": unit, "day_type": "calendar" if unit == "days" else None, "obligation": None,
            "category": category, "rule_quote": rule_text(section),
            "date_quote": f"Effective Date: {date_text}" if section.effective_date else None})

    wording = change_type == "wording_only"
    changed = [] if wording else ["value"] + (["date"] if old.effective_date != new.effective_date else [])
    return [read(old), read(new), record("compare_section", *prompts.compare_section(old, new), {
        "change_type": "wording_only" if wording else "substantive", "facts_changed": changed,
        "reason": "Reworded." if wording else "Changed."})]


def run_custom(env, i):
    cfg, _ = env
    run(env, flow(2))  # the two published versions first
    preset = cfg["site"]["presets"][i]
    offset = preset.get("date_offset_days")
    when = None if offset is None else date.fromisoformat(cfg["as_of_date"]) + timedelta(days=offset)
    done = agent.publish_custom_version(cfg, preset["jurisdiction"], preset["change_type"], preset["value"], when)
    path = cfg["_root"] / "data/replays/run.json"
    saved = json.loads(path.read_text())
    saved["records"] += custom_records(cfg["_root"], done, preset["change_type"])
    path.write_text(json.dumps(saved))
    return done, run(env, flow(1))


@pytest.mark.parametrize("i, section, jurisdiction", [
    (0, "1.1", "New York City"), (1, "2.1", "Los Angeles"), (2, "3.1", "Chicago"), (3, "3.1", "Chicago"),
    (4, "2.2", "Los Angeles")])
def test_each_preset_reaches_exactly_one_finding(env, i, section, jurisdiction):
    _, result = run_custom(env, i)
    assert result.status == "finished"
    assert [(f.section, f.jurisdiction) for f in result.findings] == [(section, jurisdiction)]
    assert all(c.passed for c in result.findings[0].check_results)


def test_custom_wage_change_is_matched_and_priced_by_code(env):
    """New York City minimum to $18.00 from the as-of date. Worked by hand from data/employees.csv:
    E017 earns 16.00 for 38 h: gap 2.00 x 38 h = $76.00. E014 earns 16.83 for 48 h: gap 1.17,
    1.17 x 40 h = 46.80 plus 1.17 x 1.5 x 8 h = 14.04, so $60.84. E003 earns 20.14, above 18.00, so not affected."""
    _, result = run_custom(env, 0)
    rows = {r.employee_id: r for r in result.rows}
    assert result.findings[0].timing is Timing.CURRENT
    assert rows["E017"].result is ImpactResult.AFFECTED and rows["E017"].weekly_increase == Decimal("76.00")
    assert rows["E017"].calculation == "2.00 x 38 h = $76.00"
    assert rows["E014"].weekly_increase == Decimal("60.84")
    assert rows["E003"].result is ImpactResult.NOT_AFFECTED
    affected = [r for r in result.rows if r.result is ImpactResult.AFFECTED]
    assert 0 < len(affected) < sum(r.jurisdiction == "New York City" for r in result.rows)  # only some employees
    assert result.in_effect == sum((r.weekly_increase for r in affected), Decimal("0.00")) and result.coming == 0


def test_future_custom_change_is_kept_apart_from_current(env):
    _, result = run_custom(env, 1)
    assert result.findings[0].timing is Timing.FUTURE
    assert result.in_effect == Decimal("0.00") and result.coming > 0


def test_missing_date_preset_gives_the_missing_date_flag(env):
    _, result = run_custom(env, 2)
    finding = result.findings[0]
    assert FlagName.MISSING_DATE in {f.name for f in finding.flags} and finding.timing is Timing.UNKNOWN
    assert result.routes[finding.finding_id].ready is False


def test_wording_only_and_filing_presets_cost_nothing(env):
    for i in (3, 4):
        cfg = env[0]
        site.reset(cfg)
        _, result = run_custom((cfg, db.connect(cfg["_root"] / "maya.db")), i)
        assert result.in_effect == 0 and result.coming == 0
        assert not any(r.result is ImpactResult.AFFECTED for r in result.rows)


def test_start_over_removes_custom_versions_and_the_saved_replays_still_work(env):
    cfg = env[0]
    run_custom(env, 0)
    agent.start_over(cfg)
    assert not list((cfg["_root"] / "data/policy_site").glob("*custom*"))
    result = run((cfg, db.connect(cfg["_root"] / "maya.db")), flow(2))
    assert len(result.findings) == 9


# ---- planner failures: retries are logged, the fixed order covers a failed model (A2, A4) -------------

class FlakyPlanner:
    """Fails the first `fail` turns with an LLMError, then follows the script."""

    def __init__(self, fail, steps):
        self.fail, self.steps = fail, list(steps)

    def next(self, messages, tools):
        if self.fail:
            self.fail -= 1
            raise LLMError("Groq call for plan failed: Tool call validation failed")
        if not self.steps:
            raise LLMError("script ended")
        return self.steps.pop(0)


def run_flaky(env, planner):
    cfg, conn = env
    llm = ReplayLLM(cfg=cfg, env={"MAYA_LLM_PROVIDER": "replay", "MAYA_REPLAY_RUN": "run"})
    llm.summary = "Compared the documents."
    return agent.Agent(cfg, planner, llm, conn, federal_register_get=lambda url, params: FR).run()


def test_one_failed_planner_turn_is_covered_by_the_fixed_order(env):
    # the model fails on turn 1: code picks watch_sources, then the model carries on from fetch_document
    result = run_flaky(env, FlakyPlanner(1, flow(2)[1:]))
    assert result.status == "finished" and len(result.findings) == 9
    assert (result.in_effect, result.coming) == (Decimal("273.19"), Decimal("142.80"))
    fallback = [l for l in result.log if l.text.startswith("Planner fallback")]
    chosen = [l for l in result.log if l.tag is LogTag.PLAN and "Chosen by code" in l.text]
    assert len(fallback) == 1 and "code chose watch_sources" in fallback[0].text and len(chosen) == 1


def test_fallbacks_are_capped_per_run(env):
    result = run_flaky(env, FlakyPlanner(9, []))
    assert result.status == "stopped"
    assert len([l for l in result.log if l.text.startswith("Planner fallback")]) == 6  # max_planner_fallbacks
    assert any("The planner gave no usable step" in l.text for l in result.log)


def test_fallback_never_approves_anything(env):
    result = run_flaky(env, FlakyPlanner(2, flow(2)[2:]))
    assert result.status == "finished" and "approve" not in agent.TOOLS
    assert not any(l.text.startswith("approve") for l in result.log if l.tag is LogTag.TOOL)


def test_planner_retry_and_rate_limit_waits_are_logged(env):
    cfg, conn = env
    llm = ReplayLLM(cfg=cfg, env={"MAYA_LLM_PROVIDER": "replay", "MAYA_REPLAY_RUN": "run"})
    run_agent = agent.Agent(cfg, Scripted([]), llm, conn)
    llm.on_plan_retry(1, "Tool call validation failed")
    llm.on_wait(7)
    texts = [l.text for l in run_agent.log]
    assert texts[0].startswith("Planner retry 1 of 1") and texts[1] == "Waiting for the model (rate limit): 7 seconds, then retrying."


# ---- Federal Register: only wage and payroll titles are kept (A2) ------------------------------------

def test_relevance_uses_whole_words_from_the_config_terms():
    from maya import sources
    terms = ["wage", "minimum wage", "payroll", "overtime", "wage and hour", "withholding", "unemployment insurance"]
    for title in ("Minimum Wage Increase", "Updating Overtime Rules", "Wage and Hour Division; Rule", "Payroll Tax Rule",
                  "Federal Income Tax Withholding Tables", "Unemployment Insurance Program Letter", "Prevailing Wages"):
        assert sources.relevant(title, terms), title
    for title in ("Sewage Treatment Standards", "Optional Practical Training Fees", "Transparency in Coverage"):
        assert not sources.relevant(title, terms), title


def test_live_search_drops_unrelated_titles_and_says_so_when_nothing_matches(env):
    from maya import sources
    cfg, _ = env
    mixed = {"results": [{"title": "Optional Practical Training Fees", "publication_date": "2026-10-08", "html_url": "https://x/0"},
                         {"title": "Overtime pay for home care workers", "publication_date": "2026-10-01", "html_url": "https://x/1"}]}
    seen = {}

    def get(url, params):
        seen.update(params)
        return mixed

    items, error = sources.search_federal_register(cfg, get)
    assert [i.title for i in items] == ["Overtime pay for home care workers"] and error is None
    assert '"minimum wage"' in seen["conditions[term]"] and " OR " in seen["conditions[term]"]
    none, _ = sources.search_federal_register(cfg, lambda u, p: {"results": [mixed["results"][0]]})
    assert none == []
    result = run(env, flow(2), get=lambda u, p: {"results": [mixed["results"][0]]})
    assert not result.informational
    assert any(l.text.startswith("No relevant items found.") for l in result.log)


# ---- a planner that keeps refusing in one step: the run finishes on the fixed order (A2, A4) -----------

class Groq400(Exception):
    status_code = 400


class FakeGroq:
    """A Groq client that answers planner calls from a queue: an Exception is raised, anything else is a tool call."""

    def __init__(self, *replies):
        self.replies, self.calls = list(replies), []
        from types import SimpleNamespace
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        from types import SimpleNamespace
        self.calls.append(kwargs)
        item = self.replies.pop(0)
        if isinstance(item, Exception):
            raise item
        name, args = item
        call = SimpleNamespace(function=SimpleNamespace(name=name, arguments=json.dumps(args)))
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(tool_calls=[call], content=None))])


def test_a_step_where_the_model_refuses_twice_is_taken_by_code_after_at_most_three_model_calls(env, monkeypatch):
    monkeypatch.setattr("maya.ai.llm.time.sleep", lambda s: None)
    cfg, conn = env
    refusal = Groq400("Error code: 400 - Tool choice is required, but model did not call a tool")
    script = flow(2)
    client = FakeGroq(refusal, refusal, *script[1:])  # step 1: two refusals; the model then takes every later step
    replay = ReplayLLM(cfg=cfg, env={"MAYA_LLM_PROVIDER": "replay", "MAYA_REPLAY_RUN": "run"})
    replay.summary = "Compared the documents."

    class Hybrid(LLM):
        """Planner calls go to the fake Groq client; the AI reading comes from the saved answers."""

        def call(self, kind, system, user, **kw):
            reply = replay.call(kind, system, user, **kw)
            self.records.append(replay.records[-1])
            return reply

    llm = Hybrid(cfg=cfg, env={"GROQ_API_KEY": "k", "MAYA_LLM_PROVIDER": "groq"}, client=client,
                 secrets_path=cfg["_root"] / "none.toml")
    result = agent.Agent(cfg, agent.LLMPlanner(llm), llm, conn, federal_register_get=lambda url, params: FR).run()
    assert result.status == "finished" and len(result.findings) == 9
    assert (result.in_effect, result.coming) == (Decimal("273.19"), Decimal("142.80"))
    fallbacks = [l for l in result.log if l.text.startswith("Planner fallback")]
    assert len(fallbacks) == 1 and "code chose watch_sources" in fallbacks[0].text
    chosen = [l for l in result.log if l.tag is LogTag.PLAN and "Chosen by code, not the model (planner fallback)" in l.text]
    assert len(chosen) == 1
    assert len(client.calls) == 2 + (len(script) - 1)  # the refused step cost exactly two model calls
    assert [c["tool_choice"] for c in client.calls[:2]] == ["required", "auto"]
    assert all(c["tool_choice"] == "auto" for c in client.calls[1:])  # sticky for the rest of the run
