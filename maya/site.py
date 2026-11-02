"""Fictional site index, publish next version, publish a custom change and reset (A2, A4, B8, P8)."""
import hashlib
import html
import importlib.util
import json
import re
import shutil
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
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


def _entry(txt, family, cfg):
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
    if _is_custom(txt.stem, cfg):
        entry["custom"] = True
    return entry


def build_index(cfg=None):
    """Write the index from the TXT files now in the site folder and return the entries."""
    cfg = cfg or load_config()
    site_dir, _, index_file, _ = _paths(cfg)
    entries = [_entry(t, _family(cfg), cfg) for t in site_dir.glob("*.txt")]
    entries.sort(key=lambda e: e["version"])
    index_file.write_text(
        json.dumps({"documents": entries}, indent=2) + "\n", encoding="utf-8"
    )
    index_file.with_suffix(".html").write_text(_index_html(entries, cfg["jurisdictions"]), encoding="utf-8")
    return entries


PAGE_STYLE = ("body{font-family:Georgia,serif;max-width:46rem;margin:2rem auto;padding:0 1rem;color:#1d2433}"
              "h1{font-size:1.5rem;margin-bottom:.2rem}.banner{background:#fff4d6;border:1px solid #d9b45a;"
              "padding:.4rem .7rem;font:600 .85rem sans-serif}table{border-collapse:collapse;width:100%;margin-top:1rem}"
              "th,td{text-align:left;padding:.4rem .5rem;border-bottom:1px solid #ccd}th{font:600 .75rem sans-serif;"
              "text-transform:uppercase;color:#555}code{font-size:.72rem;color:#555}pre{white-space:pre-wrap}")


def bulletin_slug(entry):
    return Path(entry["file"]).stem


def _index_html(entries, jurisdictions=()):
    """The fictional regulator's front page: each bulletin with its jurisdictions, date and links."""
    rows = []
    for e in entries:
        links = f'<a href="bulletin/{html.escape(bulletin_slug(e))}">Read</a> <a href="{html.escape(e["file"])}">TXT</a>'
        if e.get("pdf"):
            links += f' <a href="{html.escape(e["pdf"])}">PDF</a>'
        tag = " (custom)" if e.get("custom") else ""
        rows.append(f'<tr><td>{html.escape(e["title"])}{tag}<br><code>sha256 {e["sha256"]}</code></td>'
                    f'<td>{html.escape(", ".join(jurisdictions))}</td><td>{html.escape(e["issued"])}</td><td>{links}</td></tr>')
    return ("<!doctype html>\n<html lang=\"en\">\n<head><meta charset=\"utf-8\">"
            "<title>Regional Department of Labor: payroll bulletins</title>"
            f"<style>{PAGE_STYLE}</style></head>\n<body>\n"
            "<div class=\"banner\">Synthetic site. Place names are real; wage rates, rules and dates are illustrative, not the actual law.</div>\n"
            "<h1>Regional Department of Labor</h1>\n<p>Payroll standards bulletins, newest last.</p>\n"
            "<table><tr><th>Bulletin</th><th>Jurisdictions</th><th>Issued</th><th>Links</th></tr>\n"
            + "\n".join(rows) + "\n</table>\n</body>\n</html>\n")


def index_page(cfg):
    """The index page for the documents now in index.json."""
    _, _, index_file, _ = _paths(cfg)
    entries = json.loads(index_file.read_text(encoding="utf-8"))["documents"]
    return _index_html(entries, cfg["jurisdictions"])


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
    """Remove custom versions, move published release_order versions back, rebuild the index, clear the database and uploads."""
    cfg = cfg or load_config()
    site_dir, held_dir, _, order = _paths(cfg)
    held_dir.mkdir(parents=True, exist_ok=True)
    fetched = (cfg["site"].get("server") or {}).get("fetch_dir")
    if fetched:  # copies the agent downloaded from the site
        shutil.rmtree(cfg["_root"] / fetched, ignore_errors=True)
    for f in site_dir.iterdir():  # every custom version, so a custom change never survives a reset
        if f.is_file() and f.suffix in (".txt", ".pdf") and _is_custom(f.stem, cfg):
            f.unlink()
    for stem in order:
        for f in sorted(site_dir.glob(f"{stem}.*")):
            shutil.move(str(f), held_dir / f.name)
    build_index(cfg)
    (cfg["_root"] / cfg["state"]["database"]).unlink(missing_ok=True)  # reviews, runs and fingerprints
    for source in cfg["sources"]:
        if source["kind"] == "upload":
            shutil.rmtree(cfg["_root"] / source["path"], ignore_errors=True)


# ---- custom changes (B8): the presenter publishes a change of their own -----------------------------

_HEADER = re.compile(r"^(\d+(?:\.\d+)+)\s+([A-Z].*)$")
_NUMBERISH = re.compile(r"\$?\d[\d,]*(?:\.\d+)?%?")
_META = re.compile(r"^[A-Z][A-Za-z ]*:\s")


@dataclass
class Rule:
    number: str
    title: str
    jurisdiction: str | None = None
    date: str | None = None
    text: str = ""


@dataclass
class Published:
    """What publish_custom changed: the files written and the one section edited."""

    files: list[str]
    section: str
    title: str
    jurisdiction: str


def _is_custom(stem, cfg):
    marker = re.escape(cfg["site"].get("custom_marker", "custom"))
    return re.search(rf"_{marker}_v\d+$", stem) is not None


def _version(stem):
    found = re.search(r"_v(\d+)$", stem)
    return int(found.group(1)) if found else 0


def _parse(text):
    """Split a bulletin into its front lines and numbered rules (number, title, Jurisdiction, date, sentence)."""
    front, rules = [], []
    for line in text.splitlines():
        found = _HEADER.match(line)
        if found:
            rules.append(Rule(found.group(1), found.group(2).strip()))
        elif not rules:
            front.append(line)
        elif line.startswith("Jurisdiction:"):
            rules[-1].jurisdiction = line.partition(":")[2].strip()
        elif line.startswith("Effective Date:"):
            rules[-1].date = line.partition(":")[2].strip()
        elif line.strip():
            rules[-1].text = f"{rules[-1].text} {line.strip()}".strip()
    while front and not front[-1].strip():
        front.pop()
    return front, rules


def _render(front, rules):
    out = list(front)
    for r in rules:
        out += ["", f"{r.number} {r.title}", f"Jurisdiction: {r.jurisdiction}"]
        if r.date:
            out.append(f"Effective Date: {r.date}")
        out.append(r.text)
    return "\n".join(out) + "\n"


def _pdf_front(front):
    """Tag each front line with the look the PDF writer gives it, from its position and shape."""
    kinds, gaps, after_gap = [], 0, 0
    for i, line in enumerate(front):
        if not line.strip():
            gaps, after_gap = gaps + 1, 0
            kinds.append(("gap", ""))
            continue
        if i == 0:
            kind = "org"
        elif gaps == 0:
            kind = "sub"
        elif gaps == 1 and after_gap == 0:
            kind = "title"
        elif gaps == 1 and after_gap == 1:
            kind = "subtitle"
        elif line.startswith("NOTICE:"):
            kind = "notice"
        elif _META.match(line):
            kind = "meta"
        elif line.isupper():
            kind = "head"
        else:
            kind = "para"
        after_gap += 1
        kinds.append((kind, line))
    return kinds


def _write_pdf(front, rules, path):
    spec = importlib.util.spec_from_file_location("make_policies", ROOT / "scripts" / "make_policies.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.to_pdf(_pdf_front(front), [(r.number, r.title, r.jurisdiction, r.date, r.text) for r in rules], str(path))


def _date_text(when):
    return f"{when:%B} {when.day}, {when.year}"


def _numbers(text):
    return sorted(n.replace(",", "") for n in _NUMBERISH.findall(text))


def _value_text(kind, raw):
    """The figure to write, checked. Money goes through cents() so rounding stays in maya/cost.py."""
    raw = (raw or "").strip().lstrip("$").rstrip("%").strip()
    if kind in ("money", "percent", "days"):
        try:
            number = Decimal(raw)
        except InvalidOperation:
            raise ValueError("The new value must be a number.") from None
        if number <= 0:
            raise ValueError("The new value must be above zero.")
        if kind == "days" and number != number.to_integral_value():
            raise ValueError("A number of days must be a whole number.")
        if kind == "money":
            from maya.cost import cents
            return f"{cents(number):.2f}"
        return format(number.to_integral_value() if kind == "days" else number.normalize(), "f")
    if not raw:
        raise ValueError("Enter the new value.")
    return raw


def _plain(text):
    if "\n" in text or "\r" in text:
        raise ValueError("Use a single line of text.")
    try:
        text.encode("latin-1")
    except UnicodeEncodeError:
        raise ValueError("Use plain characters only.") from None
    return text


def _edit_sentence(rule, spec, value):
    """The rule sentence with the one figure replaced, or None when this section has no such figure."""
    kind = spec["value"]
    for pattern in spec.get("patterns", []):
        found = re.search(pattern, rule.text)
        if found:
            new = _value_text(kind, value)
            return rule.text[:found.start(1)] + _plain(new) + rule.text[found.end(1):]
    return None


def _reword(rule, spec, value):
    """Wording only: the presenter's sentence, or the configured swaps. Every number must survive."""
    if value.strip():
        new = _plain(value.strip())
    else:
        new = rule.text
        for old, replacement in spec.get("swaps", []):
            new = new.replace(old, replacement)
    if new == rule.text:
        return None
    if _numbers(new) != _numbers(rule.text):
        raise ValueError("A wording-only change must keep every number the same.")
    return new


def _next_number(texts):
    """Bulletin number one above the highest in use, published or held back, in the same format."""
    best = None
    for text in texts:
        found = re.search(r"^Bulletin number:\s*(\S+)\s*$", text, re.M)
        split = re.match(r"^(.*?)(\d+)$", found.group(1)) if found else None
        if split and (best is None or int(split.group(2)) > int(best[1])):
            best = split.groups()
    if best is None:
        raise ValueError("The latest bulletin has no bulletin number.")
    return f"{best[0]}{int(best[1]) + 1:0{len(best[1])}d}"


def publish_custom(cfg, jurisdiction, change_type, value="", effective_date=None):
    """Publish the next version of the latest bulletin with exactly one section changed (TXT, PDF, index).

    effective_date None leaves the Effective Date line out. The rehearsed held-back version is untouched.
    """
    site_cfg = cfg["site"]
    spec = (site_cfg.get("custom_changes") or {}).get(change_type)
    if spec is None:
        raise ValueError(f"Unknown change type: {change_type}")
    if jurisdiction not in cfg["jurisdictions"]:
        raise ValueError(f"Unknown jurisdiction: {jurisdiction}")
    site_dir, held_dir, _, _ = _paths(cfg)
    published = sorted(site_dir.glob("*.txt"), key=lambda p: _version(p.stem))
    if not published:
        raise ValueError("No bulletin is published yet.")
    latest = published[-1]
    text = latest.read_text(encoding="utf-8")
    front, rules = _parse(text)

    wording = spec["value"] == "sentence"
    keywords = [k.lower() for k in spec.get("title_keywords", [])]
    excluded = [k.lower() for k in spec.get("exclude_keywords", [])]
    target = new_text = None
    for rule in rules:
        title = rule.title.lower()
        if (rule.jurisdiction or "").casefold() != jurisdiction.casefold():
            continue
        if keywords and not any(k in title for k in keywords) or any(k in title for k in excluded):
            continue
        new_text = _reword(rule, spec, value) if wording else _edit_sentence(rule, spec, value)
        if new_text is not None:
            target = rule
            break
    if target is None:
        raise ValueError(f"No {spec['label'].lower()} section in {jurisdiction} can take that change.")

    target.text = new_text
    if not wording:  # wording only keeps the section's own date
        target.date = _date_text(effective_date) if effective_date else None

    version = max(_version(p.stem) for p in [*published, *held_dir.glob("*.txt")]) + 1
    number = _next_number([p.read_text(encoding="utf-8") for p in [*published, *held_dir.glob("*.txt")]])
    old_number = re.search(r"^Bulletin number:\s*(\S+)\s*$", text, re.M).group(1)
    old_issued = re.search(r"^Issued:\s*(.+?)\s*$", text, re.M).group(1)
    issued = _date_text(date.fromisoformat(str(cfg["as_of_date"])))
    for i, line in enumerate(front):
        if line.startswith("Issued:"):
            front[i] = f"Issued: {issued}"
        elif line.startswith("Supersedes:"):
            front[i] = f"Supersedes: Bulletin {old_number}, issued {old_issued}, in full."
        else:
            front[i] = line.replace(old_number, number)

    marker = site_cfg.get("custom_marker", "custom")
    prefix = re.sub(rf"(?:_{re.escape(marker)})?_v\d+$", "", latest.stem)
    stem = f"{prefix}_{marker}_v{version}"
    txt, pdf = site_dir / f"{stem}.txt", site_dir / f"{stem}.pdf"
    try:
        _write_pdf(front, rules, pdf)
        txt.write_text(_render(front, rules), encoding="utf-8")
        build_index(cfg)
    except Exception:  # never leave a half-published version behind
        txt.unlink(missing_ok=True)
        pdf.unlink(missing_ok=True)
        build_index(cfg)
        raise
    return Published([txt.name, pdf.name], target.number, target.title, target.jurisdiction)
