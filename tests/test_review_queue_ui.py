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
    parts += [c.value for c in at.caption]
    return html.unescape("\n".join(parts))


def card_values(at):
    return [html.unescape(v) for v in re.findall(r'class="value[^"]*">([^<]+)<', text(at))]


def test_main_pair_cards_match_expected(cfg):
    at = run(cfg)
    assert card_values(at) == ["9", "5", "3", "$273.19"]
    assert "Coming: $142.80, not added to in effect" in text(at)


def test_as_of_2027_moves_future_into_effect(cfg):
    at = run(cfg)
    at.date_input(key="as_of").set_value("2027-01-01").run()
    assert not at.exception
    values = card_values(at)
    assert values[3] == "$415.99" and "Coming: $0.00, not added to in effect" in text(at)


def test_dismiss_needs_a_comment(cfg):
    at = run(cfg)
    at.text_input(key="reviewer").set_value("Pavan").run()
    at.get("form_submit_button")[1].click().run()  # Dismiss with no comment
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


def test_impact_caption_counts_only_own_jurisdiction(cfg):
    captions = [c.value for c in run(cfg).caption if "employees checked" in c.value]
    assert captions == ["28 New York City employees checked: 10 affected, 12 not affected, 6 excluded. "
                        "Also listed for review: 1 hybrid employee working part of the week here."]


def test_default_mode_is_pre_approve_with_the_sign_off_button(cfg):
    at = run(cfg)
    assert at.toggle(key="auto_approve").value is False
    assert at.button(key="signoff") is not None
    assert db.history(db.connect(cfg["state"]["database"])) == []


def test_auto_approve_mode_approves_the_ready_three_and_hides_sign_off(cfg):
    at = run(cfg)
    at.toggle(key="auto_approve").set_value(True).run()
    assert not at.exception
    decisions = db.history(db.connect(cfg["state"]["database"]))
    assert len(decisions) == 3
    assert {(d.status, d.decided_by) for d in decisions} == {(Status.APPROVED, "Auto-approved")}
    assert not at.get("button") or all(b.key != "signoff" for b in at.button)
    assert card_values(at)[2] == "0"
    at.toggle(key="auto_approve").set_value(False).run()
    assert len(db.history(db.connect(cfg["state"]["database"]))) == 3  # switching back undoes nothing


def test_new_layout_has_the_fixed_card_order_and_review_order(cfg):
    at = run(cfg)
    shown = text(at)
    order = ["Previous rule and updated rule", "Financial impact", "Recommended action",
             "Why it was routed this way", "Evidence from the source", "Reviewer decision"]
    positions = [shown.index(h) for h in order]
    assert positions == sorted(positions)
    assert (shown.index("Review order") < shown.index("Ready to approve (") < shown.index("Needs decision (")
            < shown.index("Wording only or no action ("))
    assert "Reviewing as: not set" in shown and "of 9 checked by hand" in shown
    assert any(b.label == "Add comment" for b in at.get("form_submit_button"))


def test_review_order_is_sorted_by_weekly_dollars(cfg):
    at = run(cfg)
    labels = [b.label for b in at.button if b.key and b.key.startswith("pick_")]
    ranks = {m[2]: int(m[1]) for m in (re.match(r"(\d+)\. Section (\d\.\d)", x) for x in labels) if m}
    assert ranks["1.1"] == 1 and sorted(ranks.values()) == list(range(1, 10))  # New York City minimum wage is the largest


def test_ranks_count_down_the_list_in_group_order(cfg):
    at = run(cfg)
    labels = [b.label for b in at.button if b.key and b.key.startswith("pick_")]
    numbers = [int(re.match(r"(\d+)\.", x).group(1)) for x in labels]
    assert numbers == list(range(1, 10))  # 1 to 9 from the top, Ready first
    body = text(at)
    assert body.index("Ready to approve (3)") < body.index("Needs decision (5)") < body.index("Wording only or no action (1)")


def test_decision_buttons_wait_for_a_reviewer_name(cfg):
    at = run(cfg)
    labels = {b.label: b for b in at.get("form_submit_button")}
    assert set(labels) == {"Approve", "Dismiss", "Add comment"} and all(b.disabled for b in labels.values())
    assert any("Enter your name in Review settings to decide" in c.value for c in at.caption)
    at.text_input(key="reviewer").set_value("Pavan").run()
    assert not any(b.disabled for b in at.get("form_submit_button"))
    assert not any("Enter your name in Review settings to decide" in c.value for c in at.caption)


def test_calculation_column_is_wide_and_selection_look_is_off():
    from maya.ui import style
    assert re.search(r"\.mq-table td\.calc[^{]*\{[^}]*min-width: 26rem", style.CSS)
    assert "user-select: none" in style.CSS and 'stFormSubmitButton"] button { white-space: nowrap' in style.CSS
