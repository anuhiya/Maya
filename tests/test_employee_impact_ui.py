"""Employee impact page on the saved main-pair run, a temp database, no network (B3, B4)."""
import html
import re
from datetime import date

import pytest
from streamlit.testing.v1 import AppTest

from maya.site import load_config


def page(cfg):
    from maya.ui import employee_impact, style
    style.inject_css()
    employee_impact.render(cfg=cfg)


@pytest.fixture
def cfg(tmp_path):
    import streamlit as st
    st.cache_data.clear()
    cfg = load_config()
    cfg["state"] = {"database": str(tmp_path / "test.db")}
    cfg["llm"] = {**cfg["llm"], "replay_dir": "tests/fixtures/ai"}
    return cfg


def run(cfg, **state):
    at = AppTest.from_function(page, kwargs={"cfg": cfg}, default_timeout=30)
    for k, val in state.items():
        at.session_state[k] = val
    at.run()
    assert not at.exception
    return at


def text(at):
    return html.unescape("\n".join(m.value for m in [*at.markdown, *at.info, *at.error]))


def test_totals_and_assumptions(cfg):
    shown = text(run(cfg))
    assert "$273.19" in shown and "$142.80" in shown
    assert "Assumptions" in shown and "1.5 times" in shown and "Contractors are excluded" in shown
    assert "0.19 x 40 h + 0.19 x 1.5 x 2 h = $8.17" in shown  # E001 overtime


def test_as_of_is_shared(cfg):
    shown = text(run(cfg, as_of=date(2027, 1, 1)))
    assert "$415.99" in shown and "As of 2027-01-01" in shown


def test_filters_are_shared(cfg):
    shown = text(run(cfg, f_jurisdiction="Calder"))
    assert "Jurisdiction: Calder" in shown
    assert "$142.80" in shown and "$273.19" not in shown


def test_filter_with_no_match(cfg):
    at = run(cfg, f_jurisdiction="Meridian", f_category="Tax rate")
    assert any("No findings match these filters" in i.value for i in at.info)


def test_copy_rules(cfg):
    shown = text(run(cfg))
    for banned in ("rule A1", "\u00a7", "\u00b7", "\u2014"):
        assert banned not in shown


def test_affected_first_largest_increase_first_and_no_wrap(cfg):
    shown = text(run(cfg))
    amounts = [float(x) for x in re.findall(r'<td class="mono nw">(\d+\.\d\d)</td></tr>', shown)]
    first_run = amounts[:amounts.index(0.0)] if 0.0 in amounts else amounts
    assert first_run == sorted(first_run, reverse=True) and len(first_run) >= 10
    assert "Weekly increase" in shown and "Increase a week" not in shown
    assert '<th class="wrap">Why</th>' in shown and '<th class="nw">Employee</th>' in shown


def test_hybrid_review_rows_shown_without_changing_totals(cfg):
    shown = text(run(cfg))
    assert "Needs review: works part of the week in Avalon" in shown
    assert "Needs review: works part of the week in Calder" in shown
    assert "1.45 x 40 h = $58.00" in shown and "0.30 x 24 h = $7.20" in shown
    assert "$273.19" in shown and "$142.80" in shown
