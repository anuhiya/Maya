"""Write the hand-written saved AI replies for the main pair into tests/fixtures/ai/ (no network).

Facts (quotes, dates, jurisdiction) are copied from the section text; the judgments below are the
expected answers in docs/expected.md. Run again after a change to prompts or policy text.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from maya.ai import prompts  # noqa: E402
from maya.ai.llm import prompt_hash  # noqa: E402
from maya.ai.replay import save_run  # noqa: E402
from maya.site import load_config  # noqa: E402
from maya.split import read_sections, rule_text  # noqa: E402

RUN = "main_pair"
# section: category, unit, day_type, obligation, old value, new value, change type, facts changed, reason
JUDGMENTS = {
    "1.1": ("wages", "dollars per hour", None, "shall", "16.00", "17.25", "substantive",
            ["value", "date"], "The minimum wage rose from 16.00 to 17.25 and takes effect November 1, 2026."),
    "1.2": ("tax_rate", "percent", None, "shall", "2.7", "3.1", "substantive",
            ["value", "date"], "The contribution rate rose from 2.7 to 3.1 percent from January 1, 2027."),
    "1.3": ("reporting", None, None, "shall", None, None, "substantive",
            ["scope", "date"], "The pay statement must now also show the hours worked at each rate of pay."),
    "1.4": ("reporting", None, None, "shall", None, None, "added",
            [], "New section: a written wage notice must be given to each newly hired employee."),
    "2.1": ("wages", "dollars per hour", None, "shall", "14.50", "15.50", "substantive",
            ["value", "date"], "The minimum wage rose from 14.50 to 15.50 from January 1, 2027."),
    "2.2": ("filing_deadline", "days", "calendar", "shall", "30", "20", "substantive",
            ["value", "date"], "The filing deadline shortened from 30 to 20 calendar days."),
    "2.3": ("reporting", None, None, "shall", None, None, "substantive",
            ["scope", "date"], "The report is now due twice a year instead of once and the date line was removed."),
    "3.2": ("wages", None, None, None, None, None, "wording_only",
            [], "The sentence was reworded; the 40 hour threshold and the one and one-half rate are the same."),
    "3.3": ("filing_deadline", "days", "calendar", "shall", "20", "10", "substantive",
            ["value", "date"], "The reporting deadline shortened from 20 to 10 calendar days and the date is not decided."),
}
OBLIGATION_OVERRIDE = {("3.2", "new"): "must", ("3.2", "old"): "shall"}


def facts_reply(number, side, section):
    category, unit, day_type, obligation, old_v, new_v, *_ = JUDGMENTS[number]
    effective = section.effective_date
    return {
        "section": section.number, "title": section.title, "jurisdiction": section.jurisdiction,
        "effective_date": effective or "missing",
        "value": old_v if side == "old" else new_v, "unit": unit, "day_type": day_type,
        "obligation": OBLIGATION_OVERRIDE.get((number, side), obligation), "category": category,
        "rule_quote": rule_text(section),
        "date_quote": f"Effective Date: {effective}" if effective else None,
    }


def main():
    cfg = load_config()
    pair = cfg["policies"]["main_pair"]
    old = {s.number: s for s in read_sections(ROOT / pair["old"])}
    new = {s.number: s for s in read_sections(ROOT / pair["new"])}
    records = []

    def add(kind, system, user, reply):
        records.append({"kind": kind, "role": "reader", "prompt_hash": prompt_hash(system, user),
                        "system": system, "user": user, "reply": json.dumps(reply), "provider": "fixture",
                        "model": "hand-written", "replayed": False, "retries": 0})

    for number, judgment in JUDGMENTS.items():
        for side, sections in (("old", old), ("new", new)):
            if number in sections:
                system, user = prompts.read_section(sections[number])
                add("read_section", system, user, facts_reply(number, side, sections[number]))
        system, user = prompts.compare_section(old.get(number), new.get(number))
        add("compare_section", system, user,
            {"change_type": judgment[6], "facts_changed": judgment[7], "reason": judgment[8]})
    print(save_run(RUN, records, ROOT / "tests/fixtures/ai"))


if __name__ == "__main__":
    main()
