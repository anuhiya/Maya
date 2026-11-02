"""Runs the agent on a background thread so leaving a page never stops it (A4, A5).

The page polls this object. Every step leaves a snapshot (see Agent.snapshot), so the live view can
show any step again, for live runs and saved replays alike. Streamlit is never called from the thread.
"""
import threading
import time

from maya import agent, db
from maya.ai.llm import LLM, LLMError
from maya.ai.replay import ReplayError

SAVED_RUN = "agent_demo"
_runs: dict[str, "AgentRun"] = {}
_lock = threading.Lock()


class GatedPlanner:
    """Wraps a planner so a stepping run waits for permission before asking it for each step."""

    def __init__(self, planner, run):
        self.planner, self.run = planner, run

    def next(self, messages, tools):
        self.run.wait_for_permission()
        return self.planner.next(messages, tools)


class AgentRun:
    def __init__(self, cfg: dict, use_saved: bool, step_mode: bool = False, planner=None, llm=None,
                 federal_register_get=None):
        self.cfg, self.use_saved, self.step_mode = cfg, use_saved, step_mode
        self._planner, self._llm, self._fr_get = planner, llm, federal_register_get
        self.lines, self.events = [], []
        self.status = "running"  # running, finished, stopped, error
        self.error = ""
        self.result = None
        self.current: tuple | None = None  # (step number, tool, argument) of the step being run
        self.waiting = False  # a stepping run is waiting for Next step
        self._permits = threading.Semaphore(0)
        self._thread = threading.Thread(target=self._work, daemon=True)

    def start(self) -> "AgentRun":
        self._thread.start()
        return self

    def join(self, timeout: float | None = None) -> None:
        self._thread.join(timeout)

    @property
    def running(self) -> bool:
        return self.status == "running"

    def next_step(self) -> None:
        self._permits.release()

    def release_all(self) -> None:
        """Skip to end: stop waiting for permission from now on."""
        self.step_mode = False
        self._permits.release()

    def wait_for_permission(self) -> None:
        if self.step_mode:
            self.waiting = True
            self._permits.acquire()
            self.waiting = False

    def _make_llm(self):
        if self._llm is not None:
            return self._llm
        if self.use_saved:
            return LLM(cfg=self.cfg, env={"MAYA_LLM_PROVIDER": "replay", "MAYA_REPLAY_RUN": SAVED_RUN})
        return LLM(cfg=self.cfg)

    def _on_line(self, line):
        self.lines.append(line)
        if line.replayed:  # a saved run plays at a readable speed
            time.sleep(self.cfg.get("ui", {}).get("replay_line_delay", 0))

    def _on_step_start(self, n, name, args):
        self.current = (n, name, args.get("change") if isinstance(args, dict) else None)

    def _work(self):
        try:
            llm = self._make_llm()
        except (LLMError, ReplayError) as err:
            self.status, self.error = "error", str(err)
            return
        conn = db.connect(self.cfg["_root"] / self.cfg["state"]["database"])
        try:
            runner = agent.Agent(self.cfg, None, llm, conn, on_line=self._on_line,
                                 federal_register_get=self._fr_get, saved_run=SAVED_RUN,
                                 on_step=self.events.append, on_step_start=self._on_step_start)
            runner.planner = GatedPlanner(self._planner or agent.LLMPlanner(llm), self)
            self.result = runner.run()
            self.status = self.result.status
        except Exception as err:  # never lose a run silently
            self.status, self.error = "error", f"{type(err).__name__}: {err}"
        finally:
            self.current = None
            conn.close()


def start(cfg: dict, use_saved: bool, step_mode: bool = False, **kw) -> AgentRun:
    run = AgentRun(cfg, use_saved, step_mode, **kw)
    with _lock:
        _runs["current"] = run
    return run.start()


def current() -> AgentRun | None:
    return _runs.get("current")


def clear() -> None:
    with _lock:
        _runs.pop("current", None)
