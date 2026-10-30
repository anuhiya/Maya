"""Read TXT and PDF and normalise text (B1)."""
import re
from pathlib import Path

import pdfplumber


class ReadingError(Exception):
    """A document could not be read or split. Never treated as "no changes"."""


_QUOTES = str.maketrans({
    "‘": "'", "’": "'", "‚": "'", "‛": "'",
    "“": '"', "”": '"', "„": '"', "‟": '"',
    " ": " ", " ": " ", " ": " ",
})


def normalise(text: str) -> str:
    """Straight quotes, single spaces, and words split across lines rejoined."""
    text = text.translate(_QUOTES).replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"(?<=[A-Za-z])-[ \t]*\n[ \t]*(?=[a-z])", "", text)
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]
    return "\n".join(lines).strip()


def _read_pdf(path: Path) -> str:
    with pdfplumber.open(path) as pdf:
        pages = [page.extract_text() or "" for page in pdf.pages]
    text = "\n".join(pages)
    if not text.strip():
        raise ReadingError(f"{path.name} has no text (scanned or empty PDF); it cannot be read")
    return text


def read_document(path) -> str:
    """Return the normalised text of a TXT or PDF file."""
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".txt":
        text = path.read_text(encoding="utf-8")
    elif suffix == ".pdf":
        text = _read_pdf(path)
    else:
        raise ReadingError(f"{path.name}: only .txt and .pdf files can be read")
    text = normalise(text)
    if not text:
        raise ReadingError(f"{path.name} is empty")
    return text
