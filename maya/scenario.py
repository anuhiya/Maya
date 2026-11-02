"""Proposed bill scenarios: if enacted, if not enacted (A9).

A bill is a document stage, never a review status. Code reads the bill's section, matches employees with the
same rule as every finding, and calculates the money. The AI only writes a summary, and code checks its quotes.
Scenario totals are kept apart: nothing here is ever added to the in-effect or coming totals.
"""
import json
import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path

from maya import cost, sources
from maya.ai import prompts
from maya.ai.llm import LLM
from maya.employees import load_employees
from maya.impact import match_finding
from maya.ingest import read_document
from maya.models import Category, ChangeType, Employee, EmploymentType, Finding, ImpactResult, ImpactRow, Timing
from maya.pipeline import _source_for
from maya.split import read_sections
from maya.timing import classify, parse_date

_MONEY = re.compile(r"\$(\d[\d,]*(?:\.\d+)?)")
HOURLY = (EmploymentType.HOURLY_FULL_TIME, EmploymentType.HOURLY_PART_TIME)
AI_LABEL = "AI scenario summary. Numbers are calculated by code. A reviewer decides."
TOTALS_NOTE = "Scenario totals are separate. They are never added to the in-effect or coming totals."
NEEDS_INPUT = "Needs reviewer input"


@dataclass
class Bill:
    path: Path
    name: str
    number: str
    stage: str
    jurisdiction: str
    title: str
    section: str
    effective_date: str
    new_value: Decimal
    text: str
    rule: str
    fingerprint: str
    trusted: bool
    source_file: str
    kind: str = "illustrative"  # illustrative or real
    meta: dict = field(default_factory=dict)  # for a real bill: official link, retrieval date, status


@dataclass
class RealBill:
    """A real pending bill: official text saved unaltered, a header file and the facts read from the text.

    Every quote behind a fact is checked word for word against the saved text (V1). A bill that does not cover
    this company has no Bill and no cost: it shows what it covers instead.
    """

    folder: Path
    header: dict
    facts: dict
    text: str
    fingerprint: str
    quotes: list[tuple[str, bool]]
    bill: Bill | None

    @property
    def applicable(self) -> bool:
        return self.bill is not None

    @property
    def label(self) -> str:
        """A readable name for the selector: jurisdiction, bill number and short title."""
        return f"{self.facts['jurisdiction']}, {self.header['bill_number']}, {self.header['short_title']}"

    @property
    def scope(self) -> str:
        return self.facts.get("covers", {}).get("text", "")


@dataclass
class Baseline:
    """The minimum already coming for the same rule, from the main policy pair's newer bulletin."""

    value: Decimal
    effective_date: str
    source_file: str


@dataclass
class Scenario:
    bill: Bill
    timing: Timing
    baseline: Baseline | None
    rows: list[ImpactRow]
    wage_now: dict[str, Decimal]
    wage_after: dict[str, Decimal]
    affected: list[ImpactRow] = field(default_factory=list)
    weekly: Decimal = Decimal("0.00")
    yearly: Decimal = Decimal("0.00")
    tax_weekly: Decimal = Decimal("0.00")
    tax_yearly: Decimal = Decimal("0.00")

    @property
    def total_weekly(self) -> Decimal:
        return self.weekly + self.tax_weekly

    @property
    def total_yearly(self) -> Decimal:
        return self.yearly + self.tax_yearly

    @property
    def by_jurisdiction(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for r in self.affected:
            counts[r.jurisdiction] = counts.get(r.jurisdiction, 0) + 1
        return counts

    @property
    def review(self) -> list[ImpactRow]:
        return [r for r in self.rows if r.result is ImpactResult.NEEDS_REVIEW]

    @property
    def flags(self) -> list[ImpactRow]:
        return [r for r in self.rows if r.flags]


def proposed_dir(cfg: dict) -> Path:
    return cfg["_root"] / (cfg.get("proposed") or {}).get("dir", "data/policies/proposed")


def list_bills(cfg: dict) -> list[Path]:
    folder = proposed_dir(cfg)
    if not folder.is_dir():
        return []
    files = sorted(p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in (".txt", ".pdf"))
    names = {p.stem for p in files if p.suffix.lower() == ".txt"}
    return [p for p in files if p.suffix.lower() == ".txt" or p.stem not in names]


def real_dir(cfg: dict) -> Path:
    return proposed_dir(cfg) / "real"


def list_real_bills(cfg: dict) -> list[Path]:
    """Folders under proposed/real that hold a header.json, in name order."""
    folder = real_dir(cfg)
    if not folder.is_dir():
        return []
    found = [p for p in folder.iterdir() if p.is_dir() and (p / "header.json").is_file()]

    def order(p: Path) -> tuple:
        try:
            place = json.loads((p / "facts.json").read_text(encoding="utf-8")).get("jurisdiction", "")
        except (OSError, ValueError):
            place = ""
        places = cfg["jurisdictions"]
        return (places.index(place) if place in places else len(places), p.name)

    return sorted(found, key=order)  # the company's places first, in config order, then everything else


def real_label(folder: Path) -> str:
    """The selector label for a bill folder, without loading its text."""
    try:
        header = json.loads((folder / "header.json").read_text(encoding="utf-8"))
        facts = json.loads((folder / "facts.json").read_text(encoding="utf-8"))
        return f"{facts['jurisdiction']}, {header['bill_number']}, {header['short_title']}"
    except (OSError, ValueError, KeyError):
        return folder.name


def _fact_quotes(node) -> list[str]:
    found = []
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "quote" and isinstance(value, str):
                found.append(value)
            elif key == "not_priced_quotes" and isinstance(value, list):
                found += [q for q in value if isinstance(q, str)]
            else:
                found += _fact_quotes(value)
    elif isinstance(node, list):
        for item in node:
            found += _fact_quotes(item)
    return found


def load_real_bill(folder: Path, cfg: dict) -> RealBill:
    """Read a real bill folder. Raises ValueError when the header or facts file is missing or unreadable."""
    try:
        header = json.loads((folder / "header.json").read_text(encoding="utf-8"))
        facts = json.loads((folder / "facts.json").read_text(encoding="utf-8"))
        text = (folder / header["text_file"]).read_text(encoding="utf-8")
        official = folder / header["original_file"]
        fingerprint = sources.fingerprint(official)
    except (OSError, ValueError, KeyError) as err:
        raise ValueError(f"{folder.name} is not a complete real bill folder ({type(err).__name__})") from None
    quotes = verify_quotes(text, _fact_quotes(facts))
    bill = None
    rule = facts.get("rule", {})
    covered = set(facts.get("covers_jurisdictions", [])) & set(cfg["jurisdictions"])
    if covered and rule.get("wage") and rule.get("effective_date"):  # a bill that covers none of our places is not priced
        root = cfg["_root"].resolve()
        saved = (folder / header["text_file"]).resolve()
        bill = Bill(saved, header["bill_number"], header["bill_number"], "Proposed, not enacted (real bill)",
                    facts["jurisdiction"], rule.get("title", "Minimum Wage"), rule.get("section", ""),
                    rule["effective_date"], Decimal(rule["wage"]), text, rule.get("quote", ""), fingerprint, False,
                    str(saved.relative_to(root)) if saved.is_relative_to(root) else str(saved), kind="real",
                    meta={"official_url": header["official_url"], "text_url": header.get("text_url", ""),
                          "date_retrieved": header["date_retrieved"], "status": header["status_as_of_retrieval"],
                          "sponsor": header.get("sponsor", ""), "title": header["title"], "trust": header["trust"]})
    return RealBill(folder, header, facts, text, fingerprint, quotes, bill)


def _head(text: str, label: str) -> str:
    found = re.search(rf"^{label}:\s*(.+?)\s*$", text, re.M)
    return found.group(1) if found else ""


def load_bill(path: Path, cfg: dict) -> Bill:
    """Read one proposed bill: the first section with a dollar amount in its rule sentence."""
    text = read_document(path)
    for section in read_sections(path):
        rule = section.text.split("\n")[-1]
        money = _MONEY.search(rule)
        if money and section.jurisdiction and section.effective_date:
            source = _source_for(path, cfg)
            root = cfg["_root"].resolve()
            resolved = Path(path).resolve()
            number = _head(text, "Bill number") or path.stem
            return Bill(path, f"Proposed bill {number}", number, _head(text, "Stage") or "Proposed",
                        section.jurisdiction, section.title, section.number, section.effective_date,
                        Decimal(money.group(1).replace(",", "")), text, rule, sources.fingerprint(path),
                        bool(source and source.get("trusted")),
                        str(resolved.relative_to(root)) if resolved.is_relative_to(root) else str(path))
    raise ValueError(f"{Path(path).name} has no section with a jurisdiction, an effective date and a dollar amount.")


def baseline_for(cfg: dict, bill: Bill) -> Baseline | None:
    """The minimum already coming for the same jurisdiction and section title, if it starts before the bill."""
    newer = cfg["_root"] / cfg["policies"]["main_pair"]["new"]
    when = parse_date(bill.effective_date)
    for s in read_sections(newer):
        rule = s.text.split("\n")[-1]
        money = _MONEY.search(rule)
        starts = parse_date(s.effective_date)
        if (s.jurisdiction == bill.jurisdiction and s.title == bill.title and money and starts
                and (when is None or starts <= when)):  # no stated date: the bulletin minimum is treated as in place
            return Baseline(Decimal(money.group(1).replace(",", "")), s.effective_date or "", newer.name)
    return None


def compute(cfg: dict, bill: Bill, as_of: date, employees: list[Employee] | None = None) -> Scenario:
    """Match and price the bill. The wage used is the one after existing changes, so nothing is counted twice."""
    employees = employees if employees is not None else load_employees(cfg=cfg).employees
    base = baseline_for(cfg, bill)
    wage_now = {e.employee_id: e.hourly_wage for e in employees}
    shifted = []
    for e in employees:
        if base and e.jurisdiction == bill.jurisdiction and e.employment_type in HOURLY:
            shifted.append(e.model_copy(update={"hourly_wage": max(e.hourly_wage, base.value)}))
        else:
            shifted.append(e)
    wage_after = {e.employee_id: e.hourly_wage for e in shifted}
    timing = classify(bill.effective_date, as_of)
    finding = Finding(finding_id="scenario", section=bill.section, jurisdiction=bill.jurisdiction,
                      category=Category.WAGES, change_type=ChangeType.SUBSTANTIVE, new_value=bill.new_value,
                      unit="dollars per hour", effective_date=bill.effective_date, timing=timing,
                      new_rule=bill.rule, source_file=bill.source_file)
    rows = match_finding(finding, shifted, cfg)
    sc = Scenario(bill, timing, base, rows, wage_now, wage_after)
    sc.affected = [r for r in rows if r.result is ImpactResult.AFFECTED and r.weekly_increase is not None]
    sc.weekly = sum((r.weekly_increase for r in sc.affected), Decimal("0.00"))
    sc.yearly = cost.annualized(sc.weekly)[0]
    sc.tax_weekly = cost.employer_tax(sc.weekly)
    sc.tax_yearly = cost.employer_tax(sc.yearly)
    return sc


def prepare_list(sc: Scenario) -> list[str]:
    """What to prepare, derived from the bill and the numbers."""
    b = sc.bill
    items = [
        (f"Update the {b.jurisdiction} {b.title.lower()} rate table to ${b.new_value:,.2f} from {b.effective_date}."
         if parse_date(b.effective_date) else
         f"Prepare the {b.jurisdiction} {b.title.lower()} rate table for ${b.new_value:,.2f}; no effective date is stated."),
        f"Send the {len(sc.affected)} affected {b.jurisdiction} employees a notice of their new rate.",
        (f"Set the effective date {b.effective_date} in payroll so the new rate starts on that day."
         if parse_date(b.effective_date) else
         "Wait for an effective date: the saved text does not state one, so nothing can be scheduled yet."),
        f"Add a budget line of ${sc.total_weekly:,.2f} a week (${sc.total_yearly:,.2f} a year) including the employer tax estimate.",
    ]
    items += [f"Review {r.employee_id}: works part of the week in {b.jurisdiction}; confirm the split of hours." for r in sc.review]
    items += [f"Review the classification of {r.employee_id} (contractor paid below the proposed minimum)." for r in sc.flags]
    return items


def facts(sc: Scenario) -> dict:
    """The numbers code calculated, given to the AI to copy and nothing else."""
    b = sc.bill
    return {"bill": b.name, "jurisdiction": b.jurisdiction, "proposed minimum": f"${b.new_value:,.2f} an hour",
            "effective date": b.effective_date, "affected employees": len(sc.affected),
            "weekly cost": f"${sc.weekly:,.2f}", "yearly cost": f"${sc.yearly:,.2f}",
            "employer tax estimate weekly": f"${sc.tax_weekly:,.2f}", "total weekly": f"${sc.total_weekly:,.2f}",
            "total yearly": f"${sc.total_yearly:,.2f}"}


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def verify_quotes(bill_text: str, quotes: list[str]) -> list[tuple[str, bool]]:
    """V1: a quote is verified only if it appears word for word in the bill."""
    body = _norm(bill_text)
    return [(q, bool(q.strip()) and _norm(q) in body) for q in quotes]


_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")


def summary_problem(text: str, allowed: dict, bill_text: str) -> str | None:
    """A summary may only use numbers that are in the code's facts or in the bill itself."""
    ok = {n.replace(",", "") for n in _NUMBER.findall(" ".join(str(v) for v in allowed.values()) + " " + bill_text)}
    stray = [n for n in _NUMBER.findall(text) if n.replace(",", "").rstrip(".") not in ok]
    if re.search(r"approved|approves|has been enacted|is law\b", text, re.IGNORECASE):
        return "it says something is approved or enacted"
    return f"the number {stray[0]} is not in the data" if stray else None


def built_summary(sc: Scenario) -> str:
    b = sc.bill
    return (f"{b.name} would set the {b.jurisdiction} {b.title.lower()} at ${b.new_value:,.2f} an hour from "
            f"{b.effective_date}. It is proposed and not yet law. If it passes, {len(sc.affected)} employees would "
            f"cost ${sc.weekly:,.2f} a week more, ${sc.total_weekly:,.2f} with the employer tax estimate.")


def ai_summary(llm: LLM, sc: Scenario) -> dict:
    """Ask the model for a summary, then check it. Returns text, verified quotes and flagged quotes."""
    system, user = prompts.scenario_summary(sc.bill.text, facts(sc))
    answer = llm.call("scenario_summary", system, user, role="planner").answer
    problem = summary_problem(answer.summary, facts(sc), sc.bill.text)
    checked = verify_quotes(sc.bill.text, answer.quotes)
    return {"text": built_summary(sc) if problem else answer.summary, "replaced": problem,
            "verified": [q for q, ok in checked if ok], "flagged": [q for q, ok in checked if not ok]}


def scenario_csv(sc: Scenario) -> str:
    import csv
    import io
    out = io.StringIO()
    w = csv.writer(out, lineterminator="\n")
    w.writerow(["bill", "stage", "jurisdiction", "effective_date", "employee_id", "result", "wage_now",
                "wage_after_existing_changes", "target_wage", "hours_per_week", "weekly_difference", "calculation"])
    for r in sorted(sc.rows, key=lambda r: r.employee_id):
        if r.result is ImpactResult.NOT_AFFECTED:
            continue
        w.writerow([sc.bill.number, "Proposed", sc.bill.jurisdiction, sc.bill.effective_date, r.employee_id,
                    r.result.value, sc.wage_now[r.employee_id], sc.wage_after[r.employee_id], sc.bill.new_value,
                    r.weekly_hours.normalize(), "" if r.weekly_increase is None else f"{r.weekly_increase:.2f}",
                    r.calculation])
    w.writerow([])
    w.writerow(["total_weekly", f"{sc.weekly:.2f}", "employer_tax_weekly", f"{sc.tax_weekly:.2f}",
                "total_with_tax_weekly", f"{sc.total_weekly:.2f}"])
    w.writerow(["total_yearly", f"{sc.yearly:.2f}", "employer_tax_yearly", f"{sc.tax_yearly:.2f}",
                "total_with_tax_yearly", f"{sc.total_yearly:.2f}"])
    w.writerow([TOTALS_NOTE])
    return out.getvalue()


def scenario_markdown(sc: Scenario, summary: dict | None = None, note: str = "") -> str:
    b = sc.bill
    real = ([f"- Real bill: {b.meta['title']}", f"- Official page: {b.meta['official_url']}",
             f"- Retrieved: {b.meta['date_retrieved']}", f"- Status at retrieval: {b.meta['status']}",
             f"- Trust: {b.meta['trust']}", "- Bill text is real; the workforce is synthetic; status may have changed since retrieval."]
            if b.kind == "real" else ["- Illustrative bill: the text and figures are synthetic."])
    lines = [f"# {b.name}", "", "Proposed, not yet law.", "", *real,
             f"- Jurisdiction: {b.jurisdiction}", f"- Proposed effective date: {b.effective_date}",
             f"- Proposed minimum: ${b.new_value:,.2f} an hour", f"- Source: {b.source_file}",
             f"- Fingerprint: {b.fingerprint[:12]}", "", "## If it is enacted", "",
             f"- Affected employees: {len(sc.affected)}", f"- Weekly cost: ${sc.weekly:,.2f}",
             f"- Yearly cost: ${sc.yearly:,.2f}", f"- Employer tax estimate: ${sc.tax_weekly:,.2f} a week, ${sc.tax_yearly:,.2f} a year",
             f"- Total: ${sc.total_weekly:,.2f} a week, ${sc.total_yearly:,.2f} a year", "",
             "## If it is not enacted", "", "- Status quo, change in cost $0.00",
             f"- Risk of not preparing (back pay, penalties): {NEEDS_INPUT}"]
    if note.strip():
        lines.append(f"- Reviewer note: {note.strip()}")
    lines += ["", "## What to prepare", ""] + [f"- {x}" for x in prepare_list(sc)]
    if summary:
        lines += ["", f"## {AI_LABEL}", "", summary["text"]]
        lines += [f'- Verified quote: "{q}"' for q in summary["verified"]]
        lines += [f"- Not shown as a quote (not found word for word in the bill): {q}" for q in summary["flagged"]]
    lines += ["", TOTALS_NOTE, ""]
    return "\n".join(lines)
