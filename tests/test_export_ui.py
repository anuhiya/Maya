"""Export page on the saved main-pair run, a temp database, no network (B7)."""
from datetime import date

import pytest
from streamlit.testing.v1 import AppTest

from maya.site import load_config


def page(cfg):
    from maya.ui import export, style
    style.inject_css()
    export.render(cfg=cfg)


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


def test_two_download_buttons_with_as_of_in_file_name(cfg):
    at = run(cfg, as_of=date(2027, 1, 1))
    buttons = at.get("download_button")
    assert len(buttons) == 2
    labels = [b.proto.label for b in buttons]
    assert labels == ["Download findings CSV", "Download employee impact CSV"]
    assert any("Filters" in c.value or "filters" in c.value for c in at.caption)


def test_filters_apply_to_counts(cfg):
    at = run(cfg, f_jurisdiction="Calder")
    captions = " ".join(c.value for c in at.caption)
    assert "3 findings" in captions
    assert "Jurisdiction: Calder" in " ".join(m.value for m in at.markdown)


def test_avalon_filter_counts_in_exports(cfg):
    import csv, io
    from maya import export
    from maya.ui import view
    from maya import db
    import streamlit as st
    st.session_state["f_jurisdiction"] = "Avalon"
    conn = db.connect(cfg["state"]["database"])
    v = view.build_view(cfg, conn)
    findings = [i.finding for i in v.shown]
    rows = [r for i in v.shown for r in i.rows]
    assert len(list(csv.DictReader(io.StringIO(export.findings_csv(findings, conn))))) == 4
    assert len(list(csv.DictReader(io.StringIO(export.impact_csv(rows))))) == 113  # 112 Avalon rows + hybrid E076
