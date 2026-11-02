"""HTML for the live agent view (A5): pipeline nodes, narration and the Live AI work cards.

Everything here is a pure function of the step snapshots the agent produced (Agent.snapshot), so a live
run, a saved replay and a step the presenter went back to all look the same.
"""
import re

from maya.ui.style import chip, esc

NODES = [
    ("fetch", "Fetch site", ("watch_sources", "fetch_document"),
     "The agent lists the policy site over HTTP, downloads each bulletin, checks its sha256 against the index and "
     "pairs every new document with the version before it."),
    ("split", "Split sections", ("split_sections",),
     "Code splits the old and the new document into numbered sections. No AI is used."),
    ("read", "Read with AI", ("read_sections",),
     "The reader model reads only the sections that changed and answers in a fixed JSON format: values, dates, "
     "quoted sentences. Identical sections cost no AI call."),
    ("check", "Check V1 to V3", ("check_answers",),
     "Code checks every AI answer: V1 quotes appear word for word, V2 numbers are recomputed, V3 the answer is consistent."),
    ("match", "Match employees", ("match_employees",),
     "Code matches employees to each change by explicit rules. The AI never matches employees."),
    ("price", "Price", ("price_changes",),
     "Code calculates the weekly cost in exact decimal math. The AI never calculates money."),
    ("route", "Route", ("route_findings",),
     "Code decides which findings are ready for one-click sign-off and which need a reviewer. A person decides."),
]
NODE_LABEL = {tool: label for _, label, tools, _ in NODES for tool in tools}
NODE_LABEL.update({"search_federal_register": "Federal Register search", "finish": "Finish"})
TOP_STRIP = "Rules calculate every dollar. The model reads only synthetic policy text. A person approves every action."
STATE_WORD = {"waiting": "Waiting", "running": "Running", "done": "Done", "failed": "Failed"}
STATE_MARK = {"waiting": "", "running": "...", "done": "✓", "failed": "✗"}


def node_states(events: list[dict], current: tuple | None = None) -> dict[str, str]:
    """waiting, running, done or failed for each pipeline node, from the steps shown so far."""
    states = {}
    for key, _, tools, _ in NODES:
        mine = [e for e in events if e["tool"] in tools]
        if current and current[1] in tools:
            states[key] = "running"
        elif any(e["failed"] for e in mine) and not any(not e["failed"] and not e["refused"] for e in mine[-1:]):
            states[key] = "failed"
        elif any(not e["failed"] and not e["refused"] for e in mine):
            states[key] = "done"
        else:
            states[key] = "waiting"
    return states


def progress(states: dict[str, str]) -> float:
    return sum(s == "done" for s in states.values()) / len(states)


def narration(ev: dict | None, total: int | None) -> str:
    """One plain line such as "Step 3 of 10: Read with AI. 9 sections in the old file and 10 in the new."."""
    if ev is None:
        return "No step yet. Press Run live or Use saved run."
    label = NODE_LABEL.get(ev["tool"], ev["tool"])
    head = f"Step {ev['n']}" + (f" of {total}" if total else "") + f": {label}."
    change = next((c for c in ev["changes"] if c["id"] == ev["change"]), None)
    if ev["tool"] == "split_sections" and change:
        detail = f"{change['n_old']} sections in the old file and {change['n_new']} in the new."
    elif ev["tool"] == "read_sections" and change and change["total"]:
        detail = f"{change['total'] - change['identical']} of {change['total']} sections changed and were read."
    else:
        detail = ev["result"].splitlines()[0] if ev["result"] else ""
    if ev["by_code"]:
        detail += " Chosen by code, not the model (planner fallback)."
    if ev["refused"] or ev["failed"]:
        detail = "The code refused or could not run this step. " + detail
    return f"{head} {detail}".strip()


def ring(fraction: float) -> str:
    done = round(fraction * 100)
    return (f'<svg class="mq-ring" viewBox="0 0 36 36" width="64" height="64" role="img" aria-label="{done} percent done">'
            '<circle cx="18" cy="18" r="15.9" fill="none" stroke="rgba(102,179,255,0.20)" stroke-width="3"></circle>'
            f'<circle cx="18" cy="18" r="15.9" fill="none" stroke="#66B3FF" stroke-width="3" stroke-dasharray="{done} 100" '
            'pathLength="100" transform="rotate(-90 18 18)"></circle>'
            f'<text x="18" y="21" text-anchor="middle" font-size="8" fill="#F3F5F9">{done}%</text></svg>')


def card(title: str, body: str, kind: str = "") -> str:
    return f'<div class="mq-box mq-live {kind}"><div class="label">{esc(title)}</div>{body}</div>'


def now_card(ev: dict | None, running: bool, narr: str, frac: float, waiting: bool) -> str:
    if ev is None and not running:
        dot, text = '<span class="mq-dot idle"></span>', "Waiting for a run."
    elif waiting:
        dot, text = '<span class="mq-dot idle"></span>', "Paused. Press Next step. " + narr
    else:
        dot, text = f'<span class="mq-dot{" pulse" if running else ""}"></span>', narr or "Starting."
    return card("Now", f'<div class="mq-now"><div>{dot}{esc(text)}</div>{ring(frac)}</div>')


def node_detail_card(key: str, events: list[dict]) -> str:
    node = next(n for n in NODES if n[0] == key)
    mine = [e for e in events if e["tool"] in node[2]]
    lines = "".join(f'<div class="mq-hist"><b>Step {e["n"]}</b> {esc(e["plan"])}<br>{esc(e["result"])}</div>' for e in mine)
    body = f"<div>{esc(node[3])}</div>" + (lines or '<div class="mq-meta">This step has not run yet.</div>')
    return card(f"Step details: {node[1]}", body)


def _highlight(text: str, quote: str | None) -> str:
    safe = esc(text)
    if quote and esc(quote) in safe:
        return safe.replace(esc(quote), f"<mark>{esc(quote)}</mark>", 1)
    return safe


def reading_card(f: dict | None) -> str:
    if f is None:
        return card("Reading", '<div class="mq-meta">The reader has not read a section yet.</div>')
    text = f["new_excerpt"] or f["old_excerpt"] or ""
    body = (f'<div class="mq-meta">{esc(f["source_file"])}, Section {esc(f["section"])}</div>'
            f'<div class="mq-exc new mq-scan">{_highlight(text, f["new_rule"] or f["old_rule"])}</div>')
    return card("Reading", body)


def _fmt(value, unit):
    if value is None:
        return "none"
    unit = (unit or "").lower()
    return f"${value}" + (" per hour" if "hour" in unit else "") if "dollar" in unit else (
        f"{value}%" if "percent" in unit else f"{value} days" if "day" in unit else str(value))


def answer_card(f: dict | None) -> str:
    if f is None:
        return card("AI answer", '<div class="mq-meta">No answer yet.</div>')
    old_date = re.search(r"^Effective Date:\s*(.+)$", f["old_excerpt"] or "", re.M | re.I)
    body = (f'<div class="mq-fade"><div class="mq-meta">AI reading</div>'
            f'<div class="mq-kv"><div class="k">Value</div><div class="v">{esc(_fmt(f["old_value"], f["unit"]))} to '
            f'<b>{esc(_fmt(f["new_value"], f["unit"]))}</b></div>'
            f'<div class="k">Effective date</div><div class="v">{esc(old_date.group(1).strip() if old_date else "none")} to '
            f'<b>{esc(f["effective_date"] or "not found")}</b></div>'
            f'<div class="k">Change</div><div class="v">{esc(f["change_type"])}</div></div>'
            f'<div class="mq-meta">{esc(f["ai_reason"])}</div></div>')
    return card("AI answer", body)


def checks_card(f: dict | None, checked: bool) -> str:
    if f is None:
        return card("Checks", '<div class="mq-meta">Nothing to check yet.</div>')
    if not checked:
        chips = "".join(f'<span class="mq-chip"><span class="mq-spin"></span>{n} checking</span>' for n in ("V1", "V2", "V3"))
        return card("Checks", chips)
    chips = "".join(chip(f"{'✓' if c['passed'] else '✗'} {c['check']}: {'passed' if c['passed'] else 'failed'}",
                         "good" if c["passed"] else "critical") for c in f["checks"])
    failed = [c for c in f["checks"] if not c["passed"]]
    body = chips + "".join(f'<div class="mq-meta">{esc(c["check"])}: {esc(c["detail"])}</div>' for c in f["checks"])
    if failed or f["flags"]:
        reasons = [f"{c['check']}: {c['detail']}" for c in failed] + list(f["flags"])
        body += ('<div class="mq-box held"><div class="label">Held for review: not guessed</div>'
                 + "<br>".join(esc(r) for r in reasons) + "</div>")
    return card("Checks", body)


def countup(amount: str) -> str:
    whole, cents = amount.split(".")
    return f'<span class="mq-count" style="--d:{int(whole)};--t:{cents[0]};--o:{cents[1]}" aria-label="${esc(amount)}"></span>'


def calc_card(f: dict | None, priced: bool) -> str:
    if f is None or not priced:
        return card("Calculated by code, not AI", '<div class="mq-meta">Waiting for the match and price steps.</div>')
    body = (f'<div class="mq-meta">{f["matched"]} employees matched, {f["affected"]} affected.</div>'
            f'<div class="mq-bignum">{countup(f["weekly"])} <span>a week</span></div>'
            + (f'<div class="mq-meta mono">{esc(f["calc"])}</div>' if f["calc"] else
               '<div class="mq-meta">No pay change for this finding.</div>'))
    return card("Calculated by code, not AI", body, "calc")


def routing_card(f: dict | None, ev: dict | None) -> str:
    lanes = [("decision", "Needs decision"), ("ready", "Ready to approve"), ("wording", "Wording only")]
    counts = (ev or {}).get("lanes", {})
    cols = ""
    for key, label in lanes:
        here = f is not None and f["lane"] == key
        landed = (f'<div class="mq-landed">{esc(f["section"])} {esc(f["jurisdiction"])}</div>' if here else "")
        cols += (f'<div class="mq-lane{" on" if here else ""}"><b>{esc(label)}</b> ({counts.get(key, 0)}){landed}</div>')
    why = f'<div class="mq-meta">{esc(f["why"])}</div>' if f and f["lane"] else '<div class="mq-meta">Not routed yet.</div>'
    return card("Routing", f'<div class="mq-lanes">{cols}</div>{why}')


def split_bar(ev: dict | None) -> str:
    if ev is None:
        return ""
    reads = sum(c["total"] - c["identical"] for c in ev["changes"] if c["total"])
    ai, code = ev["ai_answers"], ev["prices"]
    person = ev["lanes"]["decision"] + ev["lanes"]["ready"]
    total = max(ai + code + person, 1)
    seg = lambda n, cls: f'<span class="mq-seg {cls}" style="width:{100 * n / total:.1f}%"></span>'  # noqa: E731
    return card("Who did what", f'<div class="mq-split">{seg(ai, "ai")}{seg(code, "code")}{seg(person, "person")}</div>'
                f'<div class="mq-meta">AI read {reads} sections ({ai} answers), code calculated {code} prices, '
                f'a person decides {person}.</div>')
