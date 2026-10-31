# Maya

## Assumptions

- A standard week is 40 hours. Hours above 40 are paid at 1.5 times the hourly wage. Example: E001 earns $17.06 and works 42 hours, so the rise to $17.25 costs $8.17 a week.
- A year is 52 weeks. The $273.19 a week in effect becomes $14,205.88 annualized.
- Employer FICA is 7.65% of the increase: $20.90 a week, or $1,086.75 a year, on that same total.
- An employee belongs to the jurisdiction of their work location, not their home. E002 lives in Calder but works onsite in Avalon, so Avalon's minimum wage applies.
- Employees are matched to a change by four explicit rules in plain code. The AI never matches employees or calculates money.
  - R1, wages: an hourly full- or part-time employee in the same jurisdiction is affected if the wage is below the new minimum, and not affected at or above it. Salaried exempt staff and contractors are excluded.
  - R2, tax rate: every non-contractor employee in the jurisdiction is matched. No dollar figure is calculated.
  - R3, filing deadline: an employer obligation. Every non-contractor employee in the jurisdiction is in the filing. No pay change.
  - R4, reporting: a new-hire rule covers future hires only, so no current employee is matched. Other reporting rules (pay statements, earnings reports) match every non-contractor employee in the jurisdiction.
- Policy files follow one layout: each numbered section has a `Jurisdiction:` line and an `Effective Date:` line. A missing or unclear date is flagged for a reviewer, never guessed.

## Limitations

- Verification limit: exact quotes show the AI did not invent text, not that it read a real policy correctly. Recomputation, consistency checks, the expected answers and a reviewer reduce that risk, but a plausible misreading of a real policy could still pass.
- Hybrid employees work in two jurisdictions and their split of hours is not recorded. They are flagged "Needs review" with an upper bound (E076 $58.00, E078 $7.20 a week) and are never added to totals.
- Unemployment insurance rate changes are matched but not priced, because no wage base is modelled. Back pay for a change that took effect before the review date is not calculated.
- Scanned PDFs are not supported.
- Overtime is weekly only, on standard hours, not timecards.
- Single local user. The reviewer name is typed, with no sign-in.
- Auto-approve is optional. Pre-approve is the default: a finding that passes the auto-approval rule stays pending with a "Ready to approve" label until a person signs it off.
- Not built: the repeat run check (V5), the Sources page and Step by step mode.

## Setup and run

Needs Python 3.11 or newer.

```
git clone https://github.com/anuhiya/Maya.git
cd Maya
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Groq key: create a free key at console.groq.com and put it in `.streamlit/secrets.toml`:

```
GROQ_API_KEY = "your key here"
```

That file is gitignored. Never commit it or print the key. Without a key, the sample pair still runs from the saved run in `data/replays/`, and the app says which setting is missing.

Run the tests (live Groq calls are skipped; run them by hand with `pytest -q -m live`):

```
pytest -q
```

Run the app:

```
streamlit run app.py
```

Put the demo back to its start (clears the database, fingerprints, unpublished site changes and uploads):

```
python scripts/reset_demo.py --yes
```

Check against `docs/expected.md`: for the main pair, as of 2026-11-02, Maya should show 9 findings, 3 auto-approval candidates, $273.19 a week in effect and $142.80 a week coming.
