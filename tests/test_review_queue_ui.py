"""Review queue page on the saved main-pair run, a temp database, no network (B2, B4, B5, B6, A3)."""
import html
import re

import pytest
from streamlit.testing.v1 import AppTest

from maya import db
from maya.models import Status
from maya.site import load_config


def page(cfg):
    from maya.ui import review_queue, style
    style.inject_css()
    review_queue.render(cfg=cfg)


@pytest.fixture
def cfg(tmp_path):
    import streamlit as st
    st.cache_data.clear()
    cfg = load_config()
    cfg["state"] = {"database": str(tmp_path / "test.db")}
    cfg["llm"] = {**cfg["llm"], "replay_dir": "tests/fixtures/ai"}
    return cfg


def run(cfg, **kw):
    at = AppTest.from_function(page, kwargs={"cfg": cfg}, default_timeout=30)
    at.run()
    assert not at.exception
    return at


def text(at):
    parts = [m.value for m in at.markdown] + [e.value for e in at.error] + [i.value for i in at.info]
    return "\n".join(parts)


def card_values(at):
    return [html.unescape(v) for v in re.findall(r'class="value[^"]*">([^<]+)<', text(at))]


def test_main_pair_cards_match_expected(cfg):
    at = run(cfg)
    assert card_values(at) == ["9", "5", "3", "$273.19", "$142.80"]


def test_as_of_2027_moves_future_into_effect(cfg):
    at = run(cfg)
    at.date_input(key="as_of").set_value("2027-01-01").run()
    assert not at.exception
    values = card_values(at)
    assert values[3] == "$415.99" and values[4] == "$0.00"


def test_dismiss_needs_a_comment(cfg):
    at = run(cfg)
    at.text_input(key="reviewer").set_value("Pavan").run()
    at.radio[0].set_value("Dismiss")
    at.get("form_submit_button")[0].click().run()
    assert any("comment is required" in e.value for e in at.error)
    conn = db.connect(cfg["state"]["database"])
    assert db.history(conn) == []


def test_sign_off_approves_exactly_the_ready_three(cfg):
    at = run(cfg)
    at.text_input(key="reviewer").set_value("Pavan").run()
    at.button(key="signoff").click().run()
    assert not at.exception
    conn = db.connect(cfg["state"]["database"])
    decisions = db.history(conn)
    assert len(decisions) == 3
    assert {d.status for d in decisions} == {Status.APPROVED}
    assert card_values(at)[2] == "0"


def test_identical_pair_shows_no_changes_message(cfg):
    at = run(cfg)
    pairs = at.selectbox(key="pair")
    company = next(o for o in pairs.options if "company" in o.lower())
    pairs.select(company).run()
    assert not at.exception
    assert any("No changes detected: 6 of 6 sections identical. 0 findings, $0.00." in i.value for i in at.info)


def test_copy_rules(cfg):
    at = run(cfg)
    shown = text(at)
    for banned in ("rule A1", "\u00a7", "\u00b7", "\u2014", "Auto-approve"):
        assert banned not in shown


def test_as_of_has_no_widget_warning_and_keeps_value(cfg):
    at = run(cfg)
    assert not at.warning
    at.date_input(key="as_of").set_value("2027-01-01").run()
    assert str(at.session_state["as_of"]) == "2027-01-01" and not at.warning
