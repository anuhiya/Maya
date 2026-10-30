"""Split a policy into numbered sections (B1)."""
import re
from pathlib import Path

from maya.ingest import ReadingError, normalise, read_document
from maya.models import Section
from maya.site import load_config

_HEADER = re.compile(r"^(\d+(?:\.\d+)+)\s+([A-Z].*)$")
_JURISDICTION = re.compile(r"^Jurisdiction:\s*(.*)$", re.IGNORECASE)
_EFFECTIVE = re.compile(r"^Effective Date:\s*(.*)$", re.IGNORECASE)


def _canonical(name: str, jurisdictions) -> str:
    for known in jurisdictions:
        if known.casefold() == name.casefold():
            return known
    return name


def split_sections(text: str, jurisdictions=()) -> list[Section]:
    """Split normalised text into sections; everything before the first one is skipped."""
    blocks: list[tuple[str, str, list[str]]] = []
    for line in normalise(text).split("\n"):
        m = _HEADER.match(line)
        if m:
            blocks.append((m.group(1), m.group(2).strip(), []))
        elif blocks and line:
            blocks[-1][2].append(line)
    if not blocks:
        raise ReadingError("no numbered sections found")

    sections = []
    for number, title, lines in blocks:
        jurisdiction = effective = None
        kept: list[str] = []
        body: list[str] = []
        for line in lines:
            j, e = _JURISDICTION.match(line), _EFFECTIVE.match(line)
            if j and jurisdiction is None:
                jurisdiction = _canonical(j.group(1).strip(), jurisdictions) or None
                kept.append(line)
            elif e and effective is None:
                effective = e.group(1).strip() or None
                kept.append(line)
            else:
                body.append(line)
        if body:
            kept.append(" ".join(body))
        sections.append(Section(number=number, title=title, text="\n".join(kept),
                                jurisdiction=jurisdiction, effective_date=effective))
    return sections


def rule_text(section: Section) -> str:
    """The rule sentence only: no title, Jurisdiction or Effective Date line."""
    return "\n".join(
        line for line in section.text.split("\n")
        if not (_JURISDICTION.match(line) or _EFFECTIVE.match(line))
    )


def read_sections(path) -> list[Section]:
    """Read a TXT or PDF file and split it into sections."""
    try:
        jurisdictions = load_config().get("jurisdictions", [])
    except OSError:
        jurisdictions = []
    sections = split_sections(read_document(path), jurisdictions)
    return sections
