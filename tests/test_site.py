"""Fictional site: index, publish next, reset (A2, A4)."""
import hashlib
import json
import shutil
from pathlib import Path

import pytest

from maya import site

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def cfg(tmp_path):
    shutil.copytree(ROOT / "data" / "policy_site", tmp_path / "data" / "policy_site", ignore=shutil.ignore_patterns("_fetched"))
    cfg = site.load_config()
    cfg["_root"] = tmp_path
    return cfg


def snapshot(root):
    return {
        str(p.relative_to(root)): p.read_bytes()
        for p in sorted((root / "data" / "policy_site").rglob("*"))
        if p.is_file()
    }


def test_index_lists_published_documents(cfg):
    entries = site.build_index(cfg)
    assert [e["bulletin_number"] for e in entries] == ["PSB-2026-01", "PSB-2026-02"]
    for e in entries:
        assert "pdf" not in e
        assert e["policy_family"] == "regional-dol-payroll-bulletin"
        path = cfg["_root"] / "data" / "policy_site" / e["file"]
        assert e["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert entries[1]["issued"] == "October 15, 2026"


def test_committed_index_matches_folder(cfg):
    site.build_index(cfg)
    built = (cfg["_root"] / "data" / "policy_site" / "index.json").read_bytes()
    assert built == (ROOT / "data" / "policy_site" / "index.json").read_bytes()


def test_publish_then_reset_restores_start(cfg):
    site.build_index(cfg)
    start = snapshot(cfg["_root"])
    moved = site.publish_next(cfg)
    assert moved == ["gov_rules_v3.pdf", "gov_rules_v3.txt"]
    docs = json.loads((cfg["_root"] / "data/policy_site/index.json").read_text())["documents"]
    assert docs[-1]["bulletin_number"] == "PSB-2026-03"
    assert docs[-1]["pdf"] == "gov_rules_v3.pdf"
    assert not list((cfg["_root"] / "data/policy_site/_unpublished").glob("gov_rules_v3.*"))
    site.reset(cfg)
    assert snapshot(cfg["_root"]) == start


def test_publish_with_nothing_held_back(cfg):
    site.publish_next(cfg)
    assert site.publish_next(cfg) == []


def test_reset_clears_state_files(cfg):
    root = cfg["_root"]
    up, db = root / "data/uploads", root / cfg["state"]["database"]
    up.mkdir(parents=True)
    (up / "a.txt").write_text("x")
    db.write_text("x")
    site.reset(cfg)
    assert not up.exists() and not db.exists()
    site.reset(cfg)  # missing files are fine


# ---- publish_custom (B8, P8) ------------------------------------------------------------------------

from datetime import date, timedelta  # noqa: E402

from maya.ingest import read_document  # noqa: E402
from maya.split import split_sections  # noqa: E402


def preset_args(cfg, i):
    p = cfg["site"]["presets"][i]
    offset = p.get("date_offset_days")
    when = None if offset is None else date.fromisoformat(cfg["as_of_date"]) + timedelta(days=offset)
    return p["jurisdiction"], p["change_type"], p.get("value", ""), when


def sections(cfg, name):
    return split_sections((cfg["_root"] / "data/policy_site" / name).read_text(encoding="utf-8"),
                          cfg["jurisdictions"])


@pytest.mark.parametrize("i", range(5))
def test_each_preset_changes_exactly_one_section(cfg, i):
    done = site.publish_custom(cfg, *preset_args(cfg, i))
    old, new = sections(cfg, "gov_rules_v2.txt"), sections(cfg, done.files[0])
    assert [s.number for s in new] == [s.number for s in old]
    changed = [n.number for o, n in zip(old, new) if o.text != n.text or o.effective_date != n.effective_date]
    assert changed == [done.section]
    assert next(n for n in new if n.number == done.section).jurisdiction == preset_args(cfg, i)[0]
    pdf_sections = split_sections(read_document(cfg["_root"] / "data/policy_site" / done.files[1]),
                                  cfg["jurisdictions"])
    assert [s.number for s in pdf_sections] == [s.number for s in new]


def test_custom_version_is_indexed_with_hash_and_html(cfg):
    done = site.publish_custom(cfg, *preset_args(cfg, 0))
    root = cfg["_root"] / "data/policy_site"
    docs = json.loads((root / "index.json").read_text())["documents"]
    last = docs[-1]
    assert (last["file"], last["pdf"], last["version"], last["custom"]) == (done.files[0], done.files[1], 4, True)
    assert last["bulletin_number"] == "PSB-2026-04" and last["issued"] == "November 2, 2026"
    assert last["sha256"] == hashlib.sha256((root / done.files[0]).read_bytes()).hexdigest()
    assert last["sha256"] in (root / "index.html").read_text() and done.files[0] in (root / "index.html").read_text()
    assert "Supersedes: Bulletin PSB-2026-02, issued October 15, 2026, in full." in (root / done.files[0]).read_text()


def test_custom_leaves_the_rehearsed_version_held_back(cfg):
    site.publish_custom(cfg, *preset_args(cfg, 0))
    held = cfg["_root"] / "data/policy_site/_unpublished"
    assert (held / "gov_rules_v3.txt").exists() and (held / "gov_rules_v3.pdf").exists()
    assert site.publish_next(cfg) == ["gov_rules_v3.pdf", "gov_rules_v3.txt"]


def test_second_custom_change_builds_on_the_first(cfg):
    site.publish_custom(cfg, *preset_args(cfg, 0))
    done = site.publish_custom(cfg, *preset_args(cfg, 4))
    assert done.files[0] == "gov_rules_custom_v5.txt"
    text = sections(cfg, done.files[0])
    assert next(s for s in text if s.number == "1.1").text.endswith("$18.00 per hour for all hours worked.")


def test_missing_date_preset_has_no_date_line(cfg):
    done = site.publish_custom(cfg, *preset_args(cfg, 2))
    section = next(s for s in sections(cfg, done.files[0]) if s.number == done.section)
    assert section.effective_date is None and "$14.25" in section.text


def test_wording_preset_keeps_numbers_and_date(cfg):
    done = site.publish_custom(cfg, *preset_args(cfg, 3))
    old = next(s for s in sections(cfg, "gov_rules_v2.txt") if s.number == done.section)
    new = next(s for s in sections(cfg, done.files[0]) if s.number == done.section)
    assert new.text != old.text and new.effective_date == old.effective_date and "$13.75" in new.text


@pytest.mark.parametrize("args", [
    ("Nowhere", "minimum_wage", "18", None),
    ("New York City", "reporting_requirement", "twice", None),
    ("New York City", "minimum_wage", "abc", None),
    ("New York City", "minimum_wage", "-3", None),
    ("Los Angeles", "filing_deadline", "2.5", None),
    ("Chicago", "wording_only", "Each employer must pay $99.00 per hour.", None),
    ("New York City", "no_such_type", "1", None),
])
def test_bad_custom_changes_are_refused_and_leave_nothing(cfg, args):
    start = snapshot(cfg["_root"])
    with pytest.raises(ValueError):
        site.publish_custom(cfg, *args)
    assert snapshot(cfg["_root"]) == start


def test_reset_removes_every_custom_version(cfg):
    site.build_index(cfg)
    start = snapshot(cfg["_root"])
    site.publish_next(cfg)
    site.publish_custom(cfg, *preset_args(cfg, 0))
    site.publish_custom(cfg, *preset_args(cfg, 1))
    root = cfg["_root"] / "data/policy_site"
    assert len(list(root.glob("*custom*"))) == 4
    site.reset(cfg)
    assert not list(root.glob("*custom*")) and snapshot(cfg["_root"]) == start
    assert all("custom" not in d for d in json.loads((root / "index.json").read_text())["documents"])
