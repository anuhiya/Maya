"""Watched sources, fingerprints, fictional site and Federal Register search (A2, P8).

Fingerprints live in the document_versions table: a document whose fingerprint is stored there has been
seen and its source is skipped. Nothing is stored until a run finishes (commit), so a failed run never
hides a change.
"""
import hashlib
import json
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

import requests

from maya import db
from maya.ingest import read_document
from maya.pipeline import policy_id

_VERSION = re.compile(r"_v(\d+)$", re.IGNORECASE)
_SUFFIXES = (".txt", ".pdf")
FR_TIMEOUT_SECONDS = 15
FR_RESULTS = 5


@dataclass(frozen=True)
class Doc:
    source: str
    trusted: bool
    path: Path
    family: str
    version: int
    fingerprint: str

    @property
    def name(self) -> str:
        return self.path.name


@dataclass
class SourceChange:
    """A new document and the version before it, ready to compare."""

    source: str
    trusted: bool
    family: str
    old: Doc
    new: Doc


@dataclass
class WatchResult:
    changes: list[SourceChange]
    unchanged: list[str]  # sources with documents, all already seen
    empty: list[str]  # sources with no documents
    unseen: list[Doc]  # every new document, for commit()


@dataclass
class InformationalItem:
    """A Federal Register hit. Shown to the reviewer, never applied to employees or cost."""

    title: str
    date: str
    url: str


def fingerprint(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _files(cfg: dict, source: dict) -> list[Path]:
    base = cfg["_root"] / source["path"]
    if source["kind"] == "policy_site":  # only what the site index lists is published
        try:
            index = json.loads((cfg["_root"] / cfg["site"]["index_file"]).read_text(encoding="utf-8"))
        except FileNotFoundError:
            return []
        return [base / e["file"] for e in index["documents"] if (base / e["file"]).exists()]
    if not base.is_dir():
        return []
    files = sorted(p for p in base.iterdir() if p.is_file() and p.suffix.lower() in _SUFFIXES)
    names = {p.stem for p in files if p.suffix.lower() == ".txt"}
    return [p for p in files if p.suffix.lower() == ".txt" or p.stem not in names]  # TXT wins over its PDF


def _version(path: Path, source: dict) -> int | None:
    found = _VERSION.search(path.stem)
    if found:
        return int(found.group(1))
    return path.stat().st_mtime_ns if source["kind"] == "upload" else None  # uploads: oldest first


def watch_sources(cfg: dict, conn: sqlite3.Connection) -> WatchResult:
    """Fingerprint every watched document and pair each new one with the version before it."""
    seen = {(row["file_name"], row["fingerprint"]) for row in db.list_document_versions(conn)}
    taken: set[tuple[str, str]] = set()
    by_family: dict[str, list[Doc]] = {}
    unchanged, empty = [], []
    for source in cfg["sources"]:
        if not source.get("path"):
            continue  # the Federal Register is not a document folder
        docs = []
        for path in _files(cfg, source):
            version = _version(path, source)
            if version is None:
                continue
            fp = fingerprint(path)
            if (path.name, fp) in taken:
                continue  # the same file already found in an earlier source
            taken.add((path.name, fp))
            docs.append(Doc(source["name"], bool(source.get("trusted")), path,
                            policy_id(path, path, source, cfg), version, fp))
        if not docs:
            empty.append(source["name"])
        elif all((d.name, d.fingerprint) in seen for d in docs):
            unchanged.append(source["name"])
        for doc in docs:
            by_family.setdefault(doc.family, []).append(doc)

    changes, unseen = [], []
    for family, docs in by_family.items():
        docs.sort(key=lambda d: (d.version, d.name))
        for i, doc in enumerate(docs):
            if (doc.name, doc.fingerprint) in seen:
                continue
            unseen.append(doc)
            if i > 0:
                changes.append(SourceChange(doc.source, doc.trusted, family, docs[i - 1], doc))
    return WatchResult(changes, unchanged, empty, unseen)


def commit(conn: sqlite3.Connection, docs: list[Doc]) -> None:
    """Remember these documents so the next run skips them."""
    for doc in docs:
        db.save_document_version(conn, policy_family=doc.family, file_name=doc.name,
                                 fingerprint=doc.fingerprint, text=read_document(doc.path))


def save_upload(cfg: dict, name: str, data: bytes) -> Path:
    """Save a manually uploaded file into the trusted uploads folder, under a safe plain name."""
    source = next(s for s in cfg["sources"] if s["kind"] == "upload")
    clean = re.sub(r"[^A-Za-z0-9._-]", "_", Path(name).name)
    if Path(clean).suffix.lower() not in _SUFFIXES:
        raise ValueError("only .txt and .pdf files can be uploaded")
    folder = cfg["_root"] / source["path"]
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / clean
    target.write_bytes(data)
    return target


def _get(url: str, params: dict) -> dict:
    response = requests.get(url, params=params, timeout=FR_TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.json()


def search_federal_register(cfg: dict, get=_get) -> tuple[list[InformationalItem], str | None]:
    """One read-only search for minimum wage and payroll terms. Returns (items, error); never raises."""
    source = next(s for s in cfg["sources"] if s["kind"] == "federal_register")
    params = {"conditions[term]": " ".join(source["search_terms"]), "per_page": FR_RESULTS, "order": "newest",
              "fields[]": ["title", "publication_date", "html_url"]}
    try:
        data = get(source["url"].rstrip("/") + "/documents.json", params)
        return [InformationalItem(r["title"], r["publication_date"], r["html_url"])
                for r in data.get("results", [])], None
    except Exception as err:  # network, bad JSON, missing field: the run goes on without it
        return [], f"Federal Register search failed: {type(err).__name__}"
