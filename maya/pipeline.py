"""Run the AI reading and checks end to end (B1, B2, B8, B9, V1 to V3)."""
import logging
import re
from datetime import date
from pathlib import Path

from maya import flags as flag_rules
from maya.ai import prompts
from maya.ai.llm import LLM, LLMError
from maya.checks import check_v1, check_v2, check_v3
from maya.findings import CompareResult, build_finding, failed_finding, merge_checks
from maya.models import ChangeType, CheckResult, Finding, Section
from maya.site import load_config
from maya.split import read_sections, rule_text
from maya.timing import classify, parse_date

log = logging.getLogger("maya.pipeline")

_FAMILY_SUFFIX = re.compile(r"[_-]?v\d+$", re.IGNORECASE)
_NUMBER = re.compile(r"\$?\d+(?:,\d{3})*(?:\.\d+)?%?")


def _resolve(root: Path, path) -> Path:
    return (root / path).resolve()


def _source_for(path, cfg: dict) -> dict | None:
    """The configured source whose folder holds `path` (longest prefix wins), else None."""
    target = Path(path).resolve()
    best, best_depth = None, -1
    for source in cfg.get("sources", []):
        if not source.get("path"):
            continue
        base = _resolve(cfg["_root"], source["path"])
        if target.is_relative_to(base) and len(base.parts) > best_depth:
            best, best_depth = source, len(base.parts)
    return best


def policy_id(old_path, new_path, source: dict | None, cfg: dict) -> str:
    """Policy family from the config; the file name without its version only as a last resort."""
    paths = {Path(old_path).resolve(), Path(new_path).resolve()}
    for entry in (cfg.get("policies") or {}).values():
        listed = {_resolve(cfg["_root"], entry[k]) for k in ("old", "new", "old_pdf", "new_pdf", "pdf") if entry.get(k)}
        if paths & listed and entry.get("policy_family"):
            return entry["policy_family"]
    if source and source.get("policy_family"):
        return source["policy_family"]
    return _FAMILY_SUFFIX.sub("", Path(new_path).stem)


def _masked(section: Section | None) -> Section | None:
    """The rule sentence with every number hidden, so a changed value alone is not 'new wording'."""
    if section is None:
        return None
    return section.model_copy(update={"text": _NUMBER.sub("#", rule_text(section))})


def _tag(side: str, result: CheckResult) -> CheckResult:
    if result.passed:
        return result
    return result.model_copy(update={"detail": f"{side.capitalize()} version: {result.detail}"})


def _presence_check(old: Section | None, new: Section | None, change_type: ChangeType) -> CheckResult:
    """Added means only the new version exists, removed only the old; code knows this, not the AI."""
    expected = ChangeType.ADDED if old is None else ChangeType.REMOVED if new is None else None
    wrong = change_type != expected if expected else change_type in (ChangeType.ADDED, ChangeType.REMOVED)
    if wrong:
        return CheckResult(check="V3", passed=False,
                           detail=f"Change type {change_type.value!r} does not fit which versions of the section exist.")
    return CheckResult(check="V3", passed=True, detail="Change type fits the versions that exist.")


def _analyse(old: Section | None, new: Section | None, llm, note: str):
    """Read each side, compare, and check every answer. Returns (facts by side, compare answer, checks)."""
    sides = {"old": old, "new": new}
    facts, checks = {}, []
    for side, section in sides.items():
        if section is None:
            continue
        system, user = prompts.read_section(section)
        facts[side] = llm.call("read_section", system, user + note).answer.to_facts()
        checks.append(_tag(side, check_v1(section, facts[side])))
    system, user = prompts.compare_section(old, new)
    answer = llm.call("compare_section", system, user + note).answer
    old_f, new_f = facts.get("old"), facts.get("new")
    checks.append(check_v2(old, new, old_f.value if old_f else None, new_f.value if new_f else None,
                           answer.facts_changed))
    checks.append(_presence_check(old, new, answer.change_type))
    for side, section in sides.items():
        if section is not None:
            checks.append(_tag(side, check_v3(old, new, answer.change_type, facts[side], section)))
    return facts, answer, merge_checks(checks)


def _retry_note(failed: list[CheckResult]) -> str:
    problems = " ".join(f"{c.check}: {c.detail}" for c in failed)
    return ("\n\nYour previous answer failed these checks: " + problems +
            " Answer again. Copy every quote and value exactly from the section text.")


def _finding_for(old: Section | None, new: Section | None, *, llm, policy: str, source_file: str,
                 as_of: date) -> Finding:
    note = ""
    for attempt in range(2):  # one retry after a failed check
        try:
            facts, answer, checks = _analyse(old, new, llm, note)
        except LLMError as err:  # bad JSON twice: the client has already retried once
            log.warning("section %s: no usable AI answer: %s", (new or old).number, err)
            return failed_finding(policy=policy, source_file=source_file, old=old, new=new,
                                  checks=[CheckResult(check="format", passed=False, detail=str(err))])
        failed = [c for c in checks if not c.passed]
        if not failed:
            break
        log.warning("section %s failed %s (attempt %d)", (new or old).number,
                    ", ".join(c.check for c in failed), attempt + 1)
        note = _retry_note(failed)
    else:
        return failed_finding(policy=policy, source_file=source_file, old=old, new=new, checks=checks)

    old_f, new_f = facts.get("old"), facts.get("new")
    current = new_f or old_f
    flags = []
    if new is not None:  # a removed section has no date to judge
        date_flag = flag_rules.date_flag(new_f.effective_date)
        if date_flag:
            flags.append(date_flag)
    conflict = flag_rules.conflicting_values(rule_text(new or old))
    if conflict:
        flags.append(conflict)
    wording = flag_rules.new_wording(_masked(old), _masked(new))
    if wording:
        flags.append(wording)
    return build_finding(
        policy=policy, source_file=source_file, old=old, new=new, old_facts=old_f, new_facts=new_f,
        change_type=answer.change_type, reason=answer.reason, flags=flags,
        timing=classify(current.effective_date if new is not None else None, as_of), checks=checks)


def _order(number: str) -> tuple:
    return tuple(int(part) for part in number.split("."))


def compare_documents(old_path, new_path, llm=None, cfg=None) -> CompareResult:
    """Split both documents, read and compare the changed sections, verify every AI answer.

    Identical sections cost no AI call. Trust comes from the source whose folder holds the new file.
    """
    cfg = cfg or load_config()
    old_sections = {s.number: s for s in read_sections(old_path)}
    new_sections = {s.number: s for s in read_sections(new_path)}
    source = _source_for(new_path, cfg)
    policy = policy_id(old_path, new_path, source, cfg)
    root = cfg["_root"].resolve()
    new_resolved = Path(new_path).resolve()
    source_file = str(new_resolved.relative_to(root)) if new_resolved.is_relative_to(root) else str(new_path)
    as_of = parse_date(str(cfg["as_of_date"]))

    numbers = sorted(set(old_sections) | set(new_sections), key=_order)
    findings, identical = [], 0
    for number in numbers:
        old, new = old_sections.get(number), new_sections.get(number)
        if old is not None and new is not None and (old.title, old.text) == (new.title, new.text):
            identical += 1
            continue
        if llm is None:
            llm = LLM(cfg=cfg)
        findings.append(_finding_for(old, new, llm=llm, policy=policy, source_file=source_file, as_of=as_of))
    return CompareResult(findings=findings, identical=identical, total=len(numbers),
                         trusted=bool(source and source.get("trusted")),
                         source=source["name"] if source else None)
