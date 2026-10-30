"""Fictional site index, publish next version and reset (A2, A4)."""
import hashlib
import json
import re
import shutil
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "maya.config.yaml"


def load_config(path=CONFIG_PATH):
    with open(path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    cfg["_root"] = Path(path).resolve().parent
    return cfg


def _paths(cfg):
    root = cfg["_root"]
    site = cfg["site"]
    return (
        root / site["dir"],
        root / site["unpublished_dir"],
        root / site["index_file"],
        list(site["release_order"]),
    )


def _family(cfg):
    return cfg["policies"]["main_pair"]["policy_family"]


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _entry(txt, family, site_dir):
    text = txt.read_text(encoding="utf-8")
    number = re.search(r"^Bulletin number:\s*(\S+)\s*$", text, re.M).group(1)
    issued = re.search(r"^Issued:\s*(.+?)\s*$", text, re.M).group(1)
    heading = re.search(r"^(PAYROLL STANDARDS BULLETIN)\s+\S+\s*$", text, re.M).group(1)
    entry = {
        "title": f"{heading.title()} {number}",
        "bulletin_number": number,
        "version": int(re.search(r"_v(\d+)$", txt.stem).group(1)),
        "issued": issued,
        "file": txt.name,
        "sha256": _sha256(txt),
        "policy_family": family,
    }
    pdf = txt.with_suffix(".pdf")
    if pdf.exists():
        entry["pdf"] = pdf.name
    return entry


def build_index(cfg=None):
    """Write the index from the TXT files now in the site folder and return the entries."""
    cfg = cfg or load_config()
    site_dir, _, index_file, _ = _paths(cfg)
    entries = [_entry(t, _family(cfg), site_dir) for t in site_dir.glob("*.txt")]
    entries.sort(key=lambda e: e["version"])
    index_file.write_text(
        json.dumps({"documents": entries}, indent=2) + "\n", encoding="utf-8"
    )
    return entries


def _held_back(cfg):
    _, held_dir, _, order = _paths(cfg)
    return [s for s in order if (held_dir / f"{s}.txt").exists()]


def publish_next(cfg=None):
    """Move the next held-back version into the site, rebuild the index, return the file names moved."""
    cfg = cfg or load_config()
    site_dir, held_dir, _, _ = _paths(cfg)
    pending = _held_back(cfg)
    if not pending:
        return []
    moved = []
    for f in sorted(held_dir.glob(f"{pending[0]}.*")):
        shutil.move(str(f), site_dir / f.name)
        moved.append(f.name)
    build_index(cfg)
    return moved


def reset(cfg=None):
    """Move published release_order versions back, rebuild the index, clear the database and uploads."""
    cfg = cfg or load_config()
    site_dir, held_dir, _, order = _paths(cfg)
    held_dir.mkdir(parents=True, exist_ok=True)
    for stem in order:
        for f in sorted(site_dir.glob(f"{stem}.*")):
            shutil.move(str(f), held_dir / f.name)
    build_index(cfg)
    (cfg["_root"] / cfg["state"]["database"]).unlink(missing_ok=True)  # reviews, runs and fingerprints
    for source in cfg["sources"]:
        if source["kind"] == "upload":
            shutil.rmtree(cfg["_root"] / source["path"], ignore_errors=True)
