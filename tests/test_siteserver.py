"""The local regulator site: what it serves, the agent fetching over HTTP, and reset (A2, P8)."""
import hashlib
import json
import shutil
from datetime import date
from pathlib import Path

import pytest
import requests

from maya import db, site, siteserver, sources

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def cfg(tmp_path):
    shutil.copytree(ROOT / "data", tmp_path / "data", ignore=shutil.ignore_patterns("replays", "uploads"))
    shutil.copy(ROOT / "maya.config.yaml", tmp_path / "maya.config.yaml")
    cfg = site.load_config(tmp_path / "maya.config.yaml")
    cfg["site"]["server"]["port"] = 0
    yield cfg
    siteserver.stop_all()


def get(url):
    return requests.Session().get(url, timeout=5)


def test_serves_index_pages_and_listed_files_on_localhost_only(cfg):
    base = siteserver.ensure_running(cfg)
    assert base.startswith("http://127.0.0.1:")
    index = get(base + "/")
    assert index.status_code == 200 and "Synthetic site" in index.text and "New York City, Los Angeles, Chicago" in index.text
    assert "PSB-2026-02" in index.text and "bulletin/gov_rules_v2" in index.text
    docs = get(base + "/index.json").json()["documents"]
    assert [d["version"] for d in docs] == [1, 2]
    assert get(base + "/bulletin/gov_rules_v2").text.count("Payroll Rules for Employers") == 1
    txt = get(base + "/gov_rules_v2.txt").content
    assert hashlib.sha256(txt).hexdigest() == docs[1]["sha256"]


def test_held_back_and_unlisted_files_are_never_served(cfg):
    base = siteserver.ensure_running(cfg)
    for path in ("/gov_rules_v3.txt", "/_unpublished/gov_rules_v3.txt", "/../maya.config.yaml", "/maya.db", "/bulletin/gov_rules_v3"):
        assert get(base + path).status_code == 404


def test_the_agent_fetches_over_http_and_publishing_shows_up(cfg):
    conn = db.connect(cfg["_root"] / "maya.db")
    first = sources.watch_sources(cfg, conn)
    fetched = cfg["_root"] / cfg["site"]["server"]["fetch_dir"]
    assert not first.errors and {d.path.parent for d in first.unseen if d.source == "Policy site"} == {fetched}
    names = {p.name for p in fetched.iterdir()}
    assert names == {"gov_rules_v1.txt", "gov_rules_v2.txt"}
    site.publish_next(cfg)  # a regulator posts a bulletin
    again = sources.watch_sources(cfg, conn)
    assert "gov_rules_v3.txt" in {p.name for p in fetched.iterdir()}
    assert any(c.new.name == "gov_rules_v3.txt" and c.trusted for c in again.changes)


def test_custom_change_is_served_and_fetched(cfg):
    done = site.publish_custom(cfg, "New York City", "minimum_wage", "18.00", date(2026, 11, 2))
    base = siteserver.ensure_running(cfg)
    listed = [d["file"] for d in get(base + "/index.json").json()["documents"]]
    assert done.files[0] in listed and get(f"{base}/{done.files[1]}").status_code == 200
    result = sources.watch_sources(cfg, db.connect(cfg["_root"] / "maya.db"))
    assert any(c.new.name == done.files[0] for c in result.changes)


def test_a_file_that_does_not_match_the_index_hash_is_refused(cfg):
    (cfg["_root"] / "data/policy_site/gov_rules_v2.txt").write_text("tampered\n")
    result = sources.watch_sources(cfg, db.connect(cfg["_root"] / "maya.db"))
    assert result.errors and "does not match the sha256" in result.errors[0]
    assert not [c for c in result.changes if c.source == "Policy site"]


def test_reset_clears_downloads_and_custom_versions_and_the_page_updates(cfg):
    base = siteserver.ensure_running(cfg)
    site.publish_next(cfg)
    site.publish_custom(cfg, "Los Angeles", "filing_deadline", "15", date(2026, 12, 2))
    sources.watch_sources(cfg, db.connect(cfg["_root"] / "maya.db"))
    assert "PSB-2026-03" in get(base + "/").text
    site.reset(cfg)
    assert not (cfg["_root"] / cfg["site"]["server"]["fetch_dir"]).exists()
    assert "PSB-2026-03" not in get(base + "/").text and len(get(base + "/index.json").json()["documents"]) == 2


def test_reading_the_folder_directly_still_works_when_the_server_is_off(cfg):
    cfg["site"]["server"]["enabled"] = False
    result = sources.watch_sources(cfg, db.connect(cfg["_root"] / "maya.db"))
    assert not result.errors and all("_fetched" not in str(d.path) for d in result.unseen)
