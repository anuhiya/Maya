"""Sources page: one row per watched file, current or previous, and the section viewer (A2, P8)."""
import shutil
from pathlib import Path

from streamlit.testing.v1 import AppTest

from maya.site import load_config
from maya.ui import sources_page

ROOT = Path(__file__).resolve().parent.parent


def temp_cfg(tmp_path):
    shutil.copytree(ROOT / "data", tmp_path / "data", ignore=shutil.ignore_patterns("replays", "uploads", "_fetched"))
    shutil.copy(ROOT / "maya.config.yaml", tmp_path / "maya.config.yaml")
    return load_config(tmp_path / "maya.config.yaml")


def page(cfg):
    from maya.ui import sources_page as sp
    from maya.ui import style
    style.inject_css()
    sp.render(cfg=cfg)


def test_collect_lists_company_and_government_files_with_versions(tmp_path):
    cfg = temp_cfg(tmp_path)
    files = sources_page.collect(cfg)
    by = {(f.source, f.name): f for f in files}
    assert by[("Company policies", "company_pay_policy_v2.txt")].current
    assert not by[("Company policies", "company_pay_policy_v1.txt")].current
    assert by[("Government bulletins", "gov_rules_v2.txt")].current and not by[("Government bulletins", "gov_rules_v1.txt")].current
    site_names = {f.name for f in files if f.source == "Policy site"}
    assert site_names == {"gov_rules_v1.txt", "gov_rules_v2.txt"}  # the held-back v3 is not listed
    v2 = by[("Government bulletins", "gov_rules_v2.txt")]
    assert v2.trusted and len(v2.fingerprint) == 64 and len(v2.sections) == 10
    assert v2.jurisdictions == ["Chicago", "Los Angeles", "New York City"] and "To be determined" in v2.dates


def test_page_shows_the_table_and_the_section_viewer(tmp_path):
    cfg = temp_cfg(tmp_path)
    at = AppTest.from_function(page, kwargs={"cfg": cfg}, default_timeout=60).run()
    assert not at.exception
    shown = " ".join(m.value for m in at.markdown)
    for word in ("Every policy file the agent watches", "Current", "Previous", "Trusted", "gov_rules_v2.txt",
                 "Section viewer"):
        assert word in shown
    at.selectbox(key="sources_file").select_index(0).run()
    assert not at.exception


def test_empty_state_and_unreadable_file_error(tmp_path):
    cfg = temp_cfg(tmp_path)
    for source in cfg["sources"]:
        if source.get("path"):
            source["path"] = "data/nowhere"
    cfg["site"]["index_file"] = "data/nowhere/index.json"
    at = AppTest.from_function(page, kwargs={"cfg": cfg}, default_timeout=60).run()
    assert any("No policy files found" in i.value for i in at.info)
    cfg2 = temp_cfg(tmp_path / "b")
    (cfg2["_root"] / "data/policies/gov_rules_v1.txt").write_text("no sections here\n")
    at2 = AppTest.from_function(page, kwargs={"cfg": cfg2}, default_timeout=60).run()
    assert any("Could not read gov_rules_v1.txt" in e.value for e in at2.error)


def test_app_has_a_sources_page_after_export():
    text = (ROOT / "app.py").read_text()
    assert text.index('"export"') < text.index('"sources"')
