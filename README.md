# eDelta Maya

Maya is a payroll regulatory change analysis and impact assessment tool. It takes two versions of a payroll policy, works out what changed, checks which employees are affected, estimates what the change costs, and gives a reviewer the final say. The app shows up as "eDelta Maya" on screen, and the repository is called Maya.

The idea we kept coming back to is a simple division of labour. The AI does the reading, the code does the checking and the arithmetic, and a person makes every decision.

## Getting it running

You need Python 3.11 or newer.

```
git clone https://github.com/anuhiya/Maya.git
cd Maya
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

The AI part uses Groq's free tier. Create a key at console.groq.com and put it in `.streamlit/secrets.toml`:

```
GROQ_API_KEY = "your key here"
```

That file is gitignored, so please don't commit it. If there is no key, the app still runs: it replays the saved runs in `data/replays/` and tells you which setting is missing.

To run the tests:

```
pytest -q
```

A few of them call the live AI and are skipped by default. You can run those by hand with `pytest -q -m live`.

To put the demo back to its starting point:

```
python scripts/reset_demo.py --yes
```

Add `--empty` if you want every findings page to start blank until the agent has run once.

## Using the app

There are seven pages in the sidebar. A good first pass looks like this.

1. Open Agent activity and run the agent (or play the saved run). It checks the policy website, reads the new bulletin, and shows each step in a live log as it goes.
2. Open Review queue. The findings are ordered by cost. Open one to see the old and new text, the quoted source, who is affected and the written calculation. Approve it, or dismiss it with a comment.
3. Open Employee impact for the totals, the per-employee math and the employees who need a manual look.
4. Open Proposed law to see what a bill would cost if it passed. It covers one illustrative bill and three real proposed bills.
5. Review history keeps every decision, Export downloads the findings and the employee impact as CSV files, and Sources lists every document with its file fingerprint.

On Agent activity you can also press "Publish next version" to simulate a new bulletin appearing, or publish a custom change of your own, and then run the agent again.

## What is in the repository

- `app.py` and `maya/`: the application code.
- `data/policies/`, `data/company_policies/` and `data/policy_site/`: the sample policy documents, as TXT and PDF. `data/policies/proposed/` holds the proposed bills.
- `data/employees.csv`: the synthetic employee list, 80 people across New York City, Los Angeles and Chicago.
- `tests/`: the tests. Matching and cost are covered in `test_impact.py`, `test_cost.py`, `test_total_cost.py` and `test_employees.py`. The checks on AI answers are in `test_checks.py` and the approval rule is in `test_routing.py`.
- `docs/expected.md`: the answers we worked out by hand before writing the code, which the tests compare against.

## How it is built

A watcher takes a SHA-256 fingerprint of each source and notices when a document is new or has changed. The agent downloads it from the local policy website and checks the fingerprint against the site's index. The document is split into numbered sections, and each section carries a jurisdiction line and an effective date line.

For every old and new pair of sections the AI says whether anything changed, whether the change is substantive or only wording, what the old and new rules are and when they start, and it quotes the text it used. The code then checks that answer in three ways: the quotes must appear word for word in the source, the numbers are recomputed by the code itself and compared, and the change type, jurisdiction and category must be consistent with each other. Anything that fails goes to a reviewer.

Matching employees and calculating money is plain Python with exact decimal arithmetic. The AI never does either. Finally the code decides whether a finding is "Ready to approve" (eight conditions must all pass) or needs a reviewer, and says why. Decisions are saved in SQLite and are never edited afterwards.

We use two small Groq models. gpt-oss-120b reads and compares sections. gpt-oss-20b chooses the agent's next step from a list of ten tools, and none of those tools can approve a finding. The agent stops after 25 steps and refuses repeated or out-of-order calls. The small model sometimes fails to pick a tool, so after two tries the code picks the step instead and the log says so.

## Assumptions

- A standard week is 40 hours, hours above that are paid at 1.5 times, and a year is 52 weeks.
- As an example, E001 earns $17.06 and works 42 hours, so the rise to $17.25 costs 0.19 x 40 + 0.19 x 1.5 x 2 = $8.17 a week. The $273.19 a week in effect adds up to $14,205.88 a year.
- Employer FICA is taken as 7.65 percent of the increase, which is $20.90 a week or $1,086.75 a year on that total.
- An employee belongs to the jurisdiction where they work, not where they live.
- Four plain rules match employees to changes. R1 covers minimum wage: hourly staff below the new minimum are affected, and salaried exempt staff and contractors are left out. R2 (tax rate), R3 (filing deadline) and R4 (reporting) apply to every non-contractor in the jurisdiction, except that a new-hire rule applies to future hires only.
- Each policy section has a Jurisdiction line and an Effective Date line. If a date is missing or unclear we flag it for a reviewer instead of guessing.
- The data is synthetic. The place names are real, but the wage rates, rules and dates are made up. The real proposed bills are shown for information only and are never added to the totals.

## Limitations

- A quote that matches the source proves the AI did not invent text. It does not prove the AI understood a real policy. A plausible misreading could get through, which is why a person always decides.
- Hybrid employees work in two places and we have no record of how their hours split. They are flagged as needing review, shown with an upper bound, and kept out of the totals.
- Unemployment insurance rate changes are matched but not priced, and back pay is not calculated.
- Scanned PDFs are not supported, and overtime is worked out weekly on standard hours rather than from timecards.
- It is a single-user local app. The reviewer types a name and there is no sign-in.
- On the free AI tier a full read from scratch takes a few minutes, and only a handful of full runs fit in a day.
- We did not build the repeat-run check (V5) or the optional read-only connector for Claude Desktop.

## Who did what

We split the work by layer.

Pavan built the reading side: loading and splitting the documents, the Groq client, the prompts and answer formats, the pipeline that produces findings, the agent with its live view, the policy website and reset script, and the Agent activity, Sources and Proposed law pages.

Anu built the checking and decision side: the data models, the employee loader and the synthetic employee CSV, the checks on AI answers, the matching rules, the cost calculation, the approval rule and the review history, the two CSV exports, and the Review queue, Employee impact and Review history pages.

We wrote the requirements, the expected answers and the tests together, and we reviewed each other's work. We also used Claude Code as a coding assistant. The design, the rules and the checks were our decisions, and every figure was checked against the answers we had worked out by hand. The commit history shows who changed what.
