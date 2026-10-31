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
    shutil.copytree(ROOT / "data" / "policy_site", tmp_path / "data" / "policy_site")
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
