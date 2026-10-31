"""Review history page on a temp database (B6)."""
import html

import pytest
from streamlit.testing.v1 import AppTest

from maya import db, routing
from maya.models import Status
from maya.site import load_config


def page(cfg):
    from maya.ui import review_history, style
    style.inject_css()
    review_history.render(cfg=cfg)


@pytest.fixture
def cfg(tmp_path):
    import streamlit as st
    st.cache_data.clear()
    cfg = load_config()
    cfg["state"] = {"database": str(tmp_path / "test.db")}
    cfg["llm"] = {**cfg["llm"], "replay_dir": "tests/fixtures/ai"}
    return cfg


def run(cfg):
    at = AppTest.from_function(page, kwargs={"cfg": cfg}, default_timeout=30)
    at.run()
    assert not at.exception
    return at


def text(at):
    return html.unescape("\n".join(m.value for m in [*at.markdown, *at.info, *at.caption]))


def decide(cfg, fid, status, who, comment=""):
    conn = db.connect(cfg["state"]["database"])
    routing.decide(conn, fid, status, who, comment)
    conn.close()


def test_empty_state(cfg):
    at = run(cfg)
    assert any("No decisions yet" in i.value for i in at.info)


def test_newest_first_in_eastern_time_with_labels(cfg):
    decide(cfg, "aaaaaaaaaaaa", Status.APPROVED, "Pavan", "older note")
    decide(cfg, "aaaaaaaaaaaa", Status.DISMISSED, "Anu", "newer note")
    at = run(cfg)
    shown = text(at)
    assert shown.index("newer note") < shown.index("older note")
    assert " ET" in shown and "UTC" not in shown
    assert "Dismissed" in shown and "Anu" in shown


def test_no_edit_or_delete_controls(cfg):
    decide(cfg, "aaaaaaaaaaaa", Status.APPROVED, "Pavan")
    at = run(cfg)
    labels = [b.label.lower() for b in at.button]
    assert not any(w in l for l in labels for w in ("edit", "delete", "remove"))
    assert "append-only" in text(at)


def test_filters_by_finding_and_status(cfg):
    decide(cfg, "aaaaaaaaaaaa", Status.APPROVED, "Pavan", "alpha note")
    decide(cfg, "bbbbbbbbbbbb", Status.DISMISSED, "Anu", "beta note")
    at = run(cfg)
    at.selectbox(key="h_finding").select("bbbbbbbbbbbb").run()
    assert "beta note" in text(at) and "alpha note" not in text(at)
    at.button(key="clear_h").click().run()
    at.selectbox(key="h_status").select("Approved").run()
    assert "alpha note" in text(at) and "beta note" not in text(at)
    at.selectbox(key="h_status").select("Pending").run()
    assert any("No decisions match" in i.value for i in at.info)


def test_known_finding_is_labelled(cfg):
    from maya.ai.llm import LLM
    from maya.pipeline import compare_documents
    entry = next(iter(cfg["policies"].values()))
    llm = LLM(cfg=cfg, env={"MAYA_LLM_PROVIDER": "replay", "MAYA_REPLAY_RUN": "main_pair"})
    result = compare_documents(cfg["_root"] / entry["old"], cfg["_root"] / entry["new"], llm=llm, cfg=cfg)
    wage = next(f for f in result.findings if f.section == "1.1")
    decide(cfg, wage.finding_id, Status.APPROVED, "Pavan", "ok")
    assert "Section 1.1 Avalon" in text(run(cfg))
