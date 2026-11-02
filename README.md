# eDelta Maya

Maya reads two versions of a payroll policy, finds what changed, works out which employees are affected and what it costs, and leaves every final decision to a person. On screen the app is called eDelta Maya. It was built for eDelta Consulting as the assignment "Payroll Regulatory Change Analysis and Impact Assessment".

One rule runs through everything: the AI reads and explains, code checks and calculates, and a person decides.

## Setup

Needs Python 3.11 or newer.

```
git clone https://github.com/anuhiya/Maya.git
cd Maya
git checkout feat/edelta-demo
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

AI key (free): create a Groq key at console.groq.com and save it in `.streamlit/secrets.toml`:

```
GROQ_API_KEY = "your key here"
```

That file is gitignored. Never commit it. Without a key the app still works from the saved runs in `data/replays/`, and it says which setting is missing.

Run the app:

```
streamlit run app.py
```

Run the tests (live AI calls are skipped; run them by hand with `pytest -q -m live`):

```
pytest -q
```

Put the demo back to its start (`--empty` also leaves every findings page empty until the agent has run once):

```
python scripts/reset_demo.py --yes [--empty]
```

## What is in the repository

- Source code: `app.py` and the `maya/` package.
- Sample policy documents: `data/policies/` (government bulletins, TXT and PDF), `data/company_policies/` (a company policy pair), `data/policy_site/` (the practice policy website the agent watches) and `data/policies/proposed/` (one illustrative bill and three real proposed bills).
- Synthetic employee CSV: `data/employees.csv` (80 employees in New York City, Los Angeles and Chicago).
- Tests: `tests/`. The matching and cost logic is covered in `test_impact.py`, `test_cost.py`, `test_total_cost.py` and `test_employees.py`. The AI checks are in `test_checks.py` and the approval rule in `test_routing.py`.
- Expected answers worked out by hand before the code: `docs/expected.md`.

## How it works (architecture)

1. A watcher fingerprints the sources (SHA-256) and spots a new or changed document.
2. The agent fetches it from the local policy website and checks the fingerprint against the site's index.
3. The document is split into numbered sections, each with a Jurisdiction line and an Effective Date line.
4. The AI reader compares each old and new section and answers in a fixed format, with quotes.
5. Code checks every answer: V1 quotes appear word for word, V2 numbers are recomputed in code, V3 type, jurisdiction and category are consistent.
6. Code matches employees with four explicit rules and calculates the weekly cost, with the written math.
7. Code routes each finding: Ready to approve (all eight conditions pass) or to a reviewer with the reason.
8. A person approves or dismisses (a comment is required to dismiss). Decisions are saved in SQLite and never edited.

Streamlit pages: Agent activity, Review queue, Employee impact, Proposed law, Review history, Export and Sources. The agent has ten tools and none of them approves. It stops after 25 steps, refuses repeated or out-of-order calls, and logs every step.

## How AI is used and verified

Two free Groq models: gpt-oss-120b reads and compares sections, gpt-oss-20b chooses the agent's next tool. The AI never matches employees, calculates money or approves anything. Its output is verified in layers: V1 grounding, V2 recomputation, V3 consistency, V4 answers fixed by hand in `docs/expected.md`, and V6 a person decides. If the planner model fails to pick a tool, code chooses the step, capped and logged as "Chosen by code, not the model (planner fallback)".

## Assumptions

- A standard week is 40 hours and hours above 40 are paid at 1.5 times. A year is 52 weeks.
- Example: E001 earns $17.06 and works 42 hours, so the rise to $17.25 costs 0.19 x 40 + 0.19 x 1.5 x 2 = $8.17 a week. The $273.19 a week in effect is $14,205.88 annualized.
- Employer FICA is 7.65 percent of the increase: $20.90 a week, $1,086.75 a year.
- An employee belongs to the jurisdiction of their work location, not their home.
- Matching rules: R1 wages (hourly staff below the new minimum; salaried exempt staff and contractors excluded), R2 tax rate, R3 filing deadline and R4 reporting (non-contractors in the jurisdiction; a new-hire rule matches no current employee).
- Policy files follow one layout. A missing or unclear date is flagged for a reviewer, never guessed.
- The data is synthetic. Place names are real; wage rates, rules and dates are illustrative. Real proposed bills are informational only and never added to the totals.

## Limitations

- Exact quotes show the AI did not invent text, not that it understood a real policy. A plausible misreading could pass, which is why a person decides.
- Hybrid employees work in two places with no recorded split of hours. They are flagged Needs review with an upper bound and never added to totals.
- Unemployment insurance changes are matched but not priced, and back pay is not calculated.
- Scanned PDFs are not supported. Overtime is weekly on standard hours, not timecards.
- Single local user: the reviewer name is typed, with no sign-in.
- The free AI tier limits tokens, so a full live read from scratch is slow and only a few fit in a day.
- Not built: the repeat-run check (V5) and the read-only connector for Claude Desktop (A8).

## Individual contributions

The work was split by module, as planned in `docs/plan.md`. The commit history is the record of who changed what.

- Pavan: document reading and splitting, the Groq client, prompts and answer formats, the findings pipeline, the agent and its live view, the policy website and reset script, the Agent activity page, the Sources page and the Proposed law page.
- Anu: the data models, the employee loader and the synthetic employee CSV, the checks on AI answers (V1 to V3), flags and timing, matching rules R1 to R4, cost calculation, the approval rule and review history, both CSV exports, and the Review queue, Employee impact and Review history pages.
- Together: the design, the expected answers, the requirements and the tests. AI coding tools (Claude Code) were used to speed up writing code. Design, rules and checks were decided by the team, and every number was checked against the answers worked out by hand.
