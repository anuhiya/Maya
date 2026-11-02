"""Pure pieces of the live agent view (A5): node states, narration and the cards."""
from maya.ui import live_view as lv


def event(n, tool, **kw):
    base = {"n": n, "tool": tool, "change": "c1", "plan": "p", "by_code": False, "result": "ok", "failed": False,
            "refused": False, "changes": [{"id": "c1", "label": "a -> b", "stage": 0, "n_old": 9, "n_new": 10,
                                           "total": 10, "identical": 1, "error": ""}],
            "findings": [], "in_effect": "0.00", "coming": "0.00", "ai_answers": 0, "prices": 0,
            "lanes": {"decision": 0, "ready": 0, "wording": 0}, "finished": False}
    return {**base, **kw}


def finding(**kw):
    base = {"id": "f1", "section": "3.1", "jurisdiction": "Chicago", "category": "wages", "change_type": "substantive",
            "unit": "dollars per hour", "old_value": "13.75", "new_value": "15.00", "effective_date": "January 1, 2027",
            "timing": "future", "old_rule": "old", "new_rule": "Every employer shall pay $15.00.",
            "old_excerpt": "Effective Date: January 1, 2026\nold", "new_excerpt": "Effective Date: January 1, 2027\nEvery employer shall pay $15.00.",
            "source_file": "data/x.txt", "ai_reason": "Rose.", "flags": [], "checks": [
                {"check": "V1", "passed": True, "detail": "ok"}, {"check": "V2", "passed": True, "detail": "ok"},
                {"check": "V3", "passed": True, "detail": "ok"}], "matched": 24, "affected": 6, "weekly": "98.65",
            "calc": "E1: 1.25 x 40 h = $50.00", "lane": "ready", "why": "passed every condition"}
    return {**base, **kw}


def test_node_states_follow_the_steps_and_mark_running_failed_and_done():
    steps = [event(1, "watch_sources"), event(2, "fetch_document"), event(3, "split_sections", failed=True)]
    states = lv.node_states(steps, current=(4, "split_sections", "c1"))
    assert states["fetch"] == "done" and states["split"] == "running" and states["read"] == "waiting"
    assert lv.node_states(steps)["split"] == "failed"
    assert lv.node_states([event(1, "price_changes", refused=True)])["price"] == "waiting"
    assert lv.progress(lv.node_states(steps)) == 1 / 7


def test_narration_reads_like_the_example_and_names_code_chosen_steps():
    assert lv.narration(event(3, "split_sections"), 10) == "Step 3 of 10: Split sections. 9 sections in the old file and 10 in the new."
    assert lv.narration(event(3, "read_sections"), None).startswith("Step 3: Read with AI. 9 of 10 sections changed")
    assert "Chosen by code, not the model" in lv.narration(event(1, "watch_sources", by_code=True), 5)
    assert lv.narration(None, None).startswith("No step yet")


def test_cards_show_labels_ticks_failures_and_the_count_up_number():
    f = finding()
    assert "Calculated by code, not AI" in lv.calc_card(f, True) and "--d:98;--t:6;--o:5" in lv.calc_card(f, True)
    assert "Waiting for the match and price steps" in lv.calc_card(f, False)
    assert "✓ V1: passed" in lv.checks_card(f, True) and "mq-spin" in lv.checks_card(f, False)
    bad = finding(checks=[{"check": "V2", "passed": False, "detail": "numbers differ"}], flags=["No effective date"])
    html = lv.checks_card(bad, True)
    assert "✗ V2: failed" in html and "Held for review: not guessed" in html and "numbers differ" in html
    assert "<mark>Every employer shall pay &#36;15.00.</mark>" in lv.reading_card(f)
    assert "AI reading" in lv.answer_card(f) and "&#36;13.75 per hour" in lv.answer_card(f)


def test_routing_card_lands_the_finding_in_its_lane_and_split_bar_counts():
    ev = event(9, "route_findings", findings=[finding()], lanes={"decision": 4, "ready": 4, "wording": 1}, ai_answers=18, prices=17)
    html = lv.routing_card(finding(), ev)
    assert 'class="mq-lane on"><b>Ready to approve</b> (4)' in html and "3.1 Chicago" in html
    assert "AI read 9 sections" in lv.split_bar(ev) and "code calculated 17 prices" in lv.split_bar(ev)
    assert "a person decides 8" in lv.split_bar(ev)
    assert "Not routed yet" in lv.routing_card(finding(lane=None, why=""), ev)


def test_motion_is_css_only_and_honours_reduced_motion():
    from maya.ui import style
    assert "prefers-reduced-motion: reduce" in style.CSS and "<script" not in style.CSS
    dash = chr(0x2014)
    assert dash not in style.CSS and dash not in lv.TOP_STRIP
