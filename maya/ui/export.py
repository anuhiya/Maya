"""Export page: filtered CSV downloads (B7)."""
import streamlit as st

from datetime import date

from maya import db
from maya import export as csvs
from maya import scenario
from maya.site import load_config
from maya.ui import view as v


def _scenario_text(cfg: dict, as_of) -> str:
    try:
        bills = scenario.list_bills(cfg)
        bill = scenario.load_bill(bills[0], cfg)
        return scenario.scenario_csv(scenario.compute(cfg, bill, as_of))
    except (IndexError, ValueError, OSError, KeyError):
        return ""


def render(cfg: dict | None = None) -> None:
    cfg = cfg or load_config()
    conn = db.connect(cfg["_root"] / cfg["state"]["database"])
    try:
        view = v.load_view(cfg, conn)
        v.title("Export", "Download findings and employee impact")
        if view is None:
            return
        v.filter_chips(view.as_of)
        findings = [i.finding for i in view.shown]
        rows = [r for i in view.shown for r in i.rows]
        findings_text = csvs.findings_csv(findings, conn)
    finally:
        conn.close()
    if not view.items:
        st.info("No changes detected. Both files download with headers only.")
    elif not view.shown:
        v.no_match()
        st.caption("Both files download with headers only.")
    left, right, third = st.columns(3)
    left.download_button("Download findings CSV", findings_text, key="dl_findings", mime="text/csv",
                         file_name=csvs.file_name("findings", view.as_of), type="primary")
    left.caption(f"{len(findings)} findings")
    right.download_button("Download employee impact CSV", csvs.impact_csv(rows), key="dl_impact",
                          mime="text/csv", file_name=csvs.file_name("employee_impact", view.as_of))
    right.caption(f"{len(rows)} employee results")
    third.download_button("Download scenario CSV", _scenario_text(cfg, view.as_of), key="dl_scenario_export",
                          mime="text/csv", file_name=csvs.file_name("scenario", view.as_of),
                          disabled=not scenario.list_bills(cfg))
    third.caption("The proposed law scenario, kept apart from the findings"
                  if scenario.list_bills(cfg) else "No proposed bill found")
