"""Agent activity page on the saved run, a temp copy of the data and database, no network (A2, A4, B1)."""
import html
import json
import re
import shutil
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from maya.site import load_config

ROOT = Path(__file__).resolve().parent.parent
def no_network(url, params):
    raise AssertionError("the saved run must not touch the network")


def first_saved_title():
    saved = json.loads((ROOT / "data/replays/agent_demo.json").read_text(encoding="utf-8"))
    return saved["federal_register"][0]["title"]


def page(cfg):
    from maya.ui import agent_activity, style
    style.inject_css()
    agent_activity.render(cfg=cfg)


@pytest.fixture
def cfg(tmp_path, monkeypatch):
    shutil.copytree(ROOT / "data", tmp_path / "data", ignore=shutil.ignore_patterns("uploads"))
    shutil.copy(ROOT / "maya.config.yaml", tmp_path / "maya.config.yaml")
    monkeypatch.setattr("maya.sources._get", no_network)
    monkeypatch.setattr("maya.ui.agent_activity._has_key", lambda cfg: False)
    cfg = load_config(tmp_path / "maya.config.yaml")
    cfg["ui"] = {**cfg["ui"], "replay_line_delay": 0}
    return cfg


def start(cfg):
    at = AppTest.from_function(page, kwargs={"cfg": cfg}, default_timeout=60)
    at.run()
    assert not at.exception
    return at


def text(at):
    parts = [m.value for m in at.markdown] + [e.value for e in at.error] + [i.value for i in at.info]
    parts += [w.value for w in at.warning] + [s.value for s in at.success] + [c.value for c in at.caption]
    return "\n".join(parts)


def run_saved(cfg):
    at = start(cfg)
    at.button(key="run_agent").click().run()
    assert not at.exception
    return at


def test_empty_page_shows_goal_tools_guardrails_and_saved_run_on(cfg):
    at = start(cfg)
    body = text(at)
    assert at.checkbox(key="use_saved").value is True
    assert "Find what changed since the approved version" in body
    assert "search_federal_register" in body and "Ready" in body
    assert "AI reads and judges; code checks and calculates; a person decides anything unclear." in body
    assert "No lines yet" in body


def test_saved_run_fills_the_log_and_summary(cfg):
    at = run_saved(cfg)
    body = text(at)
    for tag in ("PLAN", "TOOL", "AI", "CHECK", "RESULT"):
        assert f">{tag}</span>" in body
    assert "replayed from saved run" in body
    assert "Finished" in body and "9 findings" in body
    assert "informational only" in body.lower() and html.escape(first_saved_title()) in body
    assert "$273.19" in body.replace("&#36;", "$")


def test_second_run_says_sources_unchanged(cfg):
    at = run_saved(cfg)
    at.button(key="run_agent").click().run()
    assert any("All sources unchanged since the last run" in i.value for i in at.info)


def test_live_mode_without_key_names_the_setting(cfg, monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setattr("maya.ai.llm._secrets", lambda path: {})
    at = start(cfg)
    at.checkbox(key="use_saved").uncheck().run()
    at.button(key="run_agent").click().run()
    assert any("GROQ_API_KEY" in e.value for e in at.error)


def test_start_over_asks_first_and_cancel_keeps_the_database(cfg):
    db_file = cfg["_root"] / cfg["state"]["database"]
    at = run_saved(cfg)
    assert db_file.exists()
    at.button(key="start_over").click().run()
    assert any("clears the database" in w.value for w in at.warning) and db_file.exists()
    at.button(key="confirm_no").click().run()
    assert db_file.exists() and not at.warning


def test_start_over_confirmed_clears_database(cfg):
    db_file = cfg["_root"] / cfg["state"]["database"]
    at = run_saved(cfg)
    at.button(key="start_over").click().run()
    at.button(key="confirm_yes").click().run()
    assert not db_file.exists() and any("Demo reset" in s.value for s in at.success)


def test_publish_next_version_once_then_none_left(cfg):
    at = start(cfg)
    at.button(key="publish").click().run()
    assert any("gov_rules_v3.txt" in s.value for s in at.success)
    at.button(key="publish").click().run()
    assert any("No held-back version" in i.value for i in at.info)


def test_page_text_has_no_forbidden_characters(cfg):
    body = text(run_saved(cfg))
    assert not re.search("[\u2014\u00a7\u00b7]", body) and "rule A1" not in body


def test_uploaded_pair_is_listed_first_in_the_review_queue(cfg):
    def uploaded_page(cfg):
        import streamlit as st
        from maya.ui import review_queue
        from maya.ui.review_queue import Pair
        st.session_state["upload_pair"] = Pair("x", cfg["_root"] / "a_v1.txt", cfg["_root"] / "a_v2.txt")
        st.session_state["upload_count"] = 2
        st.write([p.label for p in review_queue.policy_pairs(cfg)][0])

    at = AppTest.from_function(uploaded_page, kwargs={"cfg": cfg}, default_timeout=30)
    at.run()
    assert not at.exception
    assert at.markdown[0].value.startswith("Uploaded:") and "(2 findings)" in at.markdown[0].value


def test_log_times_show_in_the_configured_zone(cfg):
    from datetime import datetime, timezone
    from maya.ui.agent_activity import local_time
    assert local_time(datetime(2026, 10, 30, 17, 42, 46, tzinfo=timezone.utc), cfg["ui"]) == "13:42:46 ET"
    assert re.search(r"\d\d:\d\d:\d\d ET", text(run_saved(cfg)))
