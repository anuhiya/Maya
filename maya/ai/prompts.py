"""Prompt text for planning, reading and comparing (B1, B9)."""

# Definitions from docs/plan.md "Reading and comparing", word for word.
CATEGORY_DEFINITIONS = (
    "wages = a required hourly pay amount in dollars, such as a minimum wage; tax rate = a percentage "
    "withheld or contributed; filing deadline = when a report or return must be filed; reporting = what must "
    "be reported, or given or shown to employees (pay statements, notices). "
    'If none fits, answer "unclear".'
)

CHANGE_TYPE_DEFINITIONS = (
    '- Substantive: any value, date, unit, jurisdiction, category, scope or obligation changes, or new '
    'required content appears. "$15" and "$15.00" are the same value. "shall" and "must" mean the same; '
    '"may" does not.\n'
    "- Wording only: the sentence changed but every fact above is the same.\n"
    "- Added or removed: the section exists in only one version."
)

_LABELS = (
    "Use these exact labels in the JSON answer. Category: wages, tax_rate, filing_deadline, reporting, "
    "unclear. Change type: substantive, wording_only, added, removed."
)

_COPY_EXACTLY = (
    "Every quote and every value must be copied exactly from the section text, character for character. "
    "Never paraphrase a quote and never calculate or guess a value. If something is not in the text, "
    "say so (effective date: missing; value: null) instead of inventing it. Answer with JSON only."
)


def _section_block(label, section):
    return f"{label} section {section.number}, titled {section.title!r}:\n{section.text}"


def read_section(section):
    """Prompt for read_section: the facts in one section (B1). Returns (system, user)."""
    system = (
        "You read one numbered section of a payroll policy and extract its facts. "
        "Extract: section, title, jurisdiction, effective date exactly as written (or \"missing\"), "
        "value (the dollar amount, percentage or day count the rule sets, digits exactly as written in the rule sentence, without $ or %; null if the rule sets none), unit (dollars per hour, percent, days), calendar or "
        "business days, obligation (shall, must, may), category, the rule sentence quoted, and the date "
        "line quoted.\n\n"
        f"Category definitions: {CATEGORY_DEFINITIONS}\n\n{_LABELS}\n\n{_COPY_EXACTLY}"
    )
    return system, _section_block("Read", section)


def compare_section(old, new):
    """Prompt for compare_section: how one section changed (B2). Either side may be None. Returns (system, user)."""
    system = (
        "You compare one section of a payroll policy between the old and the new version. "
        "Give the change type, which facts changed (value, date, unit, jurisdiction, category, scope, "
        "obligation) and a one-line reason.\n\n"
        f"Change type definitions:\n{CHANGE_TYPE_DEFINITIONS}\n\n"
        f"Category definitions: {CATEGORY_DEFINITIONS}\n\n{_LABELS}\n\n{_COPY_EXACTLY}"
    )
    old_text = _section_block("Old", old) if old is not None else "Old version: this section does not exist."
    new_text = _section_block("New", new) if new is not None else "New version: this section does not exist."
    return system, f"{old_text}\n\n{new_text}"


def explain_finding(finding):
    """Prompt for explain_finding: reviewer wording for one finding (A2, A3). Returns (system, user)."""
    system = (
        "You write the reviewer-facing wording for one policy change: a headline, a recommended action, "
        "an owner (a team, not a person) and a one-line reason for the routing. Use only the facts given. "
        "Do not add numbers, employee counts or dollar amounts that are not in the facts, and never say "
        "a finding is approved. Answer with JSON only."
    )
    facts = {
        "section": finding.section,
        "jurisdiction": finding.jurisdiction,
        "category": finding.category.value,
        "change_type": finding.change_type.value,
        "old_value": None if finding.old_value is None else str(finding.old_value),
        "new_value": None if finding.new_value is None else str(finding.new_value),
        "unit": finding.unit,
        "effective_date": finding.effective_date,
        "timing": finding.timing.value,
        "flags": [f.name.value for f in finding.flags],
        "ai_reason": finding.ai_reason,
    }
    lines = "\n".join(f"{key}: {value}" for key, value in facts.items())
    return system, f"Facts:\n{lines}"


PLANNER_SYSTEM = (
    "You run Maya, a payroll policy watcher. Goal: find what changed since the approved version, who it "
    "affects, what it costs, and who must decide. Call exactly one tool at a time and read its result. "
    "Typical order: watch_sources; then for each change fetch_document, split_sections, read_sections; "
    "then check_answers, match_employees, price_changes, route_findings; search_federal_register once; "
    "then finish. Every call needs a plan: one sentence on why you call it. You cannot approve anything: "
    "only the routing rule or a person can. Federal Register results are informational only. If a tool "
    "result says REFUSED, change your next step instead of repeating it."
)


def run_summary(facts):
    """Prompt for run_summary: two or three plain sentences about the run. Returns (system, user)."""
    system = (
        "You write the closing summary of one agent run for a payroll reviewer, in two or three plain "
        "sentences. Use only the facts given and copy every number exactly. Do not calculate, do not add "
        "dates, and never say anything is approved: findings wait for a person. Answer with JSON only."
    )
    return system, "Facts:\n" + "\n".join(f"{key}: {value}" for key, value in facts.items())
