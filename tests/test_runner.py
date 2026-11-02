"""The background run and page state: leaving a page never blanks or stops the Agent page (A4, A5)."""
import time

from streamlit.testing.v1 import AppTest

from maya import runner
from maya.models import LogTag
from tests.test_agent import FR, ROOT, ReplayLLM, Scripted, env, flow  # noqa: F401  (env is a fixture)


def make_run(env, steps, **kw):
    cfg, _ = env
    cfg = {**cfg, "ui": {**cfg["ui"], "replay_line_delay": 0}}
    llm = ReplayLLM(cfg=cfg, env={"MAYA_LLM_PROVIDER": "replay", "MAYA_REPLAY_RUN": "run"})
    llm.summary = "Compared the documents."
    return runner.AgentRun(cfg, False, planner=Scripted(steps), llm=llm,
                           federal_register_get=lambda url, params: FR, **kw)


def test_run_finishes_on_its_own_thread_and_keeps_a_snapshot_per_step(env):
    run = make_run(env, flow(2)).start()
    run.join(60)
    assert run.status == "finished" and run.result and len(run.result.findings) == 9
    assert [e["n"] for e in run.events] == list(range(1, len(run.events) + 1))
    last = run.events[-1]
    assert last["tool"] == "finish" and last["finished"] and len(last["findings"]) == 9
    assert last["in_effect"] == "273.19" and last["coming"] == "142.80"
    assert last["lanes"]["ready"] + last["lanes"]["decision"] + last["lanes"]["wording"] == 9
    assert any(l.tag is LogTag.RESULT for l in run.lines)


def test_step_mode_waits_for_next_step_then_skip_to_end_finishes(env):
    run = make_run(env, flow(2), step_mode=True).start()
    for _ in range(100):
        if run.waiting:
            break
        time.sleep(0.02)
    assert run.waiting and run.events == [] and run.running
    run.next_step()
    for _ in range(100):
        if len(run.events) == 1 and run.waiting:
            break
        time.sleep(0.02)
    assert [e["tool"] for e in run.events] == ["watch_sources"]
    run.release_all()
    run.join(60)
    assert run.status == "finished" and len(run.result.findings) == 9


def test_a_refused_step_is_marked_in_its_snapshot(env):
    run = make_run(env, [("price_changes", {"plan": "too early"}), ("watch_sources", {"plan": "ok"})]).start()
    run.join(60)
    assert run.events[0]["refused"] and not run.events[1]["refused"]


def test_page_state_survives_leaving_the_page():
    def page():
        import streamlit as st

        from maya.ui import review_queue
        st.radio("page", ["queue", "other"], key="nav")
        if st.session_state["nav"] == "queue":
            st.selectbox("Jurisdiction", ["All jurisdictions", "New York City"], key="f_jurisdiction")
        review_queue.keep_context()

    at = AppTest.from_function(page, default_timeout=30).run()
    at.selectbox(key="f_jurisdiction").select("New York City").run()
    at.radio(key="nav").set_value("other").run()
    at.radio(key="nav").set_value("queue").run()
    assert at.selectbox(key="f_jurisdiction").value == "New York City"


def test_lost_run_shows_run_stopped_with_run_again_and_start_over(tmp_path):
    import shutil

    from maya.site import load_config
    shutil.copytree(ROOT / "data", tmp_path / "data", ignore=shutil.ignore_patterns("uploads"))
    shutil.copy(ROOT / "maya.config.yaml", tmp_path / "maya.config.yaml")
    cfg = load_config(tmp_path / "maya.config.yaml")

    def page(cfg):
        import streamlit as st

        from maya.ui import agent_activity
        st.session_state["run_started"] = True
        agent_activity.render(cfg=cfg)

    runner.clear()
    at = AppTest.from_function(page, kwargs={"cfg": cfg}, default_timeout=30).run()
    assert not at.exception and any("Run stopped" in w.value for w in at.warning)
    assert at.button(key="lost_again") and at.button(key="lost_over")
