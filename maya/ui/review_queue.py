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

def render_cards(s: dict) -> None:
    annual, label = s["annual"]
    cards = [
        ("Changes found", str(s["found"]), "", f"{s['other']} substantive, added or removed, {s['wording']} wording only"),
        ("Need a decision", str(s["need"]), "review", "Sent to reviewer with a reason"),
        ("Ready to approve", str(s["ready"]), "", f"{s['ready']} waiting for one-click sign-off"),
        ("Weekly increase in effect", money(s["in_effect"]), "",
         f"{s['employees_now']} employees, {money(annual)} {label}"),
        ("Weekly increase coming", money(s["coming"]), "",
         f"Not in the in-effect total, {money(s['annual_coming'][0])} {s['annual_coming'][1]}"),
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


def list_meta(i: Item) -> str:
    f = i.finding
    label = routing.READY_LABEL if i.route.ready and i.status is Status.PENDING else STATUS_LABELS[i.status]
    kind = "accent" if label == routing.READY_LABEL else {Status.APPROVED: "good", Status.DISMISSED: "critical"}.get(i.status, "")
    if f.change_type is ChangeType.WORDING_ONLY:
        note = "No action needed"
    elif i.route.reasons and i.status is Status.PENDING:
        note = f'<span class="why">Sent to reviewer: {esc(i.route.reasons[0].lower())}</span>'
    else:
        note = ""
    line = f"{esc(f.jurisdiction)}, {esc(CATEGORY_LABELS[f.category])}, {esc(CHANGE_LABELS[f.change_type])}"
    return f'<div class="mq-meta">{line}<br>{chip(label, kind)}{note}</div>'


def render_list(items: list[Item], as_of: date, conn, reviewer: str) -> None:
    ready = [i for i in items if i.route.ready and i.status is Status.PENDING]
    left, right = st.columns([1, 1.5], vertical_alignment="center")
    left.markdown(f"**{len(items)} findings shown**")
    if right.button(f"Sign off {len(ready)} ready", key="signoff", disabled=not ready or not reviewer.strip()):
        try:
            routing.sign_off(conn, {i.finding.finding_id: i.route for i in ready}, reviewer.strip())
        except ValueError as err:
            st.session_state["flash"] = ("error", str(err))
        else:
            st.session_state["flash"] = ("success", f"Signed off {len(ready)} ready findings.")
        st.rerun()
    if ready and not reviewer.strip():
        st.caption("Enter your name above to sign off.")
    for group in GROUPS:
        members = [i for i in items if i.group == group]
        if not members:
            continue
        st.markdown(f'<div class="mq-group">{group} ({len(members)})</div>', unsafe_allow_html=True)
        for i in members:
            fid = i.finding.finding_id
            picked = st.session_state.get("selected_id") == fid
            with st.container(key=f"{'rowsel' if picked else 'row'}_{fid}"):
                title, when = st.columns([3, 1.2], vertical_alignment="center")
                title.button(md(f"Section {i.finding.section}  {i.title}"), key=f"pick_{fid}", width="stretch",
                             type="tertiary", on_click=lambda fid=fid: st.session_state.update(selected_id=fid))
                when.markdown(f'<div class="mq-when">{esc(days_label(i, as_of))}</div>', unsafe_allow_html=True)
                st.markdown(list_meta(i), unsafe_allow_html=True)


def render_why(i: Item) -> None:
    f = i.finding
    if f.change_type is ChangeType.WORDING_ONLY:
        body = "Wording only: no value, date, unit or scope changed, so nobody is affected and nothing costs money."
    elif i.route.ready:
        body = f"{routing.READY_LABEL}: " + "; ".join(i.route.passed_conditions) + "."
    else:
        body = "A person must decide: " + "; ".join(r.lower() for r in i.route.reasons) + "."
    st.markdown(f'<div class="mq-box"><div class="label">Why it was routed this way</div>{esc(body)}</div>',
                unsafe_allow_html=True)
    failed = [c for c in f.check_results if not c.passed]
    if f.flags or failed:
        lines = [fl.reason for fl in f.flags] + [f"Check {c.check} failed: {c.detail}" for c in failed]
        st.markdown('<div class="mq-box held"><div class="label">Held for review: not guessed</div>'
                    + "<br>".join(esc(x) for x in lines) + "</div>", unsafe_allow_html=True)


def render_excerpts(i: Item, old_name: str) -> None:
    f = i.finding
    st.markdown('<div class="mq-sub">Evidence from the source</div>', unsafe_allow_html=True)
    old_h, new_h = diff_html(f.old_excerpt, f.new_excerpt)
    if f.old_excerpt:
        st.markdown(f'<div class="mq-exc old"><div class="src">Previous version: {esc(old_name)}, '
                    f'Section {esc(f.section)}</div>{old_h}</div>', unsafe_allow_html=True)
    if f.new_excerpt:
        st.markdown(f'<div class="mq-exc new"><div class="src">Updated version: {esc(f.source_file)}, '
                    f'Section {esc(f.section)}</div>{new_h}</div>', unsafe_allow_html=True)


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
    st.markdown('<div class="mq-sub">Extracted facts</div><table class="mq-table"><tr><th>Field</th>'
                f'<th>Previous rule</th><th>Updated rule</th></tr>{body}</table>', unsafe_allow_html=True)


def render_impact(i: Item) -> None:
    rows = i.rows
    st.markdown('<div class="mq-sub">Who is affected</div>', unsafe_allow_html=True)
    if not rows:
        st.caption(f"No current {i.finding.jurisdiction} employees are matched by this change.")
        return
    counts = {}
    for r in rows:
        counts[r.result] = counts.get(r.result, 0) + 1
    parts = ", ".join(f"{n} {RESULT_LABELS[k].lower()}" for k, n in counts.items())
    st.caption(md(f"{len(rows)} {i.finding.jurisdiction} employees checked: {parts}."))
    affected = [r for r in rows if r.result is ImpactResult.AFFECTED]
    if affected:
        total = cost.sum_by_timing(rows)[i.finding.timing]
        annual, label = cost.annualized(total)
        st.markdown(f"**Weekly increase, {TIMING_LABELS[i.finding.timing].lower()}: {md(money(total))}** "
                    f"({md(money(annual))} {label})")
    order = {ImpactResult.AFFECTED: 0, ImpactResult.NEEDS_REVIEW: 1}
    heads = ["Employee", "Type", "Wage", "Hours a week", "Result", "Why", "Increase a week", "Calculation"]
    body = ""
    for r in sorted(rows, key=lambda r: (order.get(r.result, 2), r.employee_id)):
        inc = f"{r.weekly_increase:.2f}" if r.weekly_increase is not None else ""
        cells = [(r.employee_id, "mono"), (r.employment_type.value.replace("_", " "), ""),
                 (f"{r.hourly_wage:.2f}", "mono"), (f"{r.weekly_hours.normalize():f}", "mono"),
                 (RESULT_LABELS[r.result], ""), (r.reason, ""), (inc, "mono"), (r.calculation, "mono")]
        body += "<tr>" + "".join(f'<td class="{k}">{esc(v)}</td>' for v, k in cells) + "</tr>"
    st.markdown('<div class="mq-scroll"><table class="mq-table"><tr>'
                + "".join(f"<th>{h}</th>" for h in heads) + f"</tr>{body}</table></div>", unsafe_allow_html=True)


def render_decision(i: Item, conn, reviewer: str) -> None:
    fid = i.finding.finding_id
    st.markdown('<div class="mq-sub">Your decision</div>', unsafe_allow_html=True)
    with st.form(f"decide_{fid}", clear_on_submit=True):
        choice = st.radio("Decision", ["Approve", "Dismiss"], horizontal=True)
        comment = st.text_area("Comment", placeholder="Required to dismiss")
        sent = st.form_submit_button("Record decision", type="primary")
    if not sent:
        return
    if not reviewer.strip():
        st.error("Enter your name above before recording a decision.")
    elif choice == "Dismiss" and not comment.strip():
        st.error("A comment is required to dismiss a finding.")
    else:
        status = Status.APPROVED if choice == "Approve" else Status.DISMISSED
        try:
            routing.decide(conn, fid, status, reviewer.strip(), comment.strip())
        except sqlite3.IntegrityError as err:
            st.error(md(f"Could not save the decision: {err}"))
            return
        st.session_state["flash"] = ("success", f"{STATUS_LABELS[status]} section {i.finding.section}.")
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


def render_detail(i: Item, comparison: Comparison, as_of: date, conn, reviewer: str) -> None:
    f = i.finding
    st.markdown(f'<div class="mq-ref">Section {esc(f.section)}, {esc(f.jurisdiction)}, '
                f'{esc(CATEGORY_LABELS[f.category])}, {esc(f.source_file)}</div>'
                f'<div class="mq-head">{esc(headline(i))}</div>', unsafe_allow_html=True)
    chips = [timing_chip(i), chip(CHANGE_LABELS[f.change_type])]
    if f.effective_date:
        chips.append(chip(f"Effective {f.effective_date}", "mono"))
    if i.route.ready and i.status is Status.PENDING:
        chips.append(chip(routing.READY_LABEL, "accent"))
    chips.append(status_chip(i.status))
    st.markdown("".join(chips), unsafe_allow_html=True)
    if f.ai_reason:
        st.caption(md(f"AI reading: {f.ai_reason}"))
    if f.recommended_action or f.owner:
        a, b = st.columns([2, 1])
        if f.recommended_action:
            a.markdown(f'<div class="mq-box"><div class="label">Recommended action</div>{esc(f.recommended_action)}</div>',
                       unsafe_allow_html=True)
        if f.owner:
            b.markdown(f'<div class="mq-box"><div class="label">Owner</div>{esc(f.owner)}</div>', unsafe_allow_html=True)
    render_why(i)
    render_excerpts(i, comparison.old_name)
    render_facts(i)
    render_impact(i)
    render_decision(i, conn, reviewer)
    render_history(conn, f.finding_id)


# ---- the page -------------------------------------------------------------------------------

def _clear_filters() -> None:
    for key, (_, placeholder) in FILTERS.items():
        st.session_state[key] = placeholder


def render(cfg: dict | None = None) -> None:
    cfg = cfg or load_config()
    st.markdown('<div class="mq-kicker">Review queue</div>', unsafe_allow_html=True)
    pairs = policy_pairs(cfg)
    if not pairs:
        st.error("No policy pairs found. Check the policies and site sections of maya.config.yaml.")
        return

    c1, c2, c3, c4 = st.columns([3, 1.4, 1.6, 1.6])
    pair = c1.selectbox("Policy pair", pairs, format_func=lambda p: p.label, key="pair")
    as_of = c2.date_input("As of", value=parse_date(str(cfg["as_of_date"])), key="as_of")
    reviewer = c3.text_input("Reviewer name", key="reviewer", placeholder="Your name")
    c4.markdown("Approval mode")
    c4.markdown(chip("Pre-approve", "accent"), unsafe_allow_html=True)

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
        flash = st.session_state.pop("flash", None)
        if flash:
            getattr(st, flash[0])(md(flash[1]))
        render_cards(summary(items))

        cols = st.columns([1.4, 1.4, 1.3, 1.3, 1.1, 1.6])
        options = {
            "f_jurisdiction": cfg["jurisdictions"],
            "f_category": list(CATEGORY_LABELS.values()),
            "f_status": list(STATUS_LABELS.values()),
            "f_timing": list(TIMING_LABELS.values()),
        }
        for col, (key, (label, placeholder)) in zip(cols, FILTERS.items()):
            col.selectbox(label, [placeholder, *options[key]], key=key)
        cols[4].markdown("&nbsp;", unsafe_allow_html=True)
        cols[4].button("Clear filters", key="clear_filters", on_click=_clear_filters)
        cols[5].caption("Filters also apply to both exports.")

        shown = apply_filters(items, {k: st.session_state.get(k, FILTERS[k][1]) for k in FILTERS})
        if not shown:
            st.info("No findings match these filters. Use Clear filters to see all.")
            return
        if st.session_state.get("selected_id") not in {i.finding.finding_id for i in shown}:
            st.session_state["selected_id"] = shown[0].finding.finding_id
        listing, detail = st.columns([1, 2.2])
        with listing:
            render_list(shown, as_of, conn, reviewer)
        with detail:
            chosen = next(i for i in shown if i.finding.finding_id == st.session_state["selected_id"])
            render_detail(chosen, comparison, as_of, conn, reviewer)
    finally:
        conn.close()
