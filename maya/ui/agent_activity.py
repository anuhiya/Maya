"""Agent activity page: run, live log, publish, start over and manual upload (A2, A4, B1)."""
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import streamlit as st

from maya import agent, db, site, sources
from maya.ai.llm import LLM, LLMError
from maya.ai.replay import ReplayError
from maya.ingest import ReadingError
from maya.models import LogTag
from maya.ui import review_queue
from maya.ui.style import chip, esc, md

SAVED_RUN = "agent_demo"
GUARDRAILS = "AI reads and judges; code checks and calculates; a person decides anything unclear."
BADGES = {"ready": ("Ready", ""), "running": ("Running", "future"), "finished": ("Finished", "good"),
          "stopped": ("Stopped", "review")}
RESET_KEYS = ("agent_result", "upload_pair", "upload_count", "confirm_reset", "pair", "selected_id")


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


def _show_badge(slot, state: str) -> None:
    word, kind = BADGES[state]
    slot.markdown(f'<div class="mq-meta">Status {chip(word, kind)}</div>', unsafe_allow_html=True)


def _header(cfg: dict) -> None:
    st.markdown('<div class="mq-kicker">Agent activity</div>', unsafe_allow_html=True)
    st.markdown('<div class="mq-title">Watching your policy sources</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="mq-box"><div class="label">Goal</div>{esc(agent.GOAL)}</div>',
                unsafe_allow_html=True)
    chips = "".join(chip(name, "mono") for name in agent.TOOLS)
    st.markdown(f'<div class="mq-box"><div class="label">Tools</div>{chips}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="mq-box"><div class="label">Guardrails</div>{esc(GUARDRAILS)}</div>',
                unsafe_allow_html=True)


def _run(cfg: dict, use_saved: bool, log_slot, badge_slot):
    """Run the agent in Automatic mode, growing the log line by line. Returns a RunResult or None."""
    try:
        llm = _make_llm(cfg, use_saved)
    except (LLMError, ReplayError) as err:
        st.error(md(str(err)))
        return None
    ui = cfg.get("ui", {})
    conn = db.connect(cfg["_root"] / cfg["state"]["database"])
    try:
        if not sources.watch_sources(cfg, conn).unseen:
            st.info(f"All sources unchanged since the last run. Checked at "
                    f"{datetime.now(timezone.utc):%H:%M:%S} UTC.")
            return None
        lines = []

        def on_line(line):
            lines.append(line)
            log_slot.markdown(log_html(lines, ui), unsafe_allow_html=True)
            if line.replayed:
                time.sleep(ui.get("replay_line_delay", 0))  # so a replay grows like a live run

        _show_badge(badge_slot, "running")
        return agent.Agent(cfg, agent.LLMPlanner(llm), llm, conn, on_line=on_line,
                           saved_run=SAVED_RUN).run()
    finally:
        conn.close()


def render_result(result) -> None:
    st.markdown('<div class="mq-sub">Summary</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="mq-box">{esc(result.summary)}</div>', unsafe_allow_html=True)
    if result.status == "stopped":
        st.warning("The run stopped before it finished. Nothing was marked as seen; run it again.")
    st.markdown('<div class="mq-sub">Federal Register, informational only</div>', unsafe_allow_html=True)
    if result.informational:
        st.caption("Shown for the reviewer. Never matched to employees or priced.")
        for item in result.informational:
            st.markdown(f'<div class="mq-item"><a href="{esc(item.url)}" target="_blank" rel="noopener">'
                        f'{esc(item.title)}</a> <span class="when">{esc(item.date)}</span></div>',
                        unsafe_allow_html=True)
    else:
        st.caption("No items found in this run.")


def _queue_link(queue_page) -> None:
    if queue_page is not None:
        st.page_link(queue_page, label="Open the Review queue")
    else:
        st.caption("Open the Review queue from the sidebar.")


def render_actions(cfg: dict) -> None:
    st.markdown('<div class="mq-sub">Demo actions</div>', unsafe_allow_html=True)
    c1, c2, _ = st.columns([1.3, 1, 3])
    if c1.button("Publish next version", key="publish"):
        try:
            moved = agent.publish_next_version(cfg)
        except (OSError, ValueError) as err:
            st.error(md(f"Could not publish: {err}"))
        else:
            if moved:
                st.success(md(f"Published {', '.join(moved)}. Run the agent again to pick it up."))
            else:
                st.info("No held-back version is left to publish.")
    if c2.button("Start over", key="start_over"):
        st.session_state["confirm_reset"] = True
    if st.session_state.get("confirm_reset"):
        st.warning("Start over clears the database (reviews, runs and seen documents) and the uploads. "
                   "Continue?")
        a, b, _ = st.columns([2, 1, 3])
        if a.button("Yes, clear everything", key="confirm_yes", type="primary"):
            agent.start_over(cfg)
            for key in RESET_KEYS:
                st.session_state.pop(key, None)
            st.cache_data.clear()
            st.success("Demo reset. Run the agent to start again.")
        if b.button("Cancel", key="confirm_no"):
            st.session_state["confirm_reset"] = False
            st.rerun()


def render_upload(cfg: dict, queue_page) -> None:
    st.markdown('<div class="mq-sub">Compare two files yourself</div>', unsafe_allow_html=True)
    st.caption("Upload an old and a new version (TXT or PDF). They go through the same reading and checks. "
               "This needs a Groq key.")
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
    use_saved = st.checkbox("Use saved run", value=not _has_key(cfg), key="use_saved",
                            help="Replays the saved AI answers instead of calling the model.")
    clicked = st.button("Run agent", key="run_agent", type="primary")
    badge_slot = st.empty()
    st.markdown('<div class="mq-sub">Live log</div>', unsafe_allow_html=True)
    log_slot = st.empty()
    if clicked:
        st.session_state["agent_result"] = _run(cfg, use_saved, log_slot, badge_slot)
    result = st.session_state.get("agent_result")
    _show_badge(badge_slot, result.status if result else "ready")
    log_slot.markdown(log_html(result.log if result else [], cfg.get("ui", {})), unsafe_allow_html=True)
    if result:
        render_result(result)
        _queue_link(queue_page)
    render_actions(cfg)
    render_upload(cfg, queue_page)
