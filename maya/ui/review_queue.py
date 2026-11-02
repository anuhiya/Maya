"""Review queue page: filters, finding detail, decisions (B2, B4, B5, B6)."""
import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from difflib import SequenceMatcher
from pathlib import Path

import streamlit as st

from maya import cost, db, routing
from maya import export as csvs
from maya.ai.llm import LLM, LLMError, MissingSettingError
from maya.ai.replay import ReplayError
from maya.employees import load_employees
from maya.findings import CompareResult
from maya.impact import match_finding
from maya.ingest import ReadingError
from maya.models import Category, ChangeType, ImpactResult, ImpactRow, Status, Timing
from maya.pipeline import compare_documents
from maya.site import load_config
from maya.split import read_sections
from maya.timing import classify, parse_date
from maya.ui.style import chip, esc, md

GROUPS = ("Needs review", "Current", "Future")
CATEGORY_LABELS = {Category.WAGES: "Wages", Category.TAX_RATE: "Tax rate",
                   Category.FILING_DEADLINE: "Filing deadline", Category.REPORTING: "Reporting",
                   Category.UNCLEAR: "Unclear"}
TIMING_LABELS = {Timing.CURRENT: "In effect", Timing.FUTURE: "Future", Timing.UNKNOWN: "Unknown date"}
CHANGE_LABELS = {ChangeType.SUBSTANTIVE: "Substantive", ChangeType.WORDING_ONLY: "Wording only",
                 ChangeType.ADDED: "Added", ChangeType.REMOVED: "Removed"}
STATUS_LABELS = {Status.PENDING: "Pending", Status.APPROVED: "Approved", Status.DISMISSED: "Dismissed"}
RESULT_LABELS = {ImpactResult.AFFECTED: "Affected", ImpactResult.NOT_AFFECTED: "Not affected",
                 ImpactResult.EXCLUDED: "Excluded", ImpactResult.MATCHED_NO_ESTIMATE: "Covered, no estimate",
                 ImpactResult.NEEDS_REVIEW: "Needs review"}
FILTERS = {  # session key: (label, placeholder)
    "f_jurisdiction": ("Jurisdiction", "All jurisdictions"),
    "f_category": ("Change category", "All categories"),
    "f_status": ("Review status", "All statuses"),
    "f_timing": ("Timing", "All timing"),
}


@dataclass(frozen=True)
class Pair:
    label: str
    old: Path
    new: Path


@dataclass
class Comparison:
    result: CompareResult
    titles: dict[str, str]
    old_name: str


@dataclass
class Item:
    finding: object
    route: routing.Route
    rows: list[ImpactRow]
    status: Status
    title: str
    group: str


# ---- pairs and comparison -------------------------------------------------------------------

def policy_pairs(cfg: dict) -> list[Pair]:
    """Pairs from the config, then consecutive versions listed in the site index."""
    root = cfg["_root"]
    index_path = root / cfg["site"]["index_file"]
    docs = json.loads(index_path.read_text(encoding="utf-8"))["documents"] if index_path.exists() else []
    by_file = {d["file"]: d for d in docs}

    def label(old: Path, new: Path) -> str:
        a, b = by_file.get(old.name), by_file.get(new.name)
        if a and b:
            return f"{a['title']} to {b['bulletin_number']}"
        return f"{old.stem} to {new.stem}".replace("_", " ")

    pairs, seen = [], set()
    uploaded = st.session_state.get("upload_pair")  # set by the Agent activity page
    if uploaded:
        count = st.session_state.get("upload_count")
        found = f" ({count} findings)" if count is not None else ""
        pairs.append(Pair(f"Uploaded: {label(uploaded.old, uploaded.new)}{found}", uploaded.old, uploaded.new))
    for entry in (cfg.get("policies") or {}).values():
        old, new = root / entry["old"], root / entry["new"]
        pairs.append(Pair(label(old, new), old, new))
        seen.add((old.name, new.name))
    site_dir = root / cfg["site"]["dir"]
    ordered = sorted(docs, key=lambda d: d["version"])
    for a, b in zip(ordered, ordered[1:]):
        if (a["file"], b["file"]) not in seen:
            pairs.append(Pair(label(site_dir / a["file"], site_dir / b["file"]),
                              site_dir / a["file"], site_dir / b["file"]))
    return pairs


def replay_runs(cfg: dict) -> list[str]:
    """Saved runs in the replay folder, the main pair's first."""
    folder = cfg["_root"] / cfg["llm"]["replay_dir"]
    names = sorted(p.stem for p in folder.glob("*.json")) if folder.exists() else []
    return sorted(names, key=lambda n: n != "main_pair")


def _stamp(cfg: dict, pair: Pair) -> tuple:
    folder = cfg["_root"] / cfg["llm"]["replay_dir"]
    files = [pair.old, pair.new, *sorted(folder.glob("*.json"))]
    return tuple((str(p), p.stat().st_mtime_ns, p.stat().st_size) for p in files if p.exists())


def _compare(cfg: dict, pair: Pair) -> Comparison:
    """Compare with the saved runs; ask the live model only when none holds the answers and a key is set."""
    result = None
    for run in replay_runs(cfg):
        llm = LLM(cfg=cfg, env={"MAYA_LLM_PROVIDER": "replay", "MAYA_REPLAY_RUN": run})
        try:
            result = compare_documents(pair.old, pair.new, llm=llm, cfg=cfg)
            break
        except ReplayError:
            continue
    if result is None:
        try:
            result = compare_documents(pair.old, pair.new, llm=LLM(cfg=cfg), cfg=cfg)
        except MissingSettingError as err:
            raise MissingSettingError(f"No saved run covers {pair.new.name}. {err}") from None
    titles = {s.number: s.title for s in read_sections(pair.old)}
    titles.update({s.number: s.title for s in read_sections(pair.new)})
    return Comparison(result, titles, pair.old.name)


@st.cache_data(show_spinner="Reading both versions")
def _cached_compare(_cfg: dict, pair: Pair, stamp: tuple) -> Comparison:
    return _compare(_cfg, pair)


# ---- view model -----------------------------------------------------------------------------

def group_of(finding, route: routing.Route, status: Status) -> str:
    """Needs review while a person still has to decide; otherwise by timing."""
    if (status is Status.PENDING and not route.ready and finding.change_type is not ChangeType.WORDING_ONLY):
        return "Needs review"
    return "Future" if finding.timing is Timing.FUTURE else "Current"


def build_items(cfg: dict, comparison: Comparison, as_of: date, employees, conn) -> list[Item]:
    items = []
    jurisdictions = cfg["jurisdictions"]
    for original in comparison.result.findings:
        new_timing = (Timing.UNKNOWN if original.change_type is ChangeType.REMOVED
                      else classify(original.effective_date, as_of))
        finding = original.model_copy(update={"timing": new_timing})
        route = routing.route(finding, trusted=comparison.result.trusted, jurisdictions=jurisdictions)
        if finding.change_type is ChangeType.WORDING_ONLY:
            route = routing.Route(ready=False, label=None, reasons=[])
        status = db.current_status(conn, finding.finding_id)
        rows = match_finding(finding, employees, cfg)
        items.append(Item(finding, route, rows, status, comparison.titles.get(finding.section, ""),
                          group_of(finding, route, status)))
    return items


def money(value: Decimal) -> str:
    return f"${value:,.2f}"


def summary(items: list[Item]) -> dict:
    rows = [r for i in items for r in i.rows]
    totals = cost.sum_by_timing(rows)
    in_effect, coming = totals[Timing.CURRENT], totals[Timing.FUTURE]
    affected_now = {r.employee_id for r in rows if r.result is ImpactResult.AFFECTED and r.timing is Timing.CURRENT}
    wording = sum(i.finding.change_type is ChangeType.WORDING_ONLY for i in items)
    return {
        "found": len(items), "wording": wording, "other": len(items) - wording,
        "need": sum(i.group == "Needs review" for i in items),
        "ready": sum(i.route.ready and i.status is Status.PENDING for i in items),
        "in_effect": in_effect, "coming": coming, "employees_now": len(affected_now),
        "annual": cost.annualized(in_effect), "annual_coming": cost.annualized(coming),
    }


def apply_filters(items: list[Item], chosen: dict) -> list[Item]:
    def keep(i: Item) -> bool:
        f = i.finding
        return ((chosen["f_jurisdiction"] == FILTERS["f_jurisdiction"][1] or f.jurisdiction == chosen["f_jurisdiction"])
                and (chosen["f_category"] == FILTERS["f_category"][1] or CATEGORY_LABELS[f.category] == chosen["f_category"])
                and (chosen["f_status"] == FILTERS["f_status"][1] or STATUS_LABELS[i.status] == chosen["f_status"])
                and (chosen["f_timing"] == FILTERS["f_timing"][1] or TIMING_LABELS[f.timing] == chosen["f_timing"]))
    return [i for i in items if keep(i)]


# ---- wording helpers ------------------------------------------------------------------------

def fmt_value(value: Decimal | None, unit: str | None) -> str:
    if value is None:
        return "none"
    unit = (unit or "").lower()
    if "dollar" in unit:
        return money(value) + (" per hour" if "hour" in unit else "")
    if "percent" in unit:
        return f"{value.normalize():f}%"
    if "day" in unit:
        return f"{value.normalize():f} days"
    return f"{value.normalize():f} {unit}".strip()


def headline(i: Item) -> str:
    f, title = i.finding, i.title or f"Section {i.finding.section}"
    name = f"{f.jurisdiction} {title}"
    if f.change_type is ChangeType.ADDED:
        return f"{name} is a new section"
    if f.change_type is ChangeType.REMOVED:
        return f"{name} was removed"
    if f.change_type is ChangeType.WORDING_ONLY:
        return f"{name} was reworded, no facts changed"
    if f.old_value is not None and f.new_value is not None and f.old_value != f.new_value:
        text = f"{name} changes from {fmt_value(f.old_value, f.unit)} to {fmt_value(f.new_value, f.unit)}"
        n = sum(r.result is ImpactResult.AFFECTED for r in i.rows)
        return text + (f"; {n} employees fall below it" if n and f.category is Category.WAGES else "")
    return f"{name} has new or changed terms"


def days_label(i: Item, as_of: date) -> str:
    f = i.finding
    when = parse_date(f.effective_date)
    if f.timing is Timing.CURRENT:
        return "In effect"
    if f.timing is Timing.FUTURE and when:
        return f"in {(when - as_of).days} days"
    return "No date"


def old_date(f) -> str:
    m = re.search(r"^Effective Date:\s*(.+)$", f.old_excerpt or "", re.M | re.I)
    return m.group(1).strip() if m else "none"


def diff_html(old: str | None, new: str | None) -> tuple[str, str]:
    """Both texts as HTML with the words that differ marked: old struck through, new highlighted."""
    a, b = re.findall(r"\S+|\n", old or ""), re.findall(r"\S+|\n", new or "")

    def render(tokens, marks, tag):
        out, prev_nl = [], True
        for k, tok in enumerate(tokens):
            if tok == "\n":
                out.append("\n")
                prev_nl = True
                continue
            if not prev_nl:
                out.append(" ")
            out.append(f"<{tag}>{esc(tok)}</{tag}>" if k in marks else esc(tok))
            prev_nl = False
        return "".join(out)

    marks_a, marks_b = set(), set()
    for op, i1, i2, j1, j2 in SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if op != "equal":
            marks_a.update(k for k in range(i1, i2) if a[k] != "\n")
            marks_b.update(k for k in range(j1, j2) if b[k] != "\n")
    return render(a, marks_a, "del"), render(b, marks_b, "mark")


# ---- page parts -----------------------------------------------------------------------------

LANES = ("Ready to approve", "Needs decision", "Wording only or no action")
FIX_IN = {Category.WAGES: "Payroll pay rates", Category.TAX_RATE: "Tax settings",
          Category.FILING_DEADLINE: "Compliance calendar", Category.REPORTING: "Reporting process",
          Category.UNCLEAR: "To be decided"}
OWNER = {Category.WAGES: "Payroll Manager", Category.TAX_RATE: "Payroll Manager",
         Category.FILING_DEADLINE: "Compliance lead", Category.REPORTING: "Compliance lead",
         Category.UNCLEAR: "Reviewer"}
ACTION = {Category.WAGES: "Update the pay rate of each affected employee from the effective date.",
          Category.TAX_RATE: "Update the tax rate in the payroll settings from the effective date.",
          Category.FILING_DEADLINE: "Update the filing calendar so the report is filed by the new deadline.",
          Category.REPORTING: "Update the reporting process for the new requirement.",
          Category.UNCLEAR: "A reviewer reads the source and decides what to do."}


def lane_of(i: Item) -> str:
    if i.finding.change_type is ChangeType.WORDING_ONLY or i.status is not Status.PENDING:
        return LANES[2]
    return LANES[0] if i.route.ready else LANES[1]


def weekly_of(i: Item) -> Decimal:
    """Weekly dollars this finding adds, summed from the rows code priced."""
    return sum((r.weekly_increase for r in i.rows
                if r.result is ImpactResult.AFFECTED and r.weekly_increase is not None), Decimal("0.00"))


def short_title(i: Item) -> str:
    return f"Section {i.finding.section}  {i.title}".strip()


# ---- page parts -----------------------------------------------------------------------------

def render_cards(s: dict) -> None:
    annual, label = s["annual"]
    cards = [
        ("Changes found", str(s["found"]), "", f"{s['other']} substantive, added or removed, {s['wording']} wording only"),
        ("Need a decision", str(s["need"]), "review", "Sent to reviewer with a reason"),
        ("Ready to approve", str(s["ready"]), "", f"{s['ready']} waiting for one-click sign-off"),
        ("Weekly impact", money(s["in_effect"]), "",
         f"In effect: {s['employees_now']} employees, {money(annual)} {label}. "
         f"Coming: {money(s['coming'])}, not added to in effect"),
    ]
    html = "".join(f'<div class="mq-card"><div class="label">{esc(a)}</div>'
                   f'<div class="value {k}">{esc(b)}</div><div class="sub">{esc(d)}</div></div>'
                   for a, b, k, d in cards)
    st.markdown(f'<div class="mq-cards">{html}</div>', unsafe_allow_html=True)


def status_chip(status: Status) -> str:
    return chip(STATUS_LABELS[status], {Status.APPROVED: "good", Status.DISMISSED: "critical"}.get(status, ""))


def timing_chip(i: Item) -> str:
    return chip(TIMING_LABELS[i.finding.timing],
                {Timing.CURRENT: "good", Timing.FUTURE: "future", Timing.UNKNOWN: "review"}[i.finding.timing])


def render_list(items: list[Item], as_of: date, conn, reviewer: str,
                mode: routing.ApprovalMode = routing.ApprovalMode.PRE_APPROVE) -> None:
    """Review order: highest weekly dollars first, grouped by what a person has to do."""
    ready = [i for i in items if i.route.ready and i.status is Status.PENDING]
    # groups in the order a person works them; inside a group, highest weekly dollars first; one count down the list
    ordered = [i for lane in LANES for i in sorted((x for x in items if lane_of(x) == lane),
                                                    key=lambda x: (-weekly_of(x), x.finding.section))]
    rank = {i.finding.finding_id: n for n, i in enumerate(ordered, 1)}
    st.markdown('<div class="mq-sub" style="margin-top:0">Review order</div>', unsafe_allow_html=True)
    if mode is routing.ApprovalMode.AUTO_APPROVE:
        st.caption("Auto-approve is on: findings that pass the rule are approved automatically.")
        ready = []
    else:
        if st.button(f"Sign off {len(ready)} ready", key="signoff", type="primary",
                     disabled=not ready or not reviewer.strip()):
            try:
                routing.sign_off(conn, {i.finding.finding_id: i.route for i in ready}, reviewer.strip())
            except ValueError as err:
                st.session_state["flash"] = ("error", str(err))
            else:
                st.session_state["flash"] = ("success", f"Signed off {len(ready)} ready findings.")
            st.rerun()
        st.caption("Sign-off approves only findings that passed every check. Each is recorded with the checks "
                   "it passed. Numbered from the top; inside each group, highest weekly dollars first.")
    if ready and not reviewer.strip():
        st.caption("Open Review settings and enter your name to sign off.")
    for lane in LANES:
        members = [i for i in ordered if lane_of(i) == lane]
        if not members:
            continue
        st.markdown(f'<div class="mq-group">{lane} ({len(members)})</div>', unsafe_allow_html=True)
        for i in members:
            fid, f = i.finding.finding_id, i.finding
            picked = st.session_state.get("selected_id") == fid
            with st.container(key=f"{'rowsel' if picked else 'row'}_{fid}"):
                st.button(md(f"{rank[fid]}. {short_title(i)}"), key=f"pick_{fid}", width="stretch",
                          type="tertiary", on_click=lambda fid=fid: st.session_state.update(selected_id=fid))
                dollars = f"{money(weekly_of(i))} a week" if weekly_of(i) else "No pay change"
                st.markdown(f'<div class="mq-meta">{esc(f.jurisdiction)}, <b>{esc(dollars)}</b><br>'
                            f'{timing_chip(i)}{status_chip(i.status)}</div>', unsafe_allow_html=True)


def check_chips(i: Item, trusted: bool, jurisdictions: list[str]) -> str:
    """One chip per check the routing rule reads, with a tick or cross and the word."""
    f = i.finding
    names = {"V1": "V1 quotes match the source", "V2": "V2 numbers recomputed", "V3": "V3 consistent"}
    checks = [(names.get(c.check, c.check), c.passed, c.detail) for c in f.check_results]
    checks += [("Trusted source", trusted, ""), ("Effective date readable", parse_date(f.effective_date) is not None, ""),
               ("Jurisdiction known", f.jurisdiction in jurisdictions, "")]
    return "".join(chip(f"{'✓' if ok else '✗'} {name}: {'passed' if ok else 'failed'}", "good" if ok else "critical")
                   for name, ok, _ in checks)


def render_why(i: Item, comparison: Comparison, cfg: dict) -> None:
    f = i.finding
    st.markdown('<div class="mq-sub">Why it was routed this way</div>', unsafe_allow_html=True)
    st.markdown(check_chips(i, comparison.result.trusted, cfg["jurisdictions"]), unsafe_allow_html=True)
    if f.change_type is ChangeType.WORDING_ONLY:
        body = "Wording only: no value, date, unit or scope changed, so nobody is affected and nothing costs money."
    elif i.route.ready:
        body = f"{routing.READY_LABEL}: " + "; ".join(i.route.passed_conditions) + "."
    else:
        body = "A person must decide: " + "; ".join(r.lower() for r in i.route.reasons) + "."
    st.caption(md(body))
    failed = [c for c in f.check_results if not c.passed]
    if f.flags or failed:
        lines = [fl.reason for fl in f.flags] + [f"Check {c.check} failed: {c.detail}" for c in failed]
        st.markdown('<div class="mq-box held"><div class="label">Held for review: not guessed</div>'
                    + "<br>".join(esc(x) for x in lines) + "</div>", unsafe_allow_html=True)


def render_rules(i: Item) -> None:
    f = i.finding
    old_h, new_h = diff_html(f.old_excerpt, f.new_excerpt)
    left, right = st.columns(2)
    left.markdown(f'<div class="mq-exc old"><div class="src">Previous rule. Removed words are struck through.'
                  f'</div>{old_h or "No previous rule: this section is new."}</div>', unsafe_allow_html=True)
    right.markdown(f'<div class="mq-exc new"><div class="src">Updated rule. Added words are highlighted.'
                   f'</div>{new_h or "No updated rule: this section was removed."}</div>', unsafe_allow_html=True)


def render_key_facts(i: Item) -> None:
    f = i.finding
    n_affected = sum(r.result is ImpactResult.AFFECTED for r in i.rows)
    pairs = [("Jurisdiction", f.jurisdiction), ("Section", f"{f.section} {i.title}".strip()),
             ("Category", CATEGORY_LABELS[f.category]),
             ("Value", f"{fmt_value(f.old_value, f.unit)} to {fmt_value(f.new_value, f.unit)}"
              if f.old_value is not None or f.new_value is not None else "No value"),
             ("Effective date", f"{old_date(f)} to {f.effective_date or 'not found'}"),
             ("Employees affected", str(n_affected))]
    cells = "".join(f'<div class="k">{esc(k)}</div><div class="v">{esc(v)}</div>' for k, v in pairs)
    st.markdown(f'<div class="mq-kv">{cells}</div>', unsafe_allow_html=True)


def render_money(i: Item) -> None:
    st.markdown('<div class="mq-sub">Financial impact</div>', unsafe_allow_html=True)
    affected = [r for r in i.rows if r.result is ImpactResult.AFFECTED and r.weekly_increase is not None]
    if not affected:
        text = ("No pay change: nobody is affected." if i.rows or i.finding.change_type is ChangeType.WORDING_ONLY
                else f"No current {i.finding.jurisdiction} employees are matched by this change.")
        st.markdown(f'<div class="mq-bignum">No pay change</div><div class="mq-meta">{esc(text)}</div>',
                    unsafe_allow_html=True)
        return
    total = weekly_of(i)
    annual, label = cost.annualized(total)
    first = min(affected, key=lambda r: r.employee_id)
    st.markdown(f'<div class="mq-bignum">{esc(money(total))} <span>a week, {esc(TIMING_LABELS[i.finding.timing].lower())}'
                f'</span></div><div class="mq-meta">{esc(money(annual))} {esc(label)}. {len(affected)} employees affected.'
                f'<br>Example, {esc(first.employee_id)}: <span class="mono">{esc(first.calculation)}</span></div>',
                unsafe_allow_html=True)


def render_action(i: Item) -> None:
    f = i.finding
    st.markdown('<div class="mq-sub">Recommended action</div>', unsafe_allow_html=True)
    st.markdown(esc(f.recommended_action or ACTION[f.category]))
    st.markdown(chip(f"Owner: {f.owner or OWNER[f.category]}") + chip(f"Fix in: {FIX_IN[f.category]}"),
                unsafe_allow_html=True)


def render_by_hand(i: Item) -> None:
    affected = [r for r in i.rows if r.result is ImpactResult.AFFECTED and r.weekly_increase is not None]
    with st.expander("Check by hand"):
        if affected:
            r = min(affected, key=lambda r: r.employee_id)
            st.markdown("Weekly increase = gap x regular hours + gap x 1.5 x overtime hours, where gap is the new "
                        "minimum minus the wage and regular hours stop at 40.")
            st.markdown(f"Real numbers, {r.employee_id}: wage ${r.hourly_wage:.2f}, new minimum "
                        f"${r.new_minimum:.2f}, {r.weekly_hours.normalize():f} hours a week.")
            st.code(r.calculation, language=None)
            st.caption(md(f"All {len(affected)} affected employees add up to {money(weekly_of(i))} a week. "
                          f"Annualized: weekly x 52."))
        else:
            st.caption("This change has no pay calculation to check.")
        fid = i.finding.finding_id
        done = fid in st.session_state.setdefault("hand_checked", set())
        if st.checkbox("I checked this by hand", value=done, key=f"hand_{fid}"):
            st.session_state["hand_checked"].add(fid)
        else:
            st.session_state["hand_checked"].discard(fid)


def render_evidence(i: Item, comparison: Comparison) -> None:
    f = i.finding
    st.markdown('<div class="mq-sub">Evidence from the source</div>', unsafe_allow_html=True)
    old_h, new_h = diff_html(f.old_excerpt, f.new_excerpt)
    prev, upd = st.tabs(["Previous", "Updated"])
    prev.markdown(f'<div class="mq-exc old"><div class="src">Previous version: {esc(comparison.old_name)}, '
                  f'Section {esc(f.section)}</div>{old_h or "none"}</div>', unsafe_allow_html=True)
    upd.markdown(f'<div class="mq-exc new"><div class="src">Updated version: {esc(f.source_file)}, '
                 f'Section {esc(f.section)}</div>{new_h or "none"}</div>', unsafe_allow_html=True)


def render_facts(i: Item) -> None:
    f = i.finding
    rows = [("Jurisdiction", f.jurisdiction, f.jurisdiction),
            ("Category", CATEGORY_LABELS[f.category], CATEGORY_LABELS[f.category]),
            ("Value", fmt_value(f.old_value, f.unit), fmt_value(f.new_value, f.unit)),
            ("Effective date", old_date(f), f.effective_date or "No effective date found"
             if f.change_type is not ChangeType.REMOVED else "none"),
            ("Rule", f.old_rule or "none", f.new_rule or "none")]
    body = "".join(f'<tr><td>{esc(a)}</td><td class="mono">{esc(b)}</td><td class="mono"><b>{esc(c)}</b></td></tr>'
                   for a, b, c in rows)
    with st.expander("Extracted facts"):
        st.markdown('<table class="mq-table kv"><tr><th>Field</th>'
                    f'<th>Previous rule</th><th>Updated rule</th></tr>{body}</table>', unsafe_allow_html=True)


def render_impact(i: Item) -> None:
    rows = i.rows
    if not rows:
        st.caption(f"No current {i.finding.jurisdiction} employees are matched by this change.")
        return
    own = [r for r in rows if r.jurisdiction == i.finding.jurisdiction]
    counts = {}
    for r in own:
        counts[r.result] = counts.get(r.result, 0) + 1
    parts = ", ".join(f"{n} {RESULT_LABELS[k].lower()}" for k, n in counts.items())
    hybrid = len(rows) - len(own)
    note = f" Also listed for review: {hybrid} hybrid {'employee' if hybrid == 1 else 'employees'} working part of the week here." if hybrid else ""
    st.caption(md(f"{len(own)} {i.finding.jurisdiction} employees checked: {parts}.{note}"))
    order = {ImpactResult.AFFECTED: 0, ImpactResult.NEEDS_REVIEW: 1}
    heads = ["Employee", "Type", "Wage", "Hours a week", "Result", "Why", "Weekly increase", "Calculation"]
    wraps = {"Why", "Calculation"}
    body = ""
    for r in sorted(rows, key=lambda r: (order.get(r.result, 2), r.employee_id)):
        inc = f"{r.weekly_increase:.2f}" if r.weekly_increase is not None else ""
        cells = [(r.employee_id, "mono"), (r.employment_type.value.replace("_", " "), ""),
                 (f"{r.hourly_wage:.2f}", "mono"), (f"{r.weekly_hours.normalize():f}", "mono"),
                 (RESULT_LABELS[r.result], ""), (r.reason, ""), (inc, "mono"), (r.calculation, "mono")]
        body += "<tr>" + "".join(f'<td class="{k} {"calc" if h == "Calculation" else "wrap" if h in wraps else "nw"}">{esc(v)}</td>'
                                 for (v, k), h in zip(cells, heads)) + "</tr>"
    with st.expander("Employee by employee"):
        st.markdown('<div class="mq-scroll"><table class="mq-table"><tr>'
                    + "".join(f'<th class="{"calc" if h == "Calculation" else "wrap" if h in wraps else "nw"}">{h}</th>' for h in heads)
                    + f"</tr>{body}</table></div>", unsafe_allow_html=True)


def render_decision(i: Item, conn, reviewer: str) -> None:
    """The reviewer decision bar, last in the card: Approve, Dismiss (comment required) and Add comment."""
    fid = i.finding.finding_id
    st.markdown('<div class="mq-sub">Reviewer decision</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="mq-meta">Reviewing as: <b>{esc(reviewer.strip() or "not set")}</b>. Current status: '
                f'{status_chip(i.status)}</div>', unsafe_allow_html=True)
    with st.form(f"decide_{fid}", clear_on_submit=True):
        comment = st.text_area("Comment", placeholder="Required to dismiss")
        named = bool(reviewer.strip())
        a, b, c, _ = st.columns([1.1, 1.1, 1.7, 2.2])
        approve = a.form_submit_button("Approve", type="primary", disabled=not named)
        dismiss = b.form_submit_button("Dismiss", disabled=not named)
        note = c.form_submit_button("Add comment", disabled=not named)
        if not named:
            st.caption("Enter your name in Review settings to decide")
    if not (approve or dismiss or note):
        return
    if not reviewer.strip():
        st.error("Enter your name in Review settings before recording a decision.")
    elif dismiss and not comment.strip():
        st.error("A comment is required to dismiss a finding.")
    elif note and not comment.strip():
        st.error("Type a comment first.")
    else:
        status = Status.APPROVED if approve else Status.DISMISSED if dismiss else i.status
        try:
            routing.decide(conn, fid, status, reviewer.strip(), comment.strip())
        except sqlite3.IntegrityError as err:
            st.error(md(f"Could not save the decision: {err}"))
            return
        done = "Comment added to" if note else STATUS_LABELS[status]
        st.session_state["flash"] = ("success", f"{done} section {i.finding.section}.")
        st.rerun()


def render_history(conn, fid: str) -> None:
    st.markdown("<div class=\"mq-sub\">This finding's history</div>", unsafe_allow_html=True)
    decisions = db.history(conn, fid)
    if not decisions:
        st.caption("No decisions yet. The finding is pending.")
    for d in decisions:
        st.markdown(f'<div class="mq-hist"><span class="when">{esc(d.decided_at.strftime("%Y-%m-%d %H:%M"))} UTC</span> '
                    f'{status_chip(d.status)} by {esc(d.decided_by)}'
                    + (f"<br>{esc(d.comment)}" if d.comment else "") + "</div>", unsafe_allow_html=True)


def render_detail(i: Item, comparison: Comparison, as_of: date, conn, reviewer: str, cfg: dict) -> None:
    """One finding card, always in this order."""
    f = i.finding
    with st.container(border=True, key="finding_card"):
        badges = [chip(CATEGORY_LABELS[f.category]), chip(CHANGE_LABELS[f.change_type]), timing_chip(i)]
        if f.effective_date:
            badges.append(chip(f"Effective {f.effective_date}", "mono"))
        if i.route.ready and i.status is Status.PENDING:
            badges.append(chip(routing.READY_LABEL, "accent"))
        badges.append(status_chip(i.status))
        st.markdown("".join(badges), unsafe_allow_html=True)
        st.markdown(f'<div class="mq-head">{esc(headline(i))}</div>', unsafe_allow_html=True)
        if f.ai_reason:
            st.caption(md(f"AI reading: {f.ai_reason}"))
        render_key_facts(i)
        st.markdown('<div class="mq-sub">Previous rule and updated rule</div>', unsafe_allow_html=True)
        render_rules(i)
        render_money(i)
        render_impact(i)
        render_action(i)
        render_why(i, comparison, cfg)
        render_by_hand(i)
        render_evidence(i, comparison)
        render_facts(i)
        render_history(conn, f.finding_id)
        render_decision(i, conn, reviewer)


def render_trail(items: list[Item], conn, as_of) -> None:
    """Evidence trail: one line per finding, the hand-check counter and the findings CSV."""
    checked = st.session_state.get("hand_checked", set())
    mine = sum(i.finding.finding_id in checked for i in items)
    st.markdown('<div class="mq-sub">Evidence trail</div>', unsafe_allow_html=True)
    st.caption(f"{mine} of {len(items)} checked by hand this session.")
    lines = []
    for i in items:
        f = i.finding
        marks = " ".join(f"{c.check} {'passed' if c.passed else 'failed'}" for c in f.check_results)
        by_hand = "checked by hand" if f.finding_id in checked else "not checked by hand"
        lines.append(f'<div class="mq-hist"><b>Section {esc(f.section)} {esc(f.jurisdiction)}</b>: {esc(marks)}; '
                     f'{esc(lane_of(i).lower())}; {esc(STATUS_LABELS[i.status].lower())}; {by_hand}</div>')
    st.markdown("".join(lines), unsafe_allow_html=True)
    st.download_button("Download findings CSV", csvs.findings_csv([i.finding for i in items], conn),
                       key="dl_trail", mime="text/csv", file_name=csvs.file_name("findings", as_of))


# ---- the page -------------------------------------------------------------------------------

SHARED_KEYS = ("pair", "as_of", "reviewer", "auto_approve", "hand_checked", *FILTERS)


def keep_context() -> None:
    """Re-assign the shared widget keys so Streamlit keeps them when another page is shown."""
    for key in SHARED_KEYS:
        if key in st.session_state:
            st.session_state[key] = st.session_state[key]


def _clear_filters() -> None:
    for key, (_, placeholder) in FILTERS.items():
        st.session_state[key] = placeholder


def render(cfg: dict | None = None) -> None:
    cfg = cfg or load_config()
    keep_context()
    st.markdown('<div class="mq-kicker">Review queue</div>', unsafe_allow_html=True)
    pairs = policy_pairs(cfg)
    if not pairs:
        st.error("No policy pairs found. Check the policies and site sections of maya.config.yaml.")
        return

    c1, c2, c3 = st.columns([3, 1.4, 2.2], vertical_alignment="bottom")
    pair = c1.selectbox("Policy pair", pairs, format_func=lambda p: p.label, key="pair")
    if "as_of" not in st.session_state:
        st.session_state["as_of"] = parse_date(str(cfg["as_of_date"]))
    as_of = c2.date_input("As of", key="as_of")
    if "auto_approve" not in st.session_state:
        st.session_state["auto_approve"] = routing.approval_mode(cfg) is routing.ApprovalMode.AUTO_APPROVE
    with c3.popover("Review settings"):
        st.text_input("Reviewer name", key="reviewer", placeholder="Your name")
        st.toggle("Auto-approve", key="auto_approve",
                  help="Off is Pre-approve, the recommended mode: a person signs off findings that pass the rule. "
                       "On records them as approved by Auto-approved.")
    reviewer = st.session_state.get("reviewer", "")
    c3.caption(f"Reviewing as: {reviewer.strip() or 'not set'}")
    mode = (routing.ApprovalMode.AUTO_APPROVE if st.session_state["auto_approve"]
            else routing.ApprovalMode.PRE_APPROVE)

    try:
        comparison = _cached_compare(cfg, pair, _stamp(cfg, pair))
    except ReadingError as err:
        st.error(md(f"Could not read {pair.old.name} or {pair.new.name}: {err}"))
        return
    except (MissingSettingError, ReplayError, LLMError) as err:
        st.error(md(str(err)))
        return
    result = comparison.result
    st.markdown(f'<div class="mq-title">{esc(pair.label)}, {result.total} sections compared</div>',
                unsafe_allow_html=True)
    if not result.findings:
        st.info(f"No changes detected: {result.summary}. 0 findings, $0.00.")
        return

    loaded = load_employees(cfg=cfg)
    if loaded.problems:
        st.warning(f"{len(loaded.problems)} employee data problems found; see the employee file checks.")
    conn = db.connect(cfg["_root"] / cfg["state"]["database"])
    try:
        items = build_items(cfg, comparison, as_of, loaded.employees, conn)
        if routing.apply_mode(conn, mode, {i.finding.finding_id: i.route for i in items
                                           if i.status is Status.PENDING}):
            items = build_items(cfg, comparison, as_of, loaded.employees, conn)
        flash = st.session_state.pop("flash", None)
        if flash:
            getattr(st, flash[0])(md(flash[1]))
        render_cards(summary(items))

        cols = st.columns([1.4, 1.4, 1.3, 1.3, 1.5, 1.1], vertical_alignment="bottom")
        options = {
            "f_jurisdiction": cfg["jurisdictions"],
            "f_category": list(CATEGORY_LABELS.values()),
            "f_status": list(STATUS_LABELS.values()),
            "f_timing": list(TIMING_LABELS.values()),
        }
        for col, (key, (label, placeholder)) in zip(cols, FILTERS.items()):
            col.selectbox(label, [placeholder, *options[key]], key=key)
        shown = apply_filters(items, {k: st.session_state.get(k, FILTERS[k][1]) for k in FILTERS})
        cols[4].markdown(f'<div class="mq-meta" style="margin:0 0 0.6rem 0">{len(shown)} of {len(items)} findings. '
                         'Filters also apply to both exports.</div>', unsafe_allow_html=True)
        cols[5].button("Clear filters", key="clear_filters", on_click=_clear_filters)

        if not shown:
            st.info("No findings match these filters. Use Clear filters to see all.")
            return
        if st.session_state.get("selected_id") not in {i.finding.finding_id for i in shown}:
            st.session_state["selected_id"] = shown[0].finding.finding_id
        listing, detail = st.columns([1, 2.3])
        with listing:
            render_list(shown, as_of, conn, reviewer, mode)
        with detail:
            chosen = next(i for i in shown if i.finding.finding_id == st.session_state["selected_id"])
            render_detail(chosen, comparison, as_of, conn, reviewer, cfg)
        render_trail(shown, conn, as_of)
    finally:
        conn.close()
