"""Proposed law page: what a proposed bill would do if enacted and if not (A9).

A bill is a document stage, not a review status. Every number is calculated by code. The AI only writes a
summary, and code checks its quotes. Scenario totals are never added to the in-effect or coming totals.
"""
from datetime import date

import streamlit as st

from maya import export as csvs
from maya import scenario
from maya.ai.llm import LLM, LLMError, MissingSettingError
from maya.ai.replay import ReplayError
from maya.employees import load_employees
from maya.ingest import ReadingError
from maya.models import ImpactResult
from maya.site import load_config
from maya.timing import parse_date
from maya.ui import review_queue
from maya.ui.style import chip, esc, md


def money(value) -> str:
    return f"${value:,.2f}"


def _as_of(cfg: dict) -> date:
    value = st.session_state.get("as_of")
    return value if isinstance(value, date) else parse_date(str(cfg["as_of_date"]))


def bill_card(sc: scenario.Bill, plain: str) -> str:
    b = sc
    pairs = [("Jurisdiction", b.jurisdiction), ("Proposed effective date", b.effective_date),
             ("Proposed minimum", f"{money(b.new_value)} an hour"), ("Source file", b.source_file),
             ("Trust flag", "Trusted source" if b.trusted else "Not trusted"), ("Fingerprint", b.fingerprint[:12]),
             ("Stage", b.stage)]
    cells = "".join(f'<div class="k">{esc(k)}</div><div class="v">{esc(v)}</div>' for k, v in pairs)
    return (f'<div class="mq-box"><div class="label">Bill</div><div class="mq-head" style="margin:0 0 0.4rem 0">'
            f'{esc(b.name)}</div><div class="mq-meta">{esc(plain)}</div><div class="mq-kv">{cells}</div></div>')


def plain_summary(b: scenario.Bill, baseline) -> str:
    now = (f" The bulletin already sets {money(baseline.value)} from {baseline.effective_date}." if baseline else "")
    return (f"This bill would raise the {b.jurisdiction} {b.title.lower()} to {money(b.new_value)} an hour "
            f"from {b.effective_date}.{now} It has not passed.")


def jurisdiction_table(sc: scenario.Scenario, jurisdictions: list[str]) -> str:
    counts = sc.by_jurisdiction
    body = "".join(f'<tr><td class="nw">{esc(j)}</td><td class="nw mono">{counts.get(j, 0)}</td></tr>' for j in jurisdictions)
    return ('<table class="mq-table"><tr><th class="nw">Jurisdiction</th><th class="nw">Affected employees</th></tr>'
            + body + "</table>")


def cost_table(sc: scenario.Scenario) -> str:
    rows = [("Weekly cost", money(sc.weekly)), ("Yearly cost (52 weeks)", money(sc.yearly)),
            ("Employer Social Security and Medicare, weekly", money(sc.tax_weekly)),
            ("Employer Social Security and Medicare, yearly", money(sc.tax_yearly)),
            ("Total weekly", money(sc.total_weekly)), ("Total yearly", money(sc.total_yearly)),
            ("Effective date", sc.bill.effective_date if parse_date(sc.bill.effective_date)
                              else "Not stated in the saved text")]
    body = "".join(f'<tr><td>{esc(k)}</td><td class="mono"><b>{esc(v)}</b></td></tr>' for k, v in rows)
    return f'<table class="mq-table"><tr><th>Line</th><th>Amount</th></tr>{body}</table>'


def employee_table(sc: scenario.Scenario) -> str:
    heads = ["Employee", "Result", "Wage now", "Wage after existing changes", "Target wage", "Weekly difference"]
    order = {ImpactResult.AFFECTED: 0, ImpactResult.NEEDS_REVIEW: 1}
    body = ""
    for r in sorted((r for r in sc.rows if r.result is not ImpactResult.NOT_AFFECTED and (r.result in order or r.flags)),
                    key=lambda r: (order.get(r.result, 2), r.employee_id)):
        if r.result is ImpactResult.AFFECTED:
            result, diff = "Affected", money(r.weekly_increase)
        elif r.result is ImpactResult.NEEDS_REVIEW:
            bound = r.calculation.rsplit("= ", 1)[-1]
            result, diff = "Needs review", f"Upper bound {bound}, not in totals"
        else:
            result, diff = "Classification flag", "Contractor, not in totals"
        cells = [(r.employee_id, "mono nw"), (result, "nw"), (money(sc.wage_now[r.employee_id]), "mono nw"),
                 (money(sc.wage_after[r.employee_id]), "mono nw"), (money(sc.bill.new_value), "mono nw"), (diff, "mono nw")]
        body += "<tr>" + "".join(f'<td class="{k}">{esc(v)}</td>' for v, k in cells) + "</tr>"
    return ('<div class="mq-scroll"><table class="mq-table"><tr>' + "".join(f'<th class="nw">{h}</th>' for h in heads)
            + f"</tr>{body}</table></div>")


def _ai_card(cfg: dict, sc: scenario.Scenario) -> None:
    key = sc.bill.fingerprint
    st.markdown(f'<div class="mq-sub">{esc(scenario.AI_LABEL)}</div>', unsafe_allow_html=True)
    held = st.session_state.setdefault("scenario_ai", {})
    result = held.get(key)
    if result is None:
        st.markdown(f'<div class="mq-box"><div class="label">Plain summary built by code</div>{esc(scenario.built_summary(sc))}</div>',
                    unsafe_allow_html=True)
        if st.button("Write AI summary", key="scenario_ai_button",
                     help="Asks the model to summarize the bill. It needs a Groq key. Every quote is checked against the bill."):
            try:
                held[key] = scenario.ai_summary(LLM(cfg=cfg), sc)
            except (MissingSettingError, ReplayError, LLMError) as err:
                st.error(md(str(err)))
            else:
                st.rerun()
        return
    st.markdown(f'<div class="mq-box"><div class="label">AI summary</div>{esc(result["text"])}</div>', unsafe_allow_html=True)
    if result["replaced"]:
        st.warning(md(f"The AI text was replaced by the code-built summary because {result['replaced']}."))
    for quote in result["verified"]:
        st.markdown(f'<div class="mq-exc new"><div class="src">Quote verified word for word in the bill (V1)</div>{esc(quote)}</div>',
                    unsafe_allow_html=True)
    for quote in result["flagged"]:
        st.markdown(f'<div class="mq-box held"><div class="label">Quote not verified</div>Not found word for word in the '
                    f'bill, so it is not shown as a quote: {esc(quote)}</div>', unsafe_allow_html=True)


def real_card(rb: scenario.RealBill) -> str:
    h = rb.header
    ok = sum(1 for _, good in rb.quotes if good)
    link = f'<a href="{esc(h["official_url"])}" target="_blank" rel="noopener">{esc(h["official_url"])}</a>'
    pairs = [("Bill number", h["bill_number"]), ("Sponsor", h.get("sponsor", "")), ("Body", h.get("body", "")),
             ("Jurisdiction", rb.facts["jurisdiction"]), ("Covers", rb.scope or "not stated"),
             ("Date retrieved", h["date_retrieved"]), ("Status at retrieval", h["status_as_of_retrieval"]),
             ("Trust flag", h["trust"].capitalize()), ("Saved file fingerprint", rb.fingerprint[:12]),
             ("Facts verified (V1)", f"{ok} of {len(rb.quotes)} quotes found word for word in the saved text")]
    cells = "".join(f'<div class="k">{esc(k)}</div><div class="v">{esc(v)}</div>' for k, v in pairs)
    cells += f'<div class="k">Official page</div><div class="v">{link}</div>'
    return (f'<div class="mq-box"><div class="label">Real bill</div><div class="mq-head" style="margin:0 0 0.4rem 0">'
            f'{esc(h["short_title"])}</div><div class="mq-meta">{esc(h["title"])}</div><div class="mq-kv">{cells}</div></div>')


def _scenario_sections(cfg: dict, sc: scenario.Scenario, as_of: date, real: scenario.RealBill | None) -> None:
    bill = sc.bill
    enacted, not_enacted = st.columns(2, gap="large")
    with enacted:
        st.markdown('<div class="mq-sub" style="margin-top:0">If it is enacted</div>', unsafe_allow_html=True)
        st.markdown(jurisdiction_table(sc, cfg["jurisdictions"]), unsafe_allow_html=True)
        st.markdown(cost_table(sc), unsafe_allow_html=True)
        if sc.baseline:
            st.caption(md(f"Priced from each wage after existing changes: the {bill.jurisdiction} minimum of "
                          f"{money(sc.baseline.value)} from {sc.baseline.effective_date} ({sc.baseline.source_file}) is "
                          "already in the totals, so it is not counted again here."))
        if real:
            for note in [real.facts.get("applies_reason", "")] + list(real.facts.get("not_priced", [])):
                if note:
                    st.caption(md(note))
    with not_enacted:
        st.markdown('<div class="mq-sub" style="margin-top:0">If it is not enacted</div>', unsafe_allow_html=True)
        base = f"{money(sc.baseline.value)} from {sc.baseline.effective_date}" if sc.baseline else "the current rules"
        st.markdown(f'<div class="mq-box"><div class="label">Status quo</div>The current bulletin stays: {esc(base)}. '
                    f'Change in cost: <b class="mono">$0.00</b>.</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="mq-box held"><div class="label">Risk of not preparing (back pay, penalties)</div>'
                    f'{esc(scenario.NEEDS_INPUT)}. It depends on facts the documents do not give, so it is never guessed.</div>',
                    unsafe_allow_html=True)
        note = st.text_area("Reviewer note on the risk", key=f"risk_note_{bill.fingerprint[:8]}",
                            placeholder="Write what you know about back pay or penalties")

    st.markdown('<div class="mq-sub">Per employee, if it is enacted</div>', unsafe_allow_html=True)
    st.markdown(employee_table(sc), unsafe_allow_html=True)

    st.markdown('<div class="mq-sub">What to prepare</div>', unsafe_allow_html=True)
    for n, item in enumerate(scenario.prepare_list(sc)):
        st.checkbox(md(item), key=f"prep_{bill.fingerprint[:8]}_{n}")

    _ai_card(cfg, sc)

    st.markdown('<div class="mq-sub">Scenario totals, kept apart</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="mq-cards three"><div class="mq-card"><div class="label">Weekly if enacted</div>'
                f'<div class="value">{esc(money(sc.total_weekly))}</div><div class="sub">With the employer tax estimate</div></div>'
                f'<div class="mq-card"><div class="label">Yearly if enacted</div><div class="value">{esc(money(sc.total_yearly))}</div>'
                f'<div class="sub">52 weeks</div></div><div class="mq-card"><div class="label">If not enacted</div>'
                f'<div class="value">$0.00</div><div class="sub">Change in cost</div></div></div>', unsafe_allow_html=True)
    st.caption(scenario.TOTALS_NOTE)

    st.markdown('<div class="mq-sub">Export this scenario</div>', unsafe_allow_html=True)
    summary = st.session_state.get("scenario_ai", {}).get(bill.fingerprint)
    left, right = st.columns(2)
    left.download_button("Download scenario (CSV)", scenario.scenario_csv(sc), key="dl_scenario", mime="text/csv",
                         file_name=csvs.file_name("scenario", as_of), type="primary")
    right.download_button("Download scenario summary (Markdown)", scenario.scenario_markdown(sc, summary, note),
                          key="dl_scenario_md", mime="text/markdown", file_name=f"edelta_scenario_summary_{as_of.isoformat()}.md")


def _render_real(cfg: dict, as_of: date) -> None:
    folders = scenario.list_real_bills(cfg)
    folder = folders[0]
    if len(folders) > 1:
        folder = st.selectbox("Real bill", folders, format_func=scenario.real_label, key="real_bill")
    try:
        rb = scenario.load_real_bill(folder, cfg)
    except ValueError as err:
        st.error(md(f"Could not read {folder.name}: {err}"))
        return
    st.markdown(real_card(rb), unsafe_allow_html=True)
    st.caption("Bill text is real; the workforce is synthetic; status may have changed since retrieval.")
    bad = [q for q, ok in rb.quotes if not ok]
    if bad:
        st.warning(md("These facts were not found word for word in the saved text and are not relied on: " + "; ".join(bad)))
    if not rb.applicable:
        st.markdown(f'<div class="mq-box held"><div class="label">Not applicable to this company</div>'
                    f'Not applicable to this company, covers: {esc(rb.scope)}. {esc(rb.facts.get("applies_reason", ""))} '
                    f'No cost is calculated, because forcing a number onto a bill that does not cover these employees would be a guess.</div>',
                    unsafe_allow_html=True)
        st.caption(scenario.TOTALS_NOTE)
        return
    try:
        loaded = load_employees(cfg=cfg)
        sc = scenario.compute(cfg, rb.bill, as_of, loaded.employees)
    except (ReadingError, ValueError, OSError, KeyError) as err:
        st.error(md(f"Could not price {folder.name}: {err}"))
        return
    if loaded.problems:
        st.warning(f"{len(loaded.problems)} employee data problems found; see the employee file checks.")
    _scenario_sections(cfg, sc, as_of, rb)


def render(cfg: dict | None = None) -> None:
    cfg = cfg or load_config()
    review_queue.keep_context()
    as_of = _as_of(cfg)
    real, illustrative = scenario.list_real_bills(cfg), scenario.list_bills(cfg)
    options = (["Real proposed bills"] if real else []) + (["Illustrative bill"] if illustrative else [])
    st.markdown('<div class="mq-kicker">Proposed law</div><div class="mq-title">What a proposed bill would do</div>',
                unsafe_allow_html=True)
    if not options:
        st.markdown(chip("Proposed, not yet law", "review") + chip(f"As of {as_of.isoformat()}", "mono"), unsafe_allow_html=True)
        st.info("No proposed bill found. Put a bill (TXT or PDF) in data/policies/proposed/ to see what it would do.")
        return
    kind = st.radio("Bills", options, horizontal=True, key="bill_kind") if len(options) > 1 else options[0]
    label = chip("Real bill", "accent") if kind == "Real proposed bills" else chip("Illustrative bill", "review")
    st.markdown(chip("Proposed, not yet law", "review") + label + chip(f"As of {as_of.isoformat()}", "mono"),
                unsafe_allow_html=True)
    if kind == "Real proposed bills":
        _render_real(cfg, as_of)
        return
    path = illustrative[0]
    if len(illustrative) > 1:
        path = st.selectbox("Proposed bill", illustrative, format_func=lambda p: p.name, key="bill_file")
    try:
        bill = scenario.load_bill(path, cfg)
        loaded = load_employees(cfg=cfg)
        sc = scenario.compute(cfg, bill, as_of, loaded.employees)
    except (ReadingError, ValueError, OSError, KeyError) as err:
        st.error(md(f"Could not read {path.name}: {err}"))
        return
    if loaded.problems:
        st.warning(f"{len(loaded.problems)} employee data problems found; see the employee file checks.")
    st.markdown(bill_card(bill, plain_summary(bill, sc.baseline)), unsafe_allow_html=True)
    st.caption("Illustrative bill: the text and the figures are synthetic, not a real proposal.")
    _scenario_sections(cfg, sc, as_of, None)
