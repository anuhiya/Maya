"""Agent activity page on the saved run, a temp copy of the data and database, no network (A2, A4, B1)."""
import html
import json
import re
import shutil
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from maya import runner
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


@pytest.fixture(autouse=True)
def clean_runner():
    runner.clear()
    yield
    runner.clear()


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
    active = runner.current()
    if active:
        active.join(60)  # the agent runs on a background worker
    at.run()
    assert not at.exception
    return at


def test_empty_page_shows_goal_tools_guardrails_and_saved_run_on(cfg):
    at = start(cfg)
    body = text(at)
    assert at.checkbox(key="use_saved").value is True
    assert "Find what changed since the approved version" in body
    assert "search_federal_register" in body and "Ready" in body
    assert "Rules calculate every dollar. The model reads only synthetic policy text. A person approves every action." in body
    assert "No lines yet" in body and "Live AI work" in body and "Waiting for a run." in body
    assert [b.label for b in at.button if b.key.startswith("nodebtn_")] == [
        "Fetch site", "Split sections", "Read with AI", "Check V1 to V3", "Match employees", "Price", "Route"]


def test_saved_run_fills_the_log_and_summary(cfg):
    at = run_saved(cfg)
    body = text(at)
    for tag in ("PLAN", "TOOL", "AI", "CHECK", "RESULT"):
        assert f">{tag}</span>" in body
    assert "replayed from saved run" in body
    assert "Finished" in body and "9 findings" in body
    assert "informational only" in body.lower() and "No relevant items found." in body
    assert html.escape(first_saved_title()) not in body  # an unrelated saved title is not shown
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


def test_preset_button_publishes_a_custom_version_and_start_over_removes_it(cfg):
    at = start(cfg)
    next(b for b in at.button if b.key == "custom_preset_2").click().run()
    assert not at.exception and "gov_rules_custom_v4.txt" in at.success[0].value
    assert (cfg["_root"] / "data/policy_site/gov_rules_custom_v4.pdf").exists()
    at.button(key="start_over").click().run()
    at.button(key="confirm_yes").click().run()
    assert not list((cfg["_root"] / "data/policy_site").glob("*custom*"))


def test_saved_run_fills_the_pipeline_cards_and_audit_log(cfg):
    at = run_saved(cfg)
    body = text(at)
    for word in ("Calculated by code, not AI", "AI answer", "Routing", "Who did what", "Run ribbon"):
        assert word in body
    assert any(e.label == "Audit log" for e in at.expander) and re.search(r"Step (\d+) of \1: Finish", body)
    assert "AI read" in body and "code calculated" in body and "a person decides" in body
    assert at.button(key="nodebtn_read") is not None
    assert [m for m in at.markdown if "mq-state done" in m.value]


def test_back_and_next_walk_through_the_recorded_steps_and_skip_returns_to_the_end(cfg):
    at = run_saved(cfg)
    last = at.session_state["view_index"] if "view_index" in at.session_state else None
    assert last is None
    at.button(key="back_step").click().run()
    assert at.session_state["view_index"] is not None
    at.button(key="back_step").click().run()
    step_two = at.session_state["view_index"]
    at.button(key="next_step").click().run()
    assert at.session_state["view_index"] == step_two + 1
    at.button(key="skip_end").click().run()
    assert at.session_state["view_index"] is None and not at.exception


def test_clicking_a_node_shows_its_details_and_a_dot_picks_a_finding(cfg):
    at = run_saved(cfg)
    at.button(key="nodebtn_check").click().run()
    assert any("Step details: Check V1 to V3" in m.value for m in at.markdown)
    dots = [b for b in at.button if b.key.startswith("dot_")]
    assert len(dots) == 9
    dots[0].click().run()
    assert at.session_state["ribbon_pick"] in {b.key[4:] for b in dots}


def test_ribbon_dots_are_numbered_coloured_by_route_and_carry_the_section_title(cfg):
    at = run_saved(cfg)
    dots = [b for b in at.button if b.key.startswith("dot_")]
    assert [b.label for b in dots] == [str(n) for n in range(1, 10)]
    assert all(b.help and b.help.startswith("Section ") and " a week" in b.help for b in dots)
    assert any("Section 1.1 Minimum Wage, New York City" in b.help for b in dots)
    lanes = {b.key for b in at.get("button")}  # container keys carry the route colour class
    body = text(at)
    assert "Running totals: in effect" in body and '<b class="mono">&#36;273.19</b>' in body
    assert '<b class="mono">&#36;142.80</b>' in body


def test_publish_card_is_compact(cfg):
    at = start(cfg)
    from maya.ui import agent_activity
    assert len(agent_activity.CUSTOM_HELP) < 220 and "\n" not in agent_activity.CUSTOM_HELP
    assert at.text_input(key="custom_value").placeholder == "$17.25"
    presets = [b for b in at.button if b.key.startswith("custom_preset_")]
    assert len(presets) == 5
    assert any("Publish a change" in m.value for m in at.markdown)
