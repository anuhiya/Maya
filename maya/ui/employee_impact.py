"""Employee impact page: results, totals, assumptions (B3, B4)."""
import streamlit as st

from maya import cost, db
from maya.models import ImpactResult, Timing
from maya.site import load_config
from maya.ui import view as v
from maya.ui.review_queue import RESULT_LABELS, TIMING_LABELS, money
from maya.ui.style import esc

ALL = "All jurisdictions"

ASSUMPTIONS = (
    "Jurisdiction is where the employee works. For remote staff that is their home.",
    "Weekly hours are a standard week, not timecard hours.",
    "Overtime is 40 hours a week at 1.5 times the gap. Daily overtime is not modelled.",
    "The base wage is treated as the regular rate: no bonuses or shift pay.",
    "Contractors are excluded. One paid below a new minimum carries a classification warning.",
    "Salaried exempt staff are excluded.",
    "No city or county minimum wages. Only the gap to the new state minimum is costed.",
    "The hours split of hybrid staff is not recorded, so it is not priced.",
)


def totals_table(rows: list, jurisdictions: list[str]) -> str:
    body = ""
    for j in [*jurisdictions, ALL]:
        mine = rows if j == ALL else [r for r in rows if r.jurisdiction == j]
        t = cost.sum_by_timing(mine)
        affected = len({r.employee_id for r in mine if r.result is ImpactResult.AFFECTED})
        annual, label = cost.annualized(t[Timing.CURRENT])
        cells = [(j, ""), (str(affected), "mono"), (money(t[Timing.CURRENT]), "mono"),
                 (money(t[Timing.FUTURE]), "mono"), (f"{money(annual)} {label}", "mono")]
        body += "<tr>" + "".join(f'<td class="{k}">{esc(x)}</td>' for x, k in cells) + "</tr>"
    heads = ["Jurisdiction", "Employees affected", "Weekly increase in effect", "Weekly increase coming",
             "In effect, yearly"]
    return ('<table class="mq-table"><tr>' + "".join(f"<th>{h}</th>" for h in heads) + f"</tr>{body}</table>")


def cost_panel(shown: list) -> str:
    """X1 total cost panel and per-employee totals. Flagged lines show a status, never a number."""
    panel = cost.total_cost([(i.finding, i.rows) for i in shown])
    body = ""
    for x in panel.lines:
        weekly = money(x.weekly) if x.weekly is not None else "Not calculated"
        yearly = money(x.yearly) if x.yearly is not None else "Not calculated"
        cells = [(x.label, "wrap"), (weekly, "mono nw"), (yearly, "mono nw"), (x.status, "nw"), (x.note, "wrap")]
        body += "<tr>" + "".join(f'<td class="{k}">{esc(t)}</td>' for t, k in cells) + "</tr>"
    heads = ["Line", "Per week", "Yearly (52 weeks)", "Status", "Note"]
    out = ('<div class="mq-scroll"><table class="mq-table"><tr>' + "".join(f"<th>{h}</th>" for h in heads)
           + f"</tr>{body}</table></div>")
    body = ""
    for e in panel.employees:
        cells = [(e.employee_id, "mono"), (e.changes, "wrap"), (money(e.now), "mono nw"),
                 (money(e.coming), "mono nw"), (e.coming_dates, "nw"), (money(e.tax), "mono nw"),
                 (money(e.total), "mono nw"), (e.flags, "wrap")]
        body += "<tr>" + "".join(f'<td class="{k}">{esc(t)}</td>' for t, k in cells) + "</tr>"
    heads = ["Employee", "Changes", "Increase now", "Increase coming", "Coming from", "Employer tax", "Total", "Flags"]
    return (out + '<div class="mq-sub">Per employee, adds up to the panel</div>'
            '<div class="mq-scroll"><table class="mq-table"><tr>' + "".join(f"<th>{h}</th>" for h in heads)
            + f"</tr>{body}</table></div>")


def results_table(shown: list) -> str:
    heads = ["Employee", "Finding", "Timing", "Result", "Why", "Rule", "Calculation", "Weekly increase"]
    wraps = {"Why", "Calculation"}
    entries = []
    for i in shown:
        label = f"Section {i.finding.section} {i.finding.jurisdiction}"
        for r in i.rows:
            entries.append((r.result is not ImpactResult.AFFECTED, -(r.weekly_increase or 0),
                            i.finding.section, r.employee_id, label, r))
    body = ""
    for *_, label, r in sorted(entries, key=lambda e: e[:4]):
        inc = f"{r.weekly_increase:.2f}" if r.weekly_increase is not None else ""
        cells = [(r.employee_id, "mono"), (label, ""), (TIMING_LABELS[r.timing], ""),
                 (RESULT_LABELS[r.result], ""), (r.reason, ""), (r.rule_id, "mono"),
                 (r.calculation, "mono"), (inc, "mono")]
        body += "<tr>" + "".join(f'<td class="{k} {"wrap" if h in wraps else "nw"}">{esc(x)}</td>'
                                 for (x, k), h in zip(cells, heads)) + "</tr>"
    return ('<div class="mq-scroll"><table class="mq-table"><tr>'
            + "".join(f'<th class="{"wrap" if h in wraps else "nw"}">{h}</th>' for h in heads)
            + f"</tr>{body}</table></div>")


def render(cfg: dict | None = None) -> None:
    cfg = cfg or load_config()
    conn = db.connect(cfg["_root"] / cfg["state"]["database"])
    try:
        view = v.load_view(cfg, conn)
    finally:
        conn.close()
    v.title("Employee impact", "Who is affected and what it costs")
    if view is None:
        return
    v.filter_chips(view.as_of)
    if not view.items:
        st.info("No changes detected. 0 findings, $0.00.")
    elif not view.shown:
        v.no_match()
    else:
        rows = [r for i in view.shown for r in i.rows]
        st.markdown(f'<div class="mq-sub">Totals by jurisdiction</div>'
                    + totals_table(rows, cfg["jurisdictions"]), unsafe_allow_html=True)
        st.markdown('<div class="mq-sub">Total cost</div>' + cost_panel(view.shown), unsafe_allow_html=True)
        st.markdown('<div class="mq-sub">All employees for the selected findings</div>', unsafe_allow_html=True)
        st.caption(f"{len(rows)} results for {len(view.shown)} findings.")
        st.markdown(results_table(view.shown), unsafe_allow_html=True)
    st.markdown('<div class="mq-box"><div class="label">Assumptions</div>'
                + "<br>".join(esc(a) for a in ASSUMPTIONS) + "</div>", unsafe_allow_html=True)
