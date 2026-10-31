"""Agent loop, tools, run log and approval modes (A2, A3, A4).

The model only chooses the next tool. Code runs every tool, refuses invalid or unsafe steps, checks the
final summary against the data and saves the run. There is no approve tool: a finding can only be
approved by the routing rule's sign-off or a person.
"""
import json
import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Callable, Protocol

from maya import cost, db, routing, site, sources
from maya.ai import prompts
from maya.ai.llm import LLM, LLMError
from maya.ai.replay import ReplayError
from maya.employees import load_employees
from maya.findings import CompareResult
from maya.impact import match_finding
from maya.ingest import ReadingError, read_document
from maya.models import AgentLogLine, ChangeType, Finding, ImpactResult, ImpactRow, LogTag, Timing
from maya.pipeline import compare_documents
from maya.split import read_sections as split_document

GOAL = "Find what changed since the approved version, who it affects, what it costs, and who must decide."
NEW, FETCHED, SPLIT, READ, CHECKED, MATCHED, PRICED, ROUTED, FAILED = range(9)

# name: (description, argument name or None). Every tool also takes a required "plan".
TOOLS = {
    "watch_sources": ("Fingerprint the watched sources and list the documents that changed.", None),
    "fetch_document": ("Fetch the old and new document of one change.", "change"),
    "split_sections": ("Split the old and new document of one change into numbered sections.", "change"),
    "read_sections": ("AI reads and compares the changed sections of one change; code verifies each answer.",
                      "change"),
    "check_answers": ("Show the result of the code checks V1 to V3 on every AI answer so far.", None),
    "match_employees": ("Code matches employees to the findings from trusted sources.", None),
    "price_changes": ("Code calculates the weekly cost of the matched findings.", None),
    "route_findings": ("Code decides which findings are ready to approve and which need a reviewer.", None),
    "search_federal_register": ("Search the Federal Register once for minimum wage and payroll rules. "
                                "Informational only.", None),
    "finish": ("End the run. The AI writes a summary and code checks it against the data.", None),
}
_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")
_CLAIMS_APPROVAL = re.compile(r"approved|approves|auto-approv|has been approv", re.IGNORECASE)


class Refused(Exception):
    """A step the code will not run."""


class Planner(Protocol):
    def next(self, messages: list[dict], tools: list[dict]) -> tuple[str, dict]: ...


class LLMPlanner:
    """The planner model (openai/gpt-oss-20b) choosing tools through the LLM client."""

    def __init__(self, llm: LLM):
        self.llm = llm

    def next(self, messages, tools):
        answer = self.llm.plan(messages, tools).answer
        return answer["name"], answer["arguments"]


def tool_specs() -> list[dict]:
    specs = []
    for name, (description, argument) in TOOLS.items():
        props = {"plan": {"type": "string", "description": "One sentence: why you call this tool now."}}
        if argument:
            props[argument] = {"type": "string", "description": "Change ID from watch_sources, such as c1."}
        specs.append({"type": "function", "function": {
            "name": name, "description": description,
            "parameters": {"type": "object", "properties": props, "required": list(props),
                           "additionalProperties": False}}})
    return specs


@dataclass
class ChangeState:
    id: str
    change: sources.SourceChange
    stage: int = NEW
    result: CompareResult | None = None
    error: str = ""

    @property
    def label(self) -> str:
        return f"{self.change.old.name} -> {self.change.new.name}"


@dataclass
class RunResult:
    status: str  # finished or stopped
    summary: str
    log: list[AgentLogLine]
    findings: list[Finding]
    rows: list[ImpactRow]
    routes: dict[str, routing.Route]
    in_effect: Decimal
    coming: Decimal
    informational: list[sources.InformationalItem]
    steps: int


def _money(value: Decimal) -> str:
    return f"{value:.2f}"


class Agent:
    def __init__(self, cfg: dict, planner: Planner, llm: LLM, conn, on_line: Callable | None = None,
                 federal_register_get: Callable | None = None):
        self.cfg, self.planner, self.llm, self.conn, self.on_line = cfg, planner, llm, conn, on_line
        self.fr_get = federal_register_get or sources._get
        self.max_steps = cfg.get("agent", {}).get("max_steps", 25)
        self.replayed = llm.provider == "replay"
        self.log: list[AgentLogLine] = []
        self.watch: sources.WatchResult | None = None
        self.changes: dict[str, ChangeState] = {}
        self.findings: list[Finding] = []
        self.trusted: dict[str, bool] = {}
        self.rows: list[ImpactRow] = []
        self.routes: dict[str, routing.Route] = {}
        self.informational: list[sources.InformationalItem] = []
        self.searched = False
        self.summary = ""
        self.finished = False

    def emit(self, tag: LogTag, text: str) -> None:
        line = AgentLogLine(tag=tag, text=text, at=db.utcnow(), replayed=self.replayed)
        self.log.append(line)
        if self.on_line:
            self.on_line(line)

    def check(self, passed: bool, text: str) -> None:
        self.emit(LogTag.CHECK, ("Passed: " if passed else "Failed: ") + text)

    def run(self) -> RunResult:
        started = db.utcnow()
        messages = [{"role": "system", "content": prompts.PLANNER_SYSTEM}, {"role": "user", "content": GOAL}]
        specs, seen_calls, steps = tool_specs(), set(), 0
        while steps < self.max_steps and not self.finished:
            steps += 1
            try:
                name, args = self.planner.next(messages, specs)
            except (LLMError, ReplayError) as err:
                self.check(False, f"The planner gave no usable step: {err}")
                break
            call_id = f"call_{steps}"
            result = self._step(name, args, seen_calls)
            messages += [
                {"role": "assistant", "content": None, "tool_calls": [{
                    "id": call_id, "type": "function",
                    "function": {"name": name, "arguments": json.dumps(args, sort_keys=True)}}]},
                {"role": "tool", "tool_call_id": call_id, "content": result},
            ]
        if not self.finished:
            self.check(False, f"The run stopped after {steps} steps without finishing.")
            self.summary = self._built_summary()
        if self.finished:
            sources.commit(self.conn, self._to_commit())
        db.save_run(self.conn, goal=GOAL, log=[line.model_dump(mode="json") for line in self.log],
                    started_at=started, exchanges=self.llm.records, summary=self.summary)
        in_effect, coming = self._totals()
        return RunResult("finished" if self.finished else "stopped", self.summary, self.log, self.findings,
                         self.rows, self.routes, in_effect, coming, self.informational, steps)

    def _step(self, name: str, args: dict, seen_calls: set) -> str:
        shown = {k: v for k, v in args.items() if k != "plan"} if isinstance(args, dict) else args
        try:
            self._validate(name, args)
            self.emit(LogTag.PLAN, args["plan"].strip())
            self.emit(LogTag.TOOL, f"{name}({json.dumps(shown, sort_keys=True)[1:-1]})")
            key = (name, json.dumps(shown, sort_keys=True))
            if key in seen_calls:
                raise Refused("this exact call was already made; choose a different step")
            result = getattr(self, f"_{name}")(args)
            seen_calls.add(key)  # only a call that ran counts; a refused one may be valid later
            return result
        except Refused as err:
            self.check(False, f"Refused {name}: {err}")
            return f"REFUSED: {err}. {self._next_hint()}"
        except (ReadingError, LLMError, ReplayError, OSError) as err:
            self.check(False, f"{name} failed: {err}")
            return f"FAILED: {err}"

    def _next_hint(self) -> str:
        """What the code expects next, so a refused planner can recover."""
        if self.watch is None:
            return "Next step: watch_sources."
        for stage, tool in ((NEW, "fetch_document"), (FETCHED, "split_sections"), (SPLIT, "read_sections")):
            waiting = [c.id for c in self.changes.values() if c.stage == stage]
            if waiting:
                return f"Next step: {tool} for {waiting[0]}."
        for stage, tool in ((READ, "check_answers"), (CHECKED, "match_employees"), (MATCHED, "price_changes"),
                            (PRICED, "route_findings")):
            if any(c.stage == stage for c in self.changes.values()):
                return f"Next step: {tool}."
        return "Next step: finish." if self.searched else "Next step: search_federal_register."

    def _validate(self, name: str, args) -> None:
        if name not in TOOLS:
            raise Refused(f"{name!r} is not a tool")
        if not isinstance(args, dict):
            raise Refused("arguments must be an object")
        argument = TOOLS[name][1]
        extra = set(args) - {"plan", argument}
        if extra:
            raise Refused(f"unexpected argument {sorted(extra)[0]!r}")
        if not isinstance(args.get("plan"), str) or not args["plan"].strip():
            raise Refused("every call needs a plan")
        if argument and not isinstance(args.get(argument), str):
            raise Refused(f"{argument} is required")

    # tools -----------------------------------------------------------------------------------

    def _change(self, args: dict, stage: int) -> ChangeState:
        if self.watch is None:
            raise Refused("call watch_sources first")
        state = self.changes.get(args["change"])
        if state is None:
            raise Refused(f"unknown change {args['change']!r}")
        if state.stage != stage:
            raise Refused(f"{state.id} is not ready for this step")
        return state

    def _ready(self, stage: int, what: str) -> list[ChangeState]:
        ready = [c for c in self.changes.values() if c.stage == stage]
        if not ready:
            raise Refused(f"no change is ready for {what}")
        return ready

    def _watch_sources(self, args: dict) -> str:
        if self.watch is not None:
            raise Refused("sources were already watched in this run")
        self.watch = sources.watch_sources(self.cfg, self.conn)
        for n, change in enumerate(self.watch.changes, 1):
            self.changes[f"c{n}"] = ChangeState(f"c{n}", change)
        lines = [f"{c.id}: {c.label} ({c.change.source}, {'trusted' if c.change.trusted else 'not trusted'})"
                 for c in self.changes.values()]
        skipped = f"Unchanged, skipped: {', '.join(self.watch.unchanged) or 'none'}."
        self.emit(LogTag.RESULT, f"{len(lines)} changed document pair(s). {skipped}")
        for line in lines:
            self.emit(LogTag.RESULT, line)
        return "\n".join(lines + [skipped]) if lines else f"No changes. {skipped}"

    def _fetch_document(self, args: dict) -> str:
        state = self._change(args, NEW)
        sizes = [len(read_document(d.path)) for d in (state.change.old, state.change.new)]
        state.stage = FETCHED
        self.emit(LogTag.RESULT, f"{state.label}: fetched {sizes[0]} and {sizes[1]} characters.")
        return f"{state.id} fetched."

    def _split_sections(self, args: dict) -> str:
        state = self._change(args, FETCHED)
        old, new = (split_document(d.path) for d in (state.change.old, state.change.new))
        state.stage = SPLIT
        self.emit(LogTag.RESULT, f"{state.label}: {len(old)} sections and {len(new)} sections.")
        return f"{state.id} split: {len(old)} old sections, {len(new)} new sections."

    def _read_sections(self, args: dict) -> str:
        state = self._change(args, SPLIT)
        before = len(self.llm.records)
        try:
            result = compare_documents(state.change.old.path, state.change.new.path, self.llm, self.cfg)
        except (ReadingError, LLMError, ReplayError) as err:
            state.stage, state.error = FAILED, str(err)
            raise
        finally:
            made = self.llm.records[before:]
            if made:
                models = ", ".join(sorted({r["model"] for r in made}))
                self.emit(LogTag.AI, f"{len(made)} answers read and compared by {models}.")
        state.result, state.stage = result, READ
        self.findings += result.findings
        for finding in result.findings:
            self.trusted[finding.finding_id] = result.trusted
        self.emit(LogTag.RESULT, f"{state.label}: {len(result.findings)} findings, {result.summary}.")
        return f"{state.id} read: {len(result.findings)} findings, {result.summary}."

    def _check_answers(self, args: dict) -> str:
        ready = self._ready(READ, "checking")
        failed = total = 0
        for state in ready:
            for finding in state.result.findings:
                for result in finding.check_results:
                    total += 1
                    if not result.passed:
                        failed += 1
                        self.check(False, f"{finding.section} {result.check}: {result.detail}")
            state.stage = CHECKED
        if total - failed:
            self.check(True, f"{total - failed} of {total} code checks on AI answers.")
        text = f"{total - failed} of {total} checks passed. A finding with a failed check goes to the reviewer."
        self.emit(LogTag.RESULT, text)
        return text

    def _match_employees(self, args: dict) -> str:
        ready = self._ready(CHECKED, "matching")
        loaded = load_employees(cfg=self.cfg)
        if not loaded.ok:
            raise Refused("the employee file has problems; fix it first")
        matched = 0
        for state in ready:
            state.stage = MATCHED
            if not state.change.trusted:
                self.check(False, f"{state.change.source} is not trusted: {state.label} is not matched to employees.")
                continue
            for finding in state.result.findings:
                rows = match_finding(finding, loaded.employees, self.cfg)
                self.rows += rows
                matched += sum(r.result is ImpactResult.AFFECTED for r in rows)
        text = f"{matched} employees affected."
        self.emit(LogTag.RESULT, text)
        return text

    def _price_changes(self, args: dict) -> str:
        for state in self._ready(MATCHED, "pricing"):
            state.stage = PRICED
        in_effect, coming = self._totals()
        text = f"Weekly increase in effect ${_money(in_effect)}, coming ${_money(coming)}."
        self.emit(LogTag.RESULT, text)
        return text

    def _route_findings(self, args: dict) -> str:
        for state in self._ready(PRICED, "routing"):
            state.stage = ROUTED
            for finding in state.result.findings:
                self.routes[finding.finding_id] = routing.route(
                    finding, trusted=state.change.trusted, jurisdictions=self.cfg["jurisdictions"])
        ready, reviewer, none = self._route_counts()
        text = f"{ready} ready to approve, {reviewer} for the reviewer, {none} wording only. All stay pending."
        self.emit(LogTag.RESULT, text)
        return text

    def _search_federal_register(self, args: dict) -> str:
        self.searched = True
        self.informational, error = sources.search_federal_register(self.cfg, self.fr_get)
        if error:
            self.check(False, error)
            return error
        text = (f"{len(self.informational)} Federal Register item(s), informational only. "
                "They are not matched to employees or priced.")
        self.emit(LogTag.RESULT, text)
        for item in self.informational:
            self.emit(LogTag.RESULT, f"Informational: {item.title} ({item.date}) {item.url}")
        return text

    def _finish(self, args: dict) -> str:
        if self.watch is None:
            raise Refused("call watch_sources first")
        open_changes = [c.id for c in self.changes.values() if c.stage not in (ROUTED, FAILED)]
        if open_changes:
            raise Refused(f"{', '.join(open_changes)} not finished")
        if not self.searched:
            raise Refused("search_federal_register has not run")
        built = self._built_summary()
        facts = self._facts()
        before = len(self.llm.records)
        try:
            system, user = prompts.run_summary(facts)
            text = self.llm.call("run_summary", system, user, role="planner").answer.summary.strip()
            self.emit(LogTag.AI, f"Summary written by {self.llm.records[before]['model']}.")
            problem = self._summary_problem(text, facts)
        except (LLMError, ReplayError) as err:
            text, problem = built, f"no AI summary: {err}"
        if problem:
            self.check(False, f"Summary replaced by the code-built summary: {problem}")
            text = built
        else:
            self.check(True, "Every number in the summary is in the data and nothing is claimed approved.")
        self.summary, self.finished = text, True
        self.emit(LogTag.RESULT, text)
        return "Run finished."

    # checks and numbers ------------------------------------------------------------------------

    def _totals(self) -> tuple[Decimal, Decimal]:
        totals = cost.sum_by_timing(self.rows)
        return totals[Timing.CURRENT], totals[Timing.FUTURE]

    def _route_counts(self) -> tuple[int, int, int]:
        none = sum(f.change_type is ChangeType.WORDING_ONLY for f in self.findings if f.finding_id in self.routes)
        ready = sum(r.ready for r in self.routes.values())
        return ready, len(self.routes) - ready - none, none

    def _facts(self) -> dict:
        in_effect, coming = self._totals()
        ready, reviewer, none = self._route_counts()
        return {
            "document pairs compared": len(self.changes),
            "findings": len(self.findings),
            "ready to approve": ready,
            "for the reviewer": reviewer,
            "wording only": none,
            "employees affected": sum(r.result is ImpactResult.AFFECTED for r in self.rows),
            "weekly increase in effect": f"${_money(in_effect)}",
            "weekly increase coming": f"${_money(coming)}",
            "informational Federal Register items": len(self.informational),
        }

    def _built_summary(self) -> str:
        f = self._facts()
        return (f"Compared {f['document pairs compared']} document pair(s): {f['findings']} findings, "
                f"{f['ready to approve']} ready to approve, {f['for the reviewer']} for the reviewer, "
                f"{f['wording only']} wording only. {f['employees affected']} employees affected, "
                f"{f['weekly increase in effect']} a week in effect and {f['weekly increase coming']} coming. "
                f"{f['informational Federal Register items']} informational Federal Register item(s). "
                "Every finding stays pending until a person signs off.")

    def _summary_problem(self, text: str, facts: dict) -> str | None:
        if _CLAIMS_APPROVAL.search(text):
            return "it claims something is approved"
        allowed = {n.replace(",", "") for n in _NUMBER.findall(" ".join(str(v) for v in facts.values()))}
        stray = [n for n in _NUMBER.findall(text) if n.replace(",", "").rstrip(".") not in allowed]
        return f"the number {stray[0]} is not in the data" if stray else None

    def _to_commit(self) -> list[sources.Doc]:
        failed = {d.fingerprint for c in self.changes.values() if c.stage == FAILED
                  for d in (c.change.old, c.change.new)}
        return [d for d in self.watch.unseen if d.fingerprint not in failed]


def publish_next_version(cfg: dict) -> list[str]:
    """The live-change demo action: publish the held-back policy version on the fictional site."""
    return site.publish_next(cfg)


def start_over(cfg: dict) -> None:
    """Same logic as scripts/reset_demo.py: site, database with fingerprints, and uploads."""
    site.reset(cfg)
