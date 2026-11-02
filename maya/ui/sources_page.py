"""Sources page: every policy file the agent watches, its fingerprint and a section viewer (A2, P8)."""
import json
from dataclasses import dataclass, field
from pathlib import Path

import streamlit as st

from maya import sources
from maya.ingest import ReadingError
from maya.models import Section
from maya.pipeline import policy_id
from maya.site import load_config
from maya.split import read_sections
from maya.ui.style import chip, esc, md


@dataclass
class FileInfo:
    name: str
    source: str
    trusted: bool
    path: Path
    fingerprint: str
    family: str
    version: int | None
    sections: list[Section] = field(default_factory=list)
    error: str = ""
    current: bool = False

    @property
    def jurisdictions(self) -> list[str]:
        return sorted({s.jurisdiction for s in self.sections if s.jurisdiction})

    @property
    def dates(self) -> list[str]:
        return sorted({s.effective_date for s in self.sections if s.effective_date})


def _paths(cfg: dict, source: dict) -> list[Path]:
    """The files of one source. The site is read from its index, never from the held-back folder."""
    base = cfg["_root"] / source["path"]
    if source["kind"] == "policy_site":
        try:
            index = json.loads((cfg["_root"] / cfg["site"]["index_file"]).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []
        return [base / e["file"] for e in index["documents"] if (base / e["file"]).exists()]
    return sources._files(cfg, source)


def collect(cfg: dict) -> list[FileInfo]:
    """One row per watched file, with the newest version of each policy family marked current."""
    found = []
    for source in cfg["sources"]:
        if not source.get("path"):
            continue
        for path in _paths(cfg, source):
            info = FileInfo(path.name, source["name"], bool(source.get("trusted")), path, sources.fingerprint(path),
                            policy_id(path, path, source, cfg), sources._version(path, source))
            try:
                info.sections = read_sections(path)
            except (ReadingError, OSError) as err:
                info.error = str(err)
            found.append(info)
    newest: dict[tuple, int] = {}
    for f in found:
        if f.version is not None:
            key = (f.source, f.family)
            newest[key] = max(newest.get(key, f.version), f.version)
    for f in found:
        f.current = f.version is not None and f.version == newest[(f.source, f.family)]
    return sorted(found, key=lambda f: (f.source, f.family, f.version or 0, f.name))


def version_label(f: FileInfo) -> str:
    if f.version is None:
        return "Unversioned"
    return "Current" if f.current else "Previous"


def table_html(files: list[FileInfo]) -> str:
    heads = ["File", "Source", "Jurisdictions", "Trusted", "Fingerprint", "Sections", "Effective dates", "Version"]
    body = ""
    for f in files:
        flag = chip("Trusted", "good") if f.trusted else chip("Not trusted", "review")
        word = version_label(f)
        ver = chip(word, {"Current": "good", "Previous": ""}.get(word, "review"))
        cells = [(esc(f.name), "nw mono"), (esc(f.source), "nw"), (esc(", ".join(f.jurisdictions) or "none"), "nw"),
                 (flag, "nw"), (esc(f.fingerprint[:12]), "nw mono"),
                 (esc(len(f.sections)) if not f.error else "Could not read", "nw"),
                 (esc("; ".join(f.dates) or "none"), "wrap"), (ver, "nw")]
        body += "<tr>" + "".join(f'<td class="{k}">{v}</td>' for v, k in cells) + "</tr>"
    return ('<div class="mq-scroll"><table class="mq-table"><tr>'
            + "".join(f'<th class="{"wrap" if h == "Effective dates" else "nw"}">{h}</th>' for h in heads)
            + f"</tr>{body}</table></div>")


def render(cfg: dict | None = None) -> None:
    cfg = cfg or load_config()
    st.markdown('<div class="mq-kicker">Sources</div><div class="mq-title">Every policy file the agent watches</div>',
                unsafe_allow_html=True)
    try:
        files = collect(cfg)
    except (OSError, KeyError, ValueError) as err:
        st.error(md(f"Could not list the sources: {err}. Check the sources section of maya.config.yaml."))
        return
    if not files:
        st.info("No policy files found. Check the sources in maya.config.yaml or publish a bulletin on Agent activity.")
        return
    st.caption("Synthetic bulletins. Place names are real; wage rates, rules and dates are illustrative, not the actual law.")
    st.caption("Fingerprints are the first 12 characters of each file's sha256. A file whose fingerprint was seen "
               "before is skipped. Held-back versions are not listed until they are published.")
    st.markdown(table_html(files), unsafe_allow_html=True)
    bad = [f for f in files if f.error]
    for f in bad:
        st.error(md(f"Could not read {f.name}: {f.error}"))
    st.markdown('<div class="mq-sub">Section viewer</div>', unsafe_allow_html=True)
    readable = [f for f in files if not f.error]
    if not readable:
        st.info("No readable file to show.")
        return
    pick = st.selectbox("File", readable, key="sources_file",
                        format_func=lambda f: f"{f.name} ({f.source}, {version_label(f).lower()})")
    rows = "".join(
        f'<tr><td class="nw mono">{esc(s.number)}</td><td class="nw">{esc(s.title)}</td><td class="nw">{esc(s.jurisdiction or "none")}</td>'
        f'<td class="nw mono">{esc(s.effective_date or "No effective date found")}</td>'
        f'<td class="wrap">{esc(" ".join(l for l in s.text.split(chr(10)) if not l.startswith(("Jurisdiction:", "Effective Date:"))))}</td></tr>'
        for s in pick.sections)
    st.markdown('<div class="mq-scroll"><table class="mq-table"><tr><th class="nw">Section</th><th class="nw">Title</th>'
                '<th class="nw">Jurisdiction</th><th class="nw">Effective date</th><th class="wrap">Rule</th></tr>'
                + rows + "</table></div>", unsafe_allow_html=True)
