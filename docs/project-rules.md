# Maya: project rules

Maya is a local Streamlit app for Jon's eDelta assignment (payroll regulatory change analysis). An AI agent
watches policy sources, finds what changed, works out who is affected and what it costs, approves clear
changes by rule, sends anything unclear to a reviewer, and shows every step live.
Team: Pavan and Anu, split 50/50 (see `docs/plan.md`, Work split). Demo: Mon Nov 2, 2026, 4:00 PM ET.

## Read before any work

1. `docs/requirements.md`: the source of truth. Jon's brief (B) wins over everything. Every change must
   trace to a requirement ID; say which one in the pull request.
2. `docs/plan.md`: how each requirement is met (data, rules, screens, tests, timeline).
3. `docs/design.md`: before touching any UI.
4. `docs/expected.md`: the hand-written expected answers for the team's own data.

Never drift from these. If a change seems to conflict with them, stop and discuss before writing code.
Do not add features outside the requirement list. Do not change the expected answers in
`docs/expected.md`; if code disagrees with them, the code is wrong.

## Hard rules

- **No em dashes anywhere** (UI copy, comments, docstrings, docs, commit messages). Use commas, colons or
  "to". No emojis in the README or UI. No section signs and no middle dots as separators in the UI.
- **AI reads and judges; code checks and calculates.** The AI plans the agent run, extracts facts from each
  section, judges substantive vs wording only, and writes headlines, actions and reasons. Code reads
  files, splits sections, checks every AI answer, parses dates, matches employees (R1 to R4), calculates
  money, routes findings and saves everything. The AI never matches employees and never calculates money.
- **Every AI answer is verified** (requirements V1 to V3 in code, V6 by a person): JSON must fit the schema
  in `maya/ai/schemas.py`; every quoted sentence and value must appear word for word in the source section;
  numbers and dates are recomputed independently by code and compared with the AI's claim; dates must be in
  an accepted format. A failed check gets one retry with the reason; a second failure sends the finding to
  the reviewer with "AI answer failed its check."
- **Flag, never assume.** Missing date, unclear date ("To be determined", "TBD", "pending"), unreadable
  date format (03/04/2027), conflicting values, new wording: each is a named flag shown in plain English.
- **Statuses are only pending, approved, dismissed.** "Ready to approve" is a label on a pending finding.
  Dismiss requires a comment. Review history is append-only. Automatic decisions are shown as
  "Auto-approved"; the UI never shows the internal rule name.
- **Money:** `decimal.Decimal`, rounded half up to the cent, only in `maya/cost.py`. Never floats.
- **Only synthetic data goes to a model.** The API key comes from an environment variable or
  `.streamlit/secrets.toml`, which is in `.gitignore`. Never print or commit a key. A valid Groq key starts
  with `gsk_`.
- **Unreadable input is an error, never "no changes."**
- **Data-driven (P8):** jurisdictions, files, sources and the as-of date come from `maya.config.yaml`.

## Stack and commands

- Python 3.11+, Streamlit, SQLite (stdlib `sqlite3`), pandas, pdfplumber, pydantic, openai (client used for
  Groq), requests, PyYAML, fpdf2, pytest. Ask before adding any other dependency.
- Install: `pip install -r requirements.txt`
- Run: `streamlit run app.py`
- Test: `pytest -q` (must pass offline; uses saved AI replies in `tests/fixtures/ai/`)
- Live AI smoke test (by hand only): `pytest -q -m live`

## AI setup (Groq free tier only)

- One OpenAI-compatible client in `maya/ai/llm.py`. Settings: `MAYA_LLM_PROVIDER` (groq or replay),
  `MAYA_LLM_MODEL`, `GROQ_API_KEY`. Base URL: `https://api.groq.com/openai/v1`. No other provider.
- Models (tested in an earlier trial, check Groq's current docs and limits before relying on them):
  `openai/gpt-oss-120b` with reasoning effort low for reading sections, `openai/gpt-oss-20b` for planning
  the agent run. Free limits seen: 30 requests a minute, 1,000 a day, 8,000 tokens a minute, 200,000 a day.
  One full run is about 15 to 25 calls and about 30,000 tokens.
- Temperature 0. Every prompt and reply is saved with the run (`agent_runs`).
- Replay: a successful run is saved to `data/replays/`. If Groq is unreachable, the agent replays it and
  every log line says "replayed from saved run". If neither Groq nor a matching replay exists, show which
  setting is missing. Never silently continue.

## Known pitfalls (found in an earlier trial, avoid them)

- Do not hash a folder fingerprint twice. Fingerprint once, compare once.
- The agent's `watch_sources` tool must not loop: cap steps at 25 and refuse repeated identical calls.
- Search the Federal Register once per run, and say so in the log.
- The planner invented numbers ("$2,500", "120 employees") when not given facts. Feed it the real section
  facts, and validate its final summary against the data before showing it.
- The final summary must never claim automatic approval when the mode is Pre-approve.
- A flag "new wording" applies only when both versions of a section exist.
- Strip only unsupported keys from JSON schemas for Groq; never delete the `title` field of the answer.
- In Streamlit, a pair of dollar signs renders as math. Escape dollar signs in every displayed string.
- Selectbox and multiselect filters need explicit placeholders; do not show "Choose an option".
- Rerun the page after each agent step so buttons and side panels are not stale.

## Repo layout

```
app.py                     Streamlit entry, sidebar, page routing
maya.config.yaml           files, jurisdictions, sources, as-of date (P8)
maya/models.py             shared data contract (Finding, Employee, ImpactRow, Decision, enums)
maya/ingest.py             read TXT and PDF, normalise text
maya/split.py              split into numbered sections
maya/checks.py             verify AI answers against source text, recompute numbers, parse dates
maya/flags.py              flag rules
maya/timing.py             current / future / unknown against the as-of date
maya/findings.py           compare two documents into findings
maya/pipeline.py           run the AI reading and checks end to end
maya/ai/llm.py             Groq client, retries, logging
maya/ai/prompts.py         prompt text (definitions from the plan, word for word)
maya/ai/schemas.py         pydantic schemas for every AI answer
maya/ai/replay.py          save and replay runs
maya/agent.py              agent loop, tools, run log, modes
maya/sources.py            watched sources, fingerprints, fictional site, Federal Register
maya/site.py               fictional site index, publish next version, reset
maya/employees.py          load and validate employees.csv
maya/impact.py             matching rules R1 to R4
maya/cost.py               weekly cost, overtime, totals (X1 later)
maya/routing.py            auto-approval rule, approval mode, review reasons
maya/db.py                 SQLite: reviews, agent_runs, document_versions
maya/export.py             the two CSVs
maya/ui/                   one module per page, style.py for theme CSS
data/policies/             bulletins v1 and v2 (TXT and PDF)
data/company_policies/     company pay policy pair (identical: the no-change case)
data/policy_site/          the fictional source the agent watches
data/employees.csv         80 synthetic employees, three jurisdictions, onsite/hybrid/remote
notes/                     working notes behind docs/expected.md
scripts/                   make_policies.py (rebuilds policy TXT and PDF), reset_demo.py
tests/                     unit tests, tests/fixtures/ai/ saved AI replies
docs/                      requirements, plan, design, expected, decisions/, worklog.md
```

## Shared labels (use exactly these strings everywhere)

- Jurisdictions: the names defined in `maya.config.yaml` (three required)
- Categories: `wages`, `tax_rate`, `filing_deadline`, `reporting`, `unclear`
- Change types: `substantive`, `wording_only`, `added`, `removed`
- Timing: `current`, `future`, `unknown`
- Statuses: `pending`, `approved`, `dismissed`
- Employment types: `hourly_full_time`, `hourly_part_time`, `salaried_exempt`, `contractor`
- Impact results: `affected`, `not_affected`, `excluded`, `matched_no_estimate`, `needs_review` (hybrid only)
- Flags: `missing_date`, `unclear_date`, `unreadable_date_format`, `conflicting_values`, `new_wording`,
  `classification_warning`
- Work arrangements: `onsite`, `hybrid`, `remote`
- Accepted date formats: `YYYY-MM-DD`, `January 1, 2027`, `Jan 1, 2027` (any year)
- Log tags: `PLAN`, `TOOL`, `AI`, `CHECK`, `RESULT`

## How we work

- Plan first: for anything bigger than a small fix, write down the plan (files, functions, tests,
  requirement IDs) and agree before building.
- Tests first for matching, cost, checks, flags, timing and routing. Use the expected answers in `docs/expected.md`.
- Branch per change, small commits: `feat(impact): R1 wage matching (B3)`. Types: feat, fix, test, docs,
  refactor, chore. Nobody pushes to `main`. The other person reviews every pull request.
- Each person commits their own modules. Paired work gets a `Co-authored-by:` line. Never reassign commits.
- After each finished piece: update `CHANGELOG.md` (under Unreleased) and add a dated line to
  `docs/worklog.md` (who, what, requirement IDs).
- Keep functions small and typed; docstrings say what and why in plain words.
- Explain non-obvious code in a short comment. Both people must be able to explain every module to Jon.
