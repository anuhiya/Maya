"""Agent activity page: run, live log, publish, start over and manual upload (A2, A4, B1)."""
import time
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import streamlit as st

from maya import agent, db, runner, site, siteserver, sources
from maya.ai.llm import LLM, LLMError
from maya.ai.replay import ReplayError
from maya.ingest import ReadingError
from maya.models import LogTag
from maya.ui import live_view, review_queue
from maya.ui.style import chip, esc, md

SAVED_RUN = "agent_demo"
GUARDRAILS = "AI reads and judges; code checks and calculates; a person decides anything unclear."
BADGES = {"ready": ("Ready", ""), "running": ("Running", "future"), "finished": ("Finished", "good"),
          "stopped": ("Stopped", "review")}
RESET_KEYS = ("view_index", "selected_node", "ribbon_pick", "run_started", "was_running", "agent_result", "upload_pair", "upload_count", "confirm_reset", "pair", "selected_id")


def _tag_class(line) -> str:
    if line.tag is LogTag.CHECK:
        return "pass" if line.text.startswith("Passed") else "fail"
    return line.tag.value.lower()


def local_time(when: datetime, ui: dict) -> str:
    """A stored UTC time in the configured zone, such as 13:42:46 ET."""
    shown = when.astimezone(ZoneInfo(ui["timezone"])) if ui.get("timezone") else when
    return f"{shown:%H:%M:%S} {ui.get('timezone_label', '')}".strip()


def log_html(lines, ui: dict | None = None) -> str:
    """The log as rows: time, tag word with its colour, text. Replayed lines say so."""
    ui = ui or {}
    if not lines:
        return '<div class="mq-log"><div class="mq-meta">No lines yet. Press Run agent.</div></div>'
    rows = []
    for line in lines:
        mono = " mono" if line.tag is LogTag.TOOL else ""
        replayed = '<span class="rp">replayed from saved run</span>' if line.replayed else ""
        rows.append(f'<div class="mq-line"><span class="at">{local_time(line.at, ui)}</span>'
                    f'<span><span class="mq-tag {_tag_class(line)}">{line.tag.value}</span></span>'
                    f'<span class="txt{mono}">{esc(line.text)}{replayed}</span></div>')
    return f'<div class="mq-log">{"".join(rows)}</div>'


def _has_key(cfg: dict) -> bool:
    try:
        LLM(cfg=cfg)
    except (LLMError, ReplayError):
        return False
    return True


def _make_llm(cfg: dict, use_saved: bool) -> LLM:
    if use_saved:
        return LLM(cfg=cfg, env={"MAYA_LLM_PROVIDER": "replay", "MAYA_REPLAY_RUN": SAVED_RUN})
    return LLM(cfg=cfg)  # raises MissingSettingError naming GROQ_API_KEY


def _show_badge(slot, state: str) -> None:  # slot: st or an st.empty()
    word, kind = BADGES[state]
    slot.markdown(f'<div class="mq-meta">Status {chip(word, kind)}</div>', unsafe_allow_html=True)


def _header(cfg: dict) -> None:
    st.markdown('<div class="mq-kicker">Agent activity</div>', unsafe_allow_html=True)
    st.markdown('<div class="mq-title">Watching your policy sources</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="mq-strip">{esc(live_view.TOP_STRIP)}</div>', unsafe_allow_html=True)


def _agent_card() -> None:
    chips = "".join(chip(name, "mono") for name in agent.TOOLS)
    st.markdown(f'<div class="mq-box"><div class="label">Agent</div><b>Goal.</b> {esc(agent.GOAL)}'
                f'<div style="margin-top:0.4rem">{chips}</div></div>', unsafe_allow_html=True)


def _start(cfg: dict, use_saved: bool, step_mode: bool = False) -> bool:
    """Start the agent on its background worker. Leaving the page does not stop it. False if it did not start."""
    try:
        llm = _make_llm(cfg, use_saved)
    except (LLMError, ReplayError) as err:
        st.error(md(str(err)))
        return False
    conn = db.connect(cfg["_root"] / cfg["state"]["database"])
    try:
        if not sources.watch_sources(cfg, conn).unseen:
            st.info(f"All sources unchanged since the last run. Checked at "
                    f"{datetime.now(timezone.utc):%H:%M:%S} UTC.")
            return False
    finally:
        conn.close()
    runner.start(cfg, use_saved, step_mode, llm=llm)
    for key in ("view_index", "selected_node", "ribbon_pick"):
        st.session_state.pop(key, None)
    st.session_state["run_started"] = True
    return True


def _stopped_card(cfg: dict, why: str, key: str) -> None:
    st.warning(f"Run stopped. {why} Nothing was marked as seen, so running again is safe. "
               "Run again starts from step 1; it does not continue mid-step.")
    a, b, _ = st.columns([1, 1, 4])
    if a.button("Run again", key=f"{key}_again", type="primary"):
        if _start(cfg, st.session_state.get("use_saved", True), st.session_state.get("step_mode", False)):
            st.rerun()
    if b.button("Start over", key=f"{key}_over"):
        st.session_state["confirm_reset"] = True


def _view(events: list[dict]) -> tuple[int, list[dict]]:
    """Which step is on show: the latest unless the presenter went back."""
    index = st.session_state.get("view_index")
    cur = len(events) - 1 if index is None else min(index, len(events) - 1)
    return cur, events[:cur + 1]


def _pipeline(cfg: dict, queue_page) -> None:
    """Pipeline diagram, narration, status and result. Polled while the worker runs."""
    run = runner.current()
    events = list(run.events) if run else []
    cur, shown = _view(events)
    live_now = bool(run and run.running and st.session_state.get("view_index") is None)
    states = live_view.node_states(shown, run.current if live_now else None)
    st.markdown('<div class="mq-sub">Pipeline</div>', unsafe_allow_html=True)
    cols = st.columns(len(live_view.NODES))
    for col, (key, label, _, _) in zip(cols, live_view.NODES):
        chosen = st.session_state.get("selected_node") == key
        with col, st.container(key=f"node_{key}_{states[key]}{'_sel' if chosen else ''}"):
            if st.button(label, key=f"nodebtn_{key}", width="stretch"):
                st.session_state["selected_node"] = None if chosen else key
                st.rerun()
        word = live_view.STATE_WORD[states[key]]
        mark = live_view.STATE_MARK[states[key]]
        col.markdown(f'<div class="mq-state {states[key]}">{esc((mark + " " + word).strip())}</div>', unsafe_allow_html=True)
    finished = bool(run and not run.running)
    total = len(events) if finished else None
    narr = live_view.narration(shown[-1] if shown else None, total)
    state = "running" if run and run.running else ("ready" if run is None else
            "stopped" if run.status in ("stopped", "error") else "finished")
    _show_badge(st, state)
    st.markdown(f'<div class="mq-meta" style="margin-top:0.2rem">{esc(narr)}</div>', unsafe_allow_html=True)
    if run is None:
        if st.session_state.get("run_started"):
            _stopped_card(cfg, "The app restarted or the run was cleared.", "lost")
        return
    if run.running:
        st.session_state["was_running"] = True
        return
    if st.session_state.pop("was_running", False):
        st.rerun()  # one full rerun so the parts outside the fragments catch up
    if run.status == "error":
        st.error(md(run.error))
    if run.result:
        render_result(run.result, cfg)
        if run.status == "stopped":
            _stopped_card(cfg, "The run ended before it finished.", "run")
        _queue_link(queue_page)


def _live_panel(cfg: dict) -> None:
    """The right-hand Live AI work panel, built from the step on show."""
    run = runner.current()
    events = list(run.events) if run else []
    cur, shown = _view(events)
    ev = shown[-1] if shown else None
    running = bool(run and run.running)
    live_now = running and st.session_state.get("view_index") is None
    states = live_view.node_states(shown, run.current if live_now else None)
    st.markdown('<div class="mq-sub" style="margin-top:0">Live AI work</div>', unsafe_allow_html=True)
    node = st.session_state.get("selected_node")
    if node:
        st.markdown(live_view.node_detail_card(node, shown), unsafe_allow_html=True)
    findings = ev["findings"] if ev else []
    ids = [f["id"] for f in findings]
    pick = st.session_state.get("ribbon_pick")
    chosen = next((f for f in findings if f["id"] == pick), findings[-1] if findings else None)
    done = lambda tool: any(e["tool"] == tool and not e["failed"] and not e["refused"] for e in shown)  # noqa: E731
    narr = live_view.narration(ev, None)
    waiting = bool(run and run.waiting)
    parts = [live_view.now_card(ev, running, narr, live_view.progress(states), waiting),
             live_view.reading_card(chosen), live_view.answer_card(chosen),
             live_view.checks_card(chosen, done("check_answers")),
             live_view.calc_card(chosen, done("price_changes")),
             live_view.routing_card(chosen, ev)]
    st.markdown("".join(parts), unsafe_allow_html=True)
    if findings:
        st.markdown('<div class="mq-sub">Run ribbon</div>', unsafe_allow_html=True)
        with st.container(horizontal=True, key="ribbon_row"):
            for n, f in enumerate(findings, 1):
                lane = f["lane"] or "open"
                picked = "_sel" if f["id"] == (chosen or {}).get("id") else ""
                tip = f"Section {f['section']} {f['title']}, {f['jurisdiction']}: ${f['weekly']} a week"
                with st.container(key=f"ribbon_{lane}{picked}_{f['id']}"):
                    if st.button(str(n), key=f"dot_{f['id']}", help=tip):
                        st.session_state["ribbon_pick"] = f["id"]
                        st.rerun()
        st.markdown(f'<div class="mq-meta">Running totals: in effect <b class="mono">{esc("$" + ev["in_effect"])}</b>, '
                    f'coming <b class="mono">{esc("$" + ev["coming"])}</b>. Dots are numbered in finding order: green is ready '
                    'to approve, amber needs a decision, grey is wording only. Click a dot to replay its cards.</div>',
                    unsafe_allow_html=True)
    st.markdown(live_view.split_bar(ev), unsafe_allow_html=True)


def _controls(cfg: dict) -> None:
    run = runner.current()
    events = list(run.events) if run else []
    cur, _ = _view(events)
    index = st.session_state.get("view_index")
    busy = bool(run and run.running)
    a, b = st.columns(2)
    use_saved = a.checkbox("Use saved run (backup)", value=not _has_key(cfg), key="use_saved",
                           help="Replays the saved AI answers instead of calling the model.")
    step_mode = b.checkbox("Step by step", key="step_mode", help="Pause before every step until you press Next step.")
    c = st.columns([1.2, 1, 1, 1.2, 1])
    if c[0].button("Run saved" if use_saved else "Run live", key="run_agent", type="primary", disabled=busy):
        if _start(cfg, use_saved, step_mode):
            st.rerun()
    can_next = bool(run) and ((index is not None and cur < len(events) - 1) or run.waiting)
    if c[1].button("Next step", key="next_step", disabled=not can_next):
        if index is not None and cur < len(events) - 1:
            st.session_state["view_index"] = None if cur + 1 >= len(events) - 1 and not busy else cur + 1
        elif run.waiting:
            st.session_state["view_index"] = None
            run.next_step()
        st.rerun()
    if c[2].button("Back", key="back_step", disabled=cur <= 0 or not events):
        st.session_state["view_index"] = cur - 1
        st.rerun()
    if c[3].button("Skip to end", key="skip_end", disabled=not run):
        st.session_state["view_index"] = None
        if busy:
            run.release_all()
        st.rerun()
    if c[4].button("Start over", key="start_over"):
        st.session_state["confirm_reset"] = True
    confirm_reset(cfg)


def _audit_log(cfg: dict) -> None:
    run = runner.current()
    with st.expander("Audit log"):
        st.caption("Every PLAN, TOOL, AI, CHECK and RESULT line. The same log is saved to agent_runs.")
        st.markdown(log_html(list(run.lines) if run else [], cfg.get("ui", {})), unsafe_allow_html=True)


def render_result(result, cfg: dict | None = None) -> None:
    st.markdown('<div class="mq-sub">Summary</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="mq-box">{esc(result.summary)}</div>', unsafe_allow_html=True)
    if result.status == "stopped":
        st.warning("The run stopped before it finished. Nothing was marked as seen; run it again.")
    st.markdown('<div class="mq-sub">Federal Register, informational only</div>', unsafe_allow_html=True)
    items = sources.relevant_items(cfg, result.informational) if cfg else result.informational
    if items:
        st.caption("Shown for the reviewer. Never matched to employees or priced.")
        for item in items:
            st.markdown(f'<div class="mq-item"><a href="{esc(item.url)}" target="_blank" rel="noopener">'
                        f'{esc(item.title)}</a> <span class="when">{esc(item.date)}</span></div>',
                        unsafe_allow_html=True)
    else:
        st.caption("No relevant items found.")


def _queue_link(queue_page) -> None:
    if queue_page is not None:
        st.page_link(queue_page, label="Open the Review queue")
    else:
        st.caption("Open the Review queue from the sidebar.")


CUSTOM_HELP = ("Custom changes run live only (no saved run exists): untick Use saved run and use a Groq key. "
               "Publish the rehearsed version first; each change edits one section, and Start over removes it.")


def _publish_custom(cfg: dict, jurisdiction: str, change_type: str, value: str, when: date | None) -> None:
    try:
        done = agent.publish_custom_version(cfg, jurisdiction, change_type, value, when)
    except (OSError, ValueError) as err:
        st.error(md(f"Could not publish: {err}"))
        return
    st.success(md(f"Published {done.files[0]}: section {done.section} {done.title} ({done.jurisdiction}) "
                  f"changed. Untick Use saved run, then run the agent."))


def render_custom(cfg: dict) -> None:
    with st.container(border=True, key="publish_card"):
        st.markdown('<div class="mq-sub" style="margin-top:0">Publish a change</div>', unsafe_allow_html=True)
        st.caption(CUSTOM_HELP)
        site_cfg, types = cfg["site"], cfg["site"]["custom_changes"]
        as_of = date.fromisoformat(str(cfg["as_of_date"]))
        c1, c2, c3, c4 = st.columns([1.8, 1.9, 1.1, 1.6], vertical_alignment="bottom")
        jurisdiction = c1.selectbox("Jurisdiction", cfg["jurisdictions"], key="custom_jurisdiction")
        change_type = c2.selectbox("Change type", list(types), format_func=lambda k: types[k]["label"],
                                   key="custom_type")
        value = c3.text_input("New value", key="custom_value", placeholder="$17.25")
        when = c4.date_input("Effective date", value=as_of, key="custom_date")
        go, skip = st.columns([1.2, 2], vertical_alignment="center")
        leave_out = skip.checkbox("Leave the date out", key="custom_no_date",
                                  help="Shows the missing effective date flag.")
        if go.button("Publish this change", key="custom_publish", type="primary"):
            _publish_custom(cfg, jurisdiction, change_type, value, None if leave_out else when)
        st.markdown('<div class="mq-meta">Presets</div>', unsafe_allow_html=True)
        with st.container(horizontal=True, key="preset_row"):
            for i, preset in enumerate(site_cfg.get("presets", [])):
                if preset["jurisdiction"] not in cfg["jurisdictions"]:
                    continue
                offset = preset.get("date_offset_days")
                if st.button(preset["label"], key=f"custom_preset_{i}"):
                    _publish_custom(cfg, preset["jurisdiction"], preset["change_type"], preset.get("value", ""),
                                    None if offset is None else as_of + timedelta(days=offset))


SITE_EXPLAINER = ("The agent watches a fictional policy site, so publishing a bulletin here simulates a regulator "
                  "posting one; the agent then finds it, reads it, matches employees and prices it live.")


def render_site_link(cfg: dict) -> None:
    if not (cfg["site"].get("server") or {}).get("enabled"):
        return
    try:
        url = siteserver.ensure_running(cfg)
    except OSError as err:
        st.error(md(f"The policy site could not start: {err}"))
        return
    st.link_button("Open the policy site in a new tab", url)


def confirm_reset(cfg: dict) -> None:
    if not st.session_state.get("confirm_reset"):
        return
    st.warning("Start over clears the database (reviews, runs and seen documents), the uploads and every custom "
               "version. Continue?")
    a, b, _ = st.columns([2, 1, 3])
    if a.button("Yes, clear everything", key="confirm_yes", type="primary"):
        runner.clear()
        agent.start_over(cfg)
        for key in RESET_KEYS:
            st.session_state.pop(key, None)
        st.cache_data.clear()
        st.success("Demo reset. Run the agent to start again.")
    if b.button("Cancel", key="confirm_no"):
        st.session_state["confirm_reset"] = False
        st.rerun()


def render_actions(cfg: dict) -> None:
    st.markdown('<div class="mq-sub">Demo actions</div>', unsafe_allow_html=True)
    st.caption(SITE_EXPLAINER)
    render_site_link(cfg)
    if st.button("Publish next version", key="publish"):
        try:
            moved = agent.publish_next_version(cfg)
        except (OSError, ValueError) as err:
            st.error(md(f"Could not publish: {err}"))
        else:
            if moved:
                st.success(md(f"Published {', '.join(moved)}. Run the agent again to pick it up."))
            else:
                st.info("No held-back version is left to publish.")
    render_custom(cfg)


def render_upload(cfg: dict, queue_page) -> None:
    st.markdown('<div class="mq-sub">Compare two files yourself</div>', unsafe_allow_html=True)
    st.caption("Upload a fresh pair of files (TXT or PDF), an old and a new version. They go through the same "
               "reading and checks. This needs a Groq key: no saved replay exists for files you upload.")
    c1, c2 = st.columns(2)
    old = c1.file_uploader("Old version", type=["txt", "pdf"], key="old_file")
    new = c2.file_uploader("New version", type=["txt", "pdf"], key="new_file")
    if not st.button("Compare uploaded files", key="compare_upload", disabled=not (old and new)):
        return
    if old.name == new.name:
        st.error("Give the two files different names.")
        return
    try:
        old_path = sources.save_upload(cfg, old.name, old.getvalue())
        new_path = sources.save_upload(cfg, new.name, new.getvalue())
    except ValueError as err:
        st.error(md(str(err)))
        return
    pair = review_queue.Pair(f"{old_path.stem} to {new_path.stem}".replace("_", " "), old_path, new_path)
    try:
        comparison = review_queue._cached_compare(cfg, pair, review_queue._stamp(cfg, pair))
    except ReadingError as err:
        st.error(md(f"Could not read {old_path.name} or {new_path.name}: {err}"))
        return
    except (LLMError, ReplayError) as err:
        st.error(md(str(err)))
        return
    result = comparison.result
    st.session_state["upload_pair"], st.session_state["upload_count"] = pair, len(result.findings)
    st.session_state["pair"] = review_queue.policy_pairs(cfg)[0]
    if not result.findings:
        st.info(f"No changes detected: {result.summary}. 0 findings, $0.00.")
    else:
        st.success(f"{len(result.findings)} findings from {old_path.name} and {new_path.name}.")
    _queue_link(queue_page)


def render(cfg: dict | None = None, queue_page=None) -> None:
    cfg = cfg or site.load_config()
    _header(cfg)
    left, right = st.columns([3, 2], gap="large")
    run = runner.current()
    every = 0.4 if run and run.running else None
    with left:
        _agent_card()
        st.fragment(_pipeline, run_every=every)(cfg, queue_page)
        _controls(cfg)
        render_actions(cfg)
        _audit_log(cfg)
        render_upload(cfg, queue_page)
    with right:
        st.fragment(_live_panel, run_every=every)(cfg)
