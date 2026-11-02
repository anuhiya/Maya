"""The empty demo: reset --empty, clean empty pages, and findings that appear after the first run (A4)."""
import importlib.util
import json
import shutil
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from maya import db, runner, site, state

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("reset_demo", ROOT / "scripts" / "reset_demo.py")
reset_demo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reset_demo)


@pytest.fixture(autouse=True)
def clean_runner():
    runner.clear()
    yield
    runner.clear()


@pytest.fixture
def cfg(tmp_path):
    shutil.copytree(ROOT / "data", tmp_path / "data", ignore=shutil.ignore_patterns("uploads", "_fetched"))
    shutil.copy(ROOT / "maya.config.yaml", tmp_path / "maya.config.yaml")
    cfg = site.load_config(tmp_path / "maya.config.yaml")
    cfg["site"]["server"]["enabled"] = False
    cfg["ui"] = {**cfg["ui"], "replay_line_delay": 0}
    return cfg


def snapshot(folder: Path) -> dict:
    return {str(p.relative_to(folder)): p.read_bytes() for p in sorted(folder.rglob("*")) if p.is_file()}


def dirty(cfg):
    """A demo that has been used: v3 published, a custom version, a stored run and a review decision."""
    site.publish_next(cfg)
    conn = db.connect(cfg["_root"] / cfg["state"]["database"])
    from maya.models import Decision, Status
    db.add_decision(conn, Decision(finding_id="abc", status=Status.APPROVED, comment="ok", decided_at=db.utcnow(), decided_by="P"))
    db.save_run(conn, goal="g", log=[], started_at=db.utcnow(), exchanges=[], summary="s")
    conn.close()
    (cfg["_root"] / "data/uploads").mkdir(exist_ok=True)
    (cfg["_root"] / "data/uploads/a.txt").write_text("x")


def test_reset_empty_clears_state_and_keeps_the_rest(cfg):
    root = cfg["_root"]
    keep = {k: v for k, v in snapshot(root / "data").items() if k.startswith(("replays/", "employees", "company_policies/", "policies/"))}
    dirty(cfg)
    assert reset_demo.main(["--yes", "--empty"], cfg) == 0
    assert not (root / cfg["state"]["database"]).exists() and not (root / "data/uploads").exists()
    assert state.marker(cfg).exists() and state.is_empty(cfg)
    index = json.loads((root / "data/policy_site/index.json").read_text())["documents"]
    assert [d["version"] for d in index] == [1, 2]
    assert (root / "data/policy_site/_unpublished/gov_rules_v3.txt").exists()
    assert not (root / "data/policy_site/gov_rules_v3.txt").exists()
    after = snapshot(root / "data")
    assert all(after[k] == v for k, v in keep.items())  # replays, employees and policies are untouched
    assert sorted(p.name for p in (root / "data/replays").glob("*.json")) == ["agent_demo.json", "main_pair.json", "smoke_v2_read.json"]


def test_default_reset_is_unchanged_and_clears_the_marker(cfg):
    dirty(cfg)
    state.set_empty(cfg)
    assert reset_demo.main(["--yes"], cfg) == 0
    assert not state.marker(cfg).exists() and not state.is_empty(cfg)
    assert not (cfg["_root"] / cfg["state"]["database"]).exists()
    assert reset_demo.main([], cfg) == 1  # nothing without --yes


def test_the_marker_alone_does_not_empty_a_demo_that_has_run(cfg):
    state.set_empty(cfg)
    assert state.is_empty(cfg)
    conn = db.connect(cfg["_root"] / cfg["state"]["database"])
    db.save_run(conn, goal="g", log=[], started_at=db.utcnow(), exchanges=[], summary="s")
    conn.close()
    assert not state.is_empty(cfg)


def page(cfg, name):
    from maya.ui import employee_impact, export, proposed_law, review_history, review_queue, style
    style.inject_css()
    {"queue": review_queue, "impact": employee_impact, "history": review_history, "proposed": proposed_law,
     "export": export}[name].render(cfg=cfg)


@pytest.mark.parametrize("name, kicker", [("queue", "Review queue"), ("impact", "Employee impact"),
                                          ("history", "Review history"), ("proposed", "Proposed law"),
                                          ("export", "Export")])
def test_every_findings_page_shows_one_clean_line_when_empty(cfg, name, kicker):
    state.set_empty(cfg)
    at = AppTest.from_function(page, kwargs={"cfg": cfg, "name": name}, default_timeout=60).run()
    assert not at.exception and not at.error and not at.warning
    assert [i.value for i in at.info] == ["No findings yet. Open Agent activity and run the agent."]
    body = " ".join(m.value for m in at.markdown if "<style>" not in m.value)
    assert kicker in body and "mq-card" not in body and "mq-table" not in body and "$0.00" not in body
    assert not at.get("download_button") and not at.get("button")


def test_pages_fill_in_after_the_first_saved_run_and_the_agent_page_offers_both_runs(cfg):
    state.set_empty(cfg)

    def agent_page(cfg):
        from maya.ui import agent_activity, style
        style.inject_css()
        agent_activity.render(cfg=cfg)

    at = AppTest.from_function(agent_page, kwargs={"cfg": cfg}, default_timeout=60).run()
    assert not at.exception
    saved = at.checkbox(key="use_saved")
    assert saved.value is True or saved.set_value(True)
    at.checkbox(key="use_saved").set_value(False).run()
    assert at.button(key="run_agent").label == "Run agent" and any("Live run" in c.value for c in at.caption)
    at.checkbox(key="use_saved").set_value(True).run()
    assert at.button(key="run_agent").label == "Load saved run" and any("Saved run (replay)" in c.value for c in at.caption)
    at.button(key="run_agent").click().run()
    runner.current().join(60)
    at.run()
    assert not state.is_empty(cfg) and state.run_count(cfg) == 1  # the saved run filled the empty database
    queue = AppTest.from_function(page, kwargs={"cfg": cfg, "name": "queue"}, default_timeout=60).run()
    assert not queue.exception and not any("No findings yet" in i.value for i in queue.info)
    assert [m for m in queue.markdown if "mq-card" in m.value]


def test_findings_come_from_the_agents_saved_answers_when_no_replay_file_covers_them(cfg, monkeypatch):
    """A live run leaves its AI answers in the database; the queue reads findings from them, with no second model call."""
    from maya.ui import review_queue
    records = json.loads((cfg["_root"] / "data/replays/main_pair.json").read_text())["records"]
    shutil.rmtree(cfg["_root"] / "data/replays")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setattr("maya.ai.llm._secrets", lambda path: {})
    pair = review_queue.policy_pairs(cfg)[0]
    with pytest.raises(Exception, match="No saved run covers"):
        review_queue._compare(cfg, pair)
    conn = db.connect(cfg["_root"] / cfg["state"]["database"])
    db.save_run(conn, goal="g", log=[], started_at=db.utcnow(), exchanges=records, summary="s")
    conn.close()
    comparison = review_queue._compare(cfg, pair)
    assert len(comparison.result.findings) == 9


def test_all_changes_pair_appears_once_a_third_version_is_published(cfg):
    from maya.ui import review_queue
    assert not [p for p in review_queue.policy_pairs(cfg) if p.label.endswith("(all changes)")]
    site.publish_next(cfg)
    pairs = review_queue.policy_pairs(cfg)
    assert pairs[-1].label == "Payroll Standards Bulletin PSB-2026-01 to PSB-2026-03 (all changes)"
    assert (pairs[-1].old.name, pairs[-1].new.name) == ("gov_rules_v1.txt", "gov_rules_v3.txt")
