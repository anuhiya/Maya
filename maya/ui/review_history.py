"""Review history page: every decision, newest first (B6)."""
from zoneinfo import ZoneInfo

import streamlit as st

from maya import db
from maya.site import load_config
from maya.ui import review_queue as rq
from maya.ui import view as v
from maya.ui.style import esc

ET = ZoneInfo("America/New_York")
ALL_FINDINGS, ALL_STATUSES = "All findings", "All statuses"


def eastern(when) -> str:
    """Stored UTC time shown in Eastern Time."""
    return when.astimezone(ET).strftime("%Y-%m-%d %H:%M ET")


def labels_for(cfg: dict, conn) -> dict[str, str]:
    """Finding ID to 'Section 1.1 Avalon' for the selected pair; empty when it cannot be read."""
    try:
        view = v.build_view(cfg, conn)
    except Exception:
        return {}
    return {i.finding.finding_id: f"Section {i.finding.section} {i.finding.jurisdiction}" for i in view.items}


def _clear() -> None:
    st.session_state["h_finding"], st.session_state["h_status"] = ALL_FINDINGS, ALL_STATUSES


def render(cfg: dict | None = None) -> None:
    cfg = cfg or load_config()
    rq.keep_context()
    v.title("Review history", "Every decision, newest first")
    conn = db.connect(cfg["_root"] / cfg["state"]["database"])
    try:
        decisions = db.history(conn)
        labels = labels_for(cfg, conn)
    finally:
        conn.close()
    if not decisions:
        st.info("No decisions yet. Approve or dismiss a finding on the Review queue and it appears here.")
        return

    def name(fid: str) -> str:
        return f"{labels[fid]} ({fid})" if fid in labels else fid

    ids = list(dict.fromkeys(d.finding_id for d in decisions))
    c1, c2, c3 = st.columns([2, 1.4, 1])
    chosen = c1.selectbox("Finding", [ALL_FINDINGS, *ids], key="h_finding",
                          format_func=lambda x: x if x == ALL_FINDINGS else name(x))
    status = c2.selectbox("Review status", [ALL_STATUSES, *rq.STATUS_LABELS.values()], key="h_status")
    c3.markdown("&nbsp;", unsafe_allow_html=True)
    c3.button("Clear filters", key="clear_h", on_click=_clear)
    shown = [d for d in decisions
             if chosen in (ALL_FINDINGS, d.finding_id)
             and status in (ALL_STATUSES, rq.STATUS_LABELS[d.status])]
    if not shown:
        st.info("No decisions match these filters. Use Clear filters to see all.")
        return
    st.caption(f"{len(shown)} of {len(decisions)} decisions. History is append-only: nothing here can be edited or deleted.")
    body = ""
    for d in shown:
        cells = [(esc(eastern(d.decided_at)), "mono nw"), (esc(name(d.finding_id)), ""),
                 (rq.status_chip(d.status), "nw"), (esc(d.comment), ""), (esc(d.decided_by), "nw")]
        body += "<tr>" + "".join(f'<td class="{k}">{x}</td>' for x, k in cells) + "</tr>"
    heads = ["Time", "Finding", "Status", "Comment", "Decided by"]
    nowrap_heads = ("Time", "Status", "Decided by")
    st.markdown('<div class="mq-scroll"><table class="mq-table"><tr>' + "".join(f'<th class="{"nw" if h in nowrap_heads else ""}">{h}</th>' for h in heads)
                + f"</tr>{body}</table></div>", unsafe_allow_html=True)
