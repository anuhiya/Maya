# Maya: plan

Oct 29, 2026 (second revision). Pavan and Anu.

Maya is an AI agent that watches payroll policy sources, finds what changed, works out who is affected and
what it costs, approves clear changes by rule, and sends anything unclear to a reviewer, showing every step
live. Jon's written brief is the core and is built first; Aditya's additions (agent, automatic intake, live
view) sit on top, so the brief's features still work if the agent fails.

Demo: Monday Nov 2, 2026, 4:00 PM ET. Rollcall.ai use cases (shared by Aditya) are the reference for the
live-agent pattern and the "show me" finding layout.

## Requirements checklist

Every item must be visible in the app or the repo on Monday. Nothing outside `docs/requirements.md` gets
built until every row works.

| # | Requirement | How Maya meets it | Owner |
| --- | --- | --- | --- |
| B1 | TXT or PDF in; find wage, tax, filing and reporting changes; substantive vs wording | Old and new file upload on the Agent page plus agent intake; the AI extracts facts and compares; code verifies every answer; TXT and PDF give identical results | Pavan |
| B2 | Jurisdiction, category, previous and updated rule, effective date, excerpts; flag missing or ambiguous | Finding detail view with file and section cited, quoted date line, flags in plain English | Both |
| B3 | Synthetic CSV, 50+ employees, 3 jurisdictions, five columns; explicit matching rules | 80 employees written by the team (onsite, hybrid, remote); rules R1 to R4 shown on screen; every employee gets a result and a reason | Anu |
| B4 | Weekly cost for minimum wage changes, math and assumptions shown | Per-employee formula written out; overtime on the increase; assumptions panel; current and future apart | Anu |
| B5 | Dashboard with filters for jurisdiction, category, review status | Review queue with the three filters plus a timing filter; summary cards; filters also apply to exports | Anu |
| B6 | Pending, approved, dismissed, with comment, saved locally with time | Append-only SQLite table; comment required to dismiss; UTC time and reviewer name; survives a restart | Anu |
| B7 | Download findings and employee impact as CSV | Two download buttons, documented columns, as-of date in the file name | Anu |
| B8 | Five validation cases | Main pair covers four, identical pair covers "no changes", one click each | Both |
| B9 | AI optional, no paid services; explain role and checks | Groq free tier; layered verification V1 to V6; README section on AI role and checks | Both |
| B10 | Repo, local app, sample files, tests for matching and cost, README | See Tests, Repo and README sections | Both |
| A1 | Real payroll practice, visible improvements | Effective-dated rules, work-location jurisdiction, overtime, audit trail; improvements: evidence, per-employee impact, the company's own policy | Both |
| A2 | Agent finds and takes in policies itself | Watches sources, detects changed documents, fetches and processes them; searches the Federal Register live, read-only | Pavan |
| A3 | Automate clear changes, person for unclear | Auto-approval rule with strict conditions; everything else to the queue with a reason; approval-mode switch | Anu |
| A4 | Show the background work live | Agent activity page with a PLAN / TOOL / AI / CHECK / RESULT log that grows step by step | Pavan |
| P8 | Data-driven | One config file points to policies, employees, sources and as-of date | Both |
| X1 | Extra: total cost panel | Built last | Anu |

## Architecture

The AI agent plans the run, reads the policies and judges each change. Code verifies every AI answer
against the source and calculates every dollar. The router decides what a person must see. Each box is one
module, so the two halves can be built and tested apart.

Policies come in from the sources, the AI reads and compares them into findings (each answer verified by
code), impact adds employees and cost, and the router either auto-approves by rule or hands the finding to
the reviewer. Every step and decision is stored in SQLite and shown in the app.

## The AI agent (A2, A4, B9)

A language model plans each run, reads the policies and judges every change. Code does three things the AI
is not trusted with: verifying every AI answer, calculating money, and saving the record. This matches
Rollcall's rule: "Rules calculate the dollars. AI identifies, explains and groups. A reviewer decides."

| Job | Done by |
| --- | --- |
| Decide which source to check and which tool to call next | AI (planner, openai/gpt-oss-20b) |
| Read each section: jurisdiction, effective date, value, unit, category, quoted sentence | AI (reader, openai/gpt-oss-120b), fixed JSON format |
| Judge substantive vs wording only; spot new wording or scope changes | AI (reader) |
| Write the headline, recommended action, owner, routing reason, run summary | AI |
| Verify every AI value and quote, recompute numbers and dates, parse dates | Code |
| Match employees, calculate weekly cost, overtime and totals | Code (exact decimal math) |
| Route findings, record decisions, save runs, prompts and replies | Code (SQLite) |

**Agent tools** (code runs each one; the model only chooses): `watch_sources`, `fetch_document`,
`split_sections`, `read_sections` (AI), `check_answers`, `match_employees`, `price_changes`,
`route_findings`, `search_federal_register`, `finish` (AI). Each call carries a required `plan` argument
that becomes the PLAN line in the log. There is no approve tool: the agent can never approve a finding;
only the routing rule or a person can. Code refuses unsafe or invalid steps and logs the refusal as a
failed CHECK. The run stops after 25 steps.

**Run steps:** the model gets the goal ("find what changed since the approved version, who it affects,
what it costs, who must decide") and the tool list, calls one tool at a time, reads each result, and ends
with `finish`. A failed check gets one retry with the reason; a second failure sends the finding to the
reviewer with "AI answer failed its check."

**Sources it watches:**
- a fictional "Department of Labor" policy site for the three fictional jurisdictions in the config (trusted; the demo source,
  because the brief says fictional policies);
- the company policy folder (trusted);
- manual upload of an old and a new file on the Agent activity page (trusted, because the reviewer chose
  it); it moves to the Sources page if that stretch page is built;
- the Federal Register API, free and keyless (informational only): the log shows Maya searching it once per
  run for new minimum wage and payroll rules; anything found goes to the reviewer as informational and
  never reaches employees or cost, because the brief's policies are fictional.
- The US Department of Labor state minimum wage page is optional and off.

**The live activity log.** Each line is tagged so Jon can tell the AI from the code: **PLAN** (what the
agent will do), **TOOL** (a tool call), **AI** (what the model answered), **CHECK** (pass or fail),
**RESULT** (what came out). The page shows a status badge, the goal, tool chips and the guardrails line,
and runs in Automatic mode (Step by step, one step per click, is stretch). "Start over" resets the demo; `scripts/reset_demo.py --yes` does
the same from a terminal. "Publish next version" (publish the held-back policy version) is the live-change demo action.

**Guardrails line, shown on screen:** AI reads and judges. Code checks every AI answer and calculates
every dollar. A person decides anything unclear.

**Reliability:** temperature 0; reasoning effort low for the reader; a fixed JSON schema for every AI
answer (anything that does not fit is rejected); every prompt and reply saved with the run; optional repeat
run (V5).

**Model and cost (B9, no paid services):** Groq free tier only, no other provider. One OpenAI-style client.
Keys live in an environment variable or `.streamlit/secrets.toml`, never in the repo. Only synthetic data
is ever sent to a model.

**Demo safety:** save the replies from a successful run to `data/replays/`. If Groq is down or limited
during the demo, the agent replays that run, labelled "replayed from saved run" in every log line.

## Routing: what is automated and what a person decides (A3, B6)

Clear changes are approved by a written rule; anything else waits for a person, with the reason shown.
Every decision, automatic or human, goes into the same review history.

**Auto-approval rule (internal name "rule A1", never shown in the UI).** A finding is approved
automatically only when all of these are true:

1. Category is wages or tax rate.
2. Exactly one old value and one new value, both extracted by the AI and confirmed by the checks.
3. Both values appear word for word in the source excerpts (V1) and match the code's recomputation (V2).
4. The effective date is present and in an accepted format.
5. The jurisdiction is known.
6. The source is marked trusted in the config (the fictional site, the company folder, a manual upload;
   real government sources are informational only).
7. Every AI answer passed its checks (and, if repeat run is on, both runs agree).
8. Nothing else in the section changed (no new wording, no scope change).

The history records it as status *approved*, shown as "Auto-approved", with the passed conditions as the
comment. A person can reverse it at any time, which adds a new history row.

**Sent to the reviewer, with the reason shown:**

| Reason shown | Example |
| --- | --- |
| No effective date found | Calder annual earnings report, section 2.3 |
| Effective date is unclear ("To be determined", 03/04/2027) | Meridian new hire reporting, section 3.3 |
| New or changed wording that no value check covers | Avalon pay statements must now show hours at each rate, section 1.3 |
| Two different amounts in one section | "$16.50 and $17.00" (not in our data; covered by a unit test) |
| Section added or removed | Avalon wage notice at hire, section 1.4 |
| Filing deadline or reporting change | Calder quarterly wage report, section 2.2 (always reviewed: the employer must change a process) |
| Source not trusted, an AI answer failed its check, or two runs disagree | Any |

**Approval mode:**
- **Pre-approve, one-click sign-off (core, default and recommended):** findings that pass the rule are
  labelled "Ready to approve" and a person signs them off together with one click. Their status stays
  pending until then. The brief allows only pending, approved and dismissed, so "Ready to approve" is a
  label, never a fourth status. The checks show an answer agrees with the source but cannot prove the
  interpretation is right, so every rule-passing change still gets a person's signature.
- **Auto-approve (stretch, off by default):** findings that pass the rule are approved straight away,
  shown as "Auto-approved". Offered so Jon can judge it; not used in the demo.

## Reading and comparing (B1, B2, V1 to V3)

The AI does the reading and judging; the definitions below go into its instructions word for word, and the
check layer enforces them.

**1. Read and split (code, Pavan).** TXT is read directly; PDF text comes from pdfplumber. Clean curly
quotes, extra spaces and words split across lines, so a TXT and a PDF of the same policy read the same.
Split into numbered sections. A PDF with no text (scanned) or a file with no sections is an error, never
"no changes."

**2. Extract each section (AI, JSON answer):** section, title, jurisdiction, effective date exactly as
written (or "missing"), value, unit (dollars per hour, percent, days), calendar or business days,
obligation (shall, must, may), category, the rule sentence quoted, and the date line quoted.

**Category definitions given to the AI:** wages = a required hourly pay amount in dollars, such as a
minimum wage; tax rate = a percentage withheld or contributed; filing deadline = when a report or return must
be filed; reporting = what must be reported, or given or shown to employees (pay statements, notices). If
none fits, answer "unclear".

**3. Compare old and new (AI, JSON answer):** change type (substantive, wording only, added, removed),
which facts changed, and a one-line reason. Definitions given to the AI:
- Substantive: any value, date, unit, jurisdiction, category, scope or obligation changes, or new required
  content appears. "$15" and "$15.00" are the same value. "shall" and "must" mean the same; "may" does not.
- Wording only: the sentence changed but every fact above is the same.
- Added or removed: the section exists in only one version.

**4. Verify every answer (code, Anu), layered (requirements V1 to V6):**
- V1: every quoted sentence and value appears word for word in the source section.
- V2: code extracts every dollar amount, percentage and day count from both versions of the section and
  compares; any disagreement with the AI's claim goes to the reviewer.
- V3: "wording only" is rejected if the extracted facts differ; jurisdiction must match the section's text;
  category must be one of the five labels.
- Effective dates must be in one of three formats: YYYY-MM-DD (2027-01-01), full month name (January 1,
  2027) or short month name (Jan 1, 2027); any year. "To be determined", "TBD" or "pending" gives flag
  *unclear date*; 03/04/2027 gives *unreadable date format*; no date line gives *missing date*.
- Two different amounts in one section give flag *conflicting values*.
- A flag *new wording* applies only when both versions of the section exist.

**5. Timing (code)** against the as-of date: no usable date = unknown; on or before = current; after =
future.

**Each finding stores:** finding ID (stable hash of policy, section and category), section, jurisdiction,
category, change type, old rule, new rule, old value, new value, unit, effective date, timing, old excerpt,
new excerpt, source file, flags, AI reason, check results, recommended action, owner.

## Employees, matching and cost (B3, B4)

The team's own synthetic employee CSV has 80 employees across three jurisdictions (the brief asks for at
least 50). It is a plain file, committed (`data/employees.csv`), and every employee gets a result and a one-line reason for every finding in their
jurisdiction.

**CSV columns:** the brief's five come first: `employee_id`, `jurisdiction` (work location), `hourly_wage`,
`weekly_hours`, `employment_type` (hourly_full_time, hourly_part_time, salaried_exempt, contractor). Extra
payroll columns are allowed after them (name, job title, department, hire date, pay frequency, FLSA status,
overtime eligibility, annual salary, work arrangement, office location, secondary jurisdiction, residence
jurisdiction); matching uses only the columns a rule needs, and always the work-location `jurisdiction`. For
salaried staff, hourly_wage = annual salary / 2080, for information only.

**Work location (real payroll practice, A1):** the law of the place where the work is performed applies.
`work_arrangement` is onsite, hybrid or remote. Onsite: the office is the work location. Remote: the home is
the work location, so `jurisdiction` is the home and `office_location` may differ. Hybrid: `jurisdiction` is
the primary work location and `secondary_jurisdiction` the other one (blank if both are the same). If an
hourly hybrid employee's wage is below the new minimum of their `secondary_jurisdiction`, Maya does not guess
the split of hours: the employee is listed under that change as "Needs review: works part of the week in
<jurisdiction>" with an indicative upper bound (all hours at that minimum), never added to the totals.

**Data rules (for the file the team writes):**
- Hand-written edge cases first, each with its expected result recorded in `docs/expected.md`: below a new
  minimum, exactly at it, above it, with overtime, part-time, salaried exempt, a contractor below the
  minimum (excluded with a classification warning), and one reached only by a future change.
- Choose the other rows so the live-demo change reaches exactly the employees you expect, and so the
  totals can be checked by hand.
- Validate on load: required columns, unique IDs, known jurisdictions and types, positive wage and hours.
  If the work-location columns are present: arrangement is onsite, hybrid or remote; onsite means office
  equals jurisdiction and no secondary; remote means residence equals jurisdiction; a secondary jurisdiction
  is known, differs from jurisdiction and appears only on hybrid rows. Report bad rows; never drop them
  silently.

**Matching rules (shown on screen as a table):**

| Rule | Applies to | Who is matched |
| --- | --- | --- |
| R1 | Wages | Hourly full- or part-time, same jurisdiction, wage below the new minimum = affected; at or above = not affected; salaried exempt and contractors = excluded |
| R2 | Tax rate | Every non-contractor employee in the jurisdiction; no dollar estimate |
| R3 | Filing deadline | Employer obligation; every non-contractor employee in the jurisdiction is in the filing; no pay change |
| R4 | Reporting | New-hire rules = future hires only (no current employees); other reporting rules (pay statements, earnings reports) = every non-contractor employee in the jurisdiction |
| none | Wording only | Nobody: no operational impact |

**Cost formula (wages only):**
- Gap = new minimum minus current wage
- Weekly increase = gap x min(hours, 40) + gap x 1.5 x max(hours - 40, 0)
- Written out per employee, for example "0.50 x 40 h + 0.50 x 1.5 x 5 h = $23.75"
- Exact decimal math, rounded half up to the cent
- Current and future totals kept apart; yearly figure labelled "annualized (52 weeks)"

**Assumptions, shown next to every total:**
- Weekly hours are a standard week, not timecard hours.
- Overtime is 1.5 times over 40 hours a week; daily overtime is not modelled.
- The base wage is treated as the regular rate (no bonuses or shift pay).
- Jurisdiction is where the employee works (for remote staff, their home); the hours split of hybrid staff
  is not recorded.
- Only the gap to the new minimum is costed; raises for people just above it are not.
- Salaried exempt staff and contractors are excluded.

## Extra X1: total cost panel and per-employee totals

Built only after everything else works. It sits below the brief's required minimum wage figure (B4), which
stays the headline. Anything Maya cannot calculate from the documents is flagged, not guessed.

| Line | How it is calculated | Status |
| --- | --- | --- |
| Wage increases in effect | Sum of minimum wage increases now in effect (B4) | Calculated |
| Employer Social Security and Medicare | Increase x 7.65% | Estimate; assumes everyone is under the wage base |
| **Total in effect** | Sum of the two lines above, plus the annualized figure (52 weeks) | Calculated |
| Wage increases coming | Same method, grouped by effective date | Shown apart, not added to in-effect |
| Unemployment tax change | (new rate - old rate) x taxable wages up to the wage base | Flagged when the policy does not state the wage base |
| Back pay | Weekly increase x days between effective date and the date pay was updated / 7 | Needs reviewer input |
| Filing and reporting changes | Process changes, no pay impact | Listed, $0.00 |

Per-employee rows (employee ID, changes that reach them, increase now, increase coming with date, employer
tax, total, flags) add up to the panel. These columns are also added to the employee impact CSV; the five
required columns stay as they are. The expected numbers come from `docs/expected.md`.

## Screens (B5, B6, B7, A4)

One Streamlit app with a sidebar and five core pages: Agent activity, Review queue (finding detail beside
the list), Employee impact, Review history and Export. The sixth, Sources, is stretch. The Maya design canvas is the visual
reference (`docs/design.md`); this list is what must actually work.

**Sidebar (every page):** wordmark, page links, footer line. As-of date, reviewer name, approval mode and
the filters (jurisdiction, category, review status, timing) live on the Review queue; the Impact and Export
pages show the active filters as chips. Filters drive the queue, the impact page and both exports.

| Page | Owner | What it shows | Requirement |
| --- | --- | --- | --- |
| Agent activity | Pavan | Run button, status badge, goal, tool chips, guardrails line, the live log, Publish next version, Start over, manual upload of old and new TXT or PDF (Step by step mode is stretch) | A2, A4, B1 |
| Sources (stretch) | Pavan | Watched sources with trust and last check; manual upload moves here | A2, B1 |
| Review queue | Anu | Summary cards; findings grouped Needs review / Current / Future; finding detail beside the list with headline, old vs new rule with the changed value highlighted, dates, excerpts with file and section, flags with reasons, affected employees, cost with written math, recommended action, owner, decision form, this finding's history | B2, B4, B5, B6 |
| Employee impact | Anu | All employees for the selected findings with result, reason, rule ID, calculation, weekly increase; per-jurisdiction totals; assumptions panel | B3, B4 |
| Review history | Anu | Every decision newest first: time (UTC), finding, status, comment, reviewer (person or "Auto-approved") | B6 |
| Export | Anu | Two downloads, filtered, as-of date in the file name | B7 |

**Required empty and error states:**
- No changes: "No changes detected: N of N sections identical. 0 findings, $0.00." Exports still download,
  with headers only.
- Unreadable file: a red error naming the file and the reason. Never shown as "no changes."
- Agent finds nothing new: "All sources unchanged since the last run," with the time checked.
- No model reachable and no replay: name the missing setting.

**Export columns:**
- Findings: finding ID, section, jurisdiction, category, change type, old rule, new rule, old value, new
  value, effective date, timing, flags, old excerpt, new excerpt, source file, review status, last comment,
  decided at, decided by.
- Employee impact: finding ID, employee ID, jurisdiction, employment type, hourly wage, weekly hours, rule
  ID, result, reason, new minimum, weekly increase, calculation, timing.

**Persistence (B6):** SQLite file in the app folder with three tables: `reviews` (append-only decisions,
enforced by triggers), `agent_runs` (one row per run with its log), `document_versions` (fingerprint and
text of every version seen). Restarting the app keeps everything; show this in the demo.

## Data and validation (B8)

The team writes its own synthetic data: a main policy pair that covers four of the five required cases, an
identical pair for the fifth, and a later version that drives the live agent demo. Every section has a
number and title, a Jurisdiction line, an Effective Date line and one rule sentence. Files are already in the repo:
`data/policies/` (bulletins PSB-2026-01 and -02, TXT and PDF), `data/company_policies/` (pay policy HR-PAY-04,
two identical copies and a PDF), `data/policy_site/` (the fictional site, with PSB-2026-03 held back in
`_unpublished/`). `scripts/make_policies.py` rebuilds every TXT and PDF if a value changes. Paths and names
are set in `maya.config.yaml`.

`docs/expected.md` is filled in and frozen (requirements V4): for each section, the expected change type and
timing, affected employees with the written math, and the route. Its numbers were worked out independently
of the app's code and confirmed twice from the CSV.

**The five required cases, one click each:**

| Required case | Must be shown by | Expected on screen |
| --- | --- | --- |
| Minimum wage increase affecting only some employees | a wage section in the main pair | some employees affected, some not, some excluded, with reasons |
| Future change shown separately | a section with a later effective date | in the Future group, not in the current total; moving the as-of date past it moves it to Current |
| Missing effective date | a section with no date line | in Needs review with "No effective date found in section X" |
| Wording change, no impact | a reworded section with identical facts | wording only; no employees; no cost |
| No changes | an identical pair | "No changes detected: N of N sections identical" |

Also include at least one unclear date ("To be determined"), one added section and one section whose new
wording adds a requirement, so the routing reasons all appear.

**Live agent demo:** during the demo, publish a held-back newer version on the fictional site that changes
one minimum wage with a future effective date. The agent detects it, the affected employee shows a future
weekly cost, the finding passes the auto-approval rule and waits for one-click sign-off.

## Tests (B10)

The brief requires meaningful tests of matching and cost. The rest protect the demo. All run offline with
one command and automatically on GitHub. Keep the suite lean: required tests first, extras only where they
guard a known failure.

**Matching and cost (required, Anu), one test per row of the edge-case table in `docs/expected.md`:**
- [ ] Each edge-case employee gets exactly the expected result, reason and weekly cost (overtime included)
- [ ] A finding for one jurisdiction never matches employees of another
- [ ] Per-jurisdiction totals equal the sum of their rows; current and future totals stay apart
- [ ] Rounding: $10.125 becomes $10.13
- [ ] A tax-rate finding matches every non-contractor employee in the jurisdiction, with no dollar amount
- [ ] Salaried exempt and contractors are excluded; a contractor below the minimum carries the warning

**Verification and reading (Anu: checks; Pavan: ingest and split):**
- [ ] A quote not in the source fails V1; an AI number that disagrees with the code's recomputation fails V2
- [ ] "wording only" with different facts is rejected (V3)
- [ ] Missing date, "To be determined" and "03/04/2027" each give their own flag
- [ ] "$15" vs "$15.00" = no change; "may" to "must" = substantive; "30 days" to "30 business days" = substantive
- [ ] Main pair gives exactly the findings in `docs/expected.md` (on saved AI replies)
- [ ] No-change pair = zero findings; a file with no sections = an error
- [ ] TXT and PDF of the same policy give identical findings

**Agent and routing:**
- [ ] The auto-approval rule passes and refuses exactly the sections marked in `docs/expected.md` (Anu)
- [ ] Scripted planner run finds the expected findings from replay; the later version gives only its one change; a refused step logs a failed CHECK; Federal Register results never reach employees or cost (Pavan)
- [ ] With Groq unreachable, the agent replays the saved run and logs "replayed from saved run" (Pavan)
- [ ] One live smoke test on the main pair, by hand, not in CI (Pavan)

**Review history (Anu):**
- [ ] Two decisions on one finding keep both rows; the latest is the current status
- [ ] Dismissing without a comment is refused
- [ ] Decisions survive closing and reopening the database

**Total cost panel (X1, Anu):** employer tax, in-effect total and annualized figure match `docs/expected.md`;
per-employee rows add up; a future increase stays out of the in-effect total until its date; a line that
cannot be calculated is flagged, never given a number.

## Work split (50/50, P5)

Pavan owns documents, the AI layer and the agent. Anu owns the checks on AI answers, employees, matching,
cost, routing and storage. The pages are split by page. Most typing is done by tools, so most time goes to
reviewing, testing and understanding. Each person must be able to explain the other's half.

| Scope | Work item | Owner | Hours |
| --- | --- | --- | --- |
| Core | Repo setup with docs and data | Anu (Pavan reviews) | 0.5 |
| Core | Data contract `maya/models.py`: Anu writes it, Pavan reviews | Both | 1 Anu, 0.5 Pavan |
| Core | AI answer formats `maya/ai/schemas.py`: Pavan writes them, Anu builds her checks on them | Pavan | 0.5 |
| Core | Fictional site index, publish next version, reset (`maya/site.py`, `scripts/reset_demo.py`) | Pavan | 0.5 |
| Core | Reading TXT and PDF, splitting into sections (`ingest`, `split`), with tests | Pavan | 1 |
| Core | Groq client, prompts, findings pipeline, saved-run replay, with tests | Pavan | 3 |
| Core | Agent loop, tools, Automatic mode, live log, sources, Federal Register search, with tests | Pavan | 3 |
| Core | Agent activity page, including manual upload | Pavan | 1 |
| Core | README: architecture, how the agent works, use of AI | Pavan | 0.5 |
| Core | Checks on AI answers V1 to V3 (`checks`), flags, timing | Anu | 2 |
| Core | Employee loader and validation (`employees`) | Anu | 0.5 |
| Core | Matching R1 to R4 (remote staff included) and cost with overtime, with the required tests | Anu | 2 |
| Core | Routing with Pre-approve sign-off, append-only history (`db`), both CSV exports | Anu | 2 |
| Core | Review queue with detail and filters, Employee impact, Review history, Export pages | Anu | 2 |
| Core | README: assumptions, limitations, setup | Anu | 0.5 |
| Stretch | Sources page, Step by step mode, repeat run (V5), config clean-up (P8 audit) | Pavan | 3 |
| Stretch | Hybrid "Needs review" flag, Auto-approve option, X1, extra routing and history tests | Anu | 3 |

**Core and stretch (time budget about 10 hours each, as the brief and Aditya ask):** core is about 10 hours
for Pavan and 10.5 for Anu; stretch is about 3 each and starts only after the core reproduces every number
in `docs/expected.md`. If the hybrid flag is not built, remove the E076 and E078 review lines from
`docs/expected.md` by agreement; totals do not change. Pre-approve is the default and recommended setting.

**Agree first, together (Thursday night):**
1. Anu creates the repo layout and commits the kit's `docs/` as the first commit; Pavan is a collaborator
   and `main` requires a reviewed pull request.
2. Anu writes `maya/models.py` in the first pull request; Pavan reviews it.
3. Pavan writes `maya/ai/schemas.py`; Anu reads it before building `checks`.
4. Both use the same labels everywhere (`docs/project-rules.md`).
5. Never change an expected answer in `docs/expected.md` without telling the other person.

**Honest history rules:** each person commits their own modules on their own branch and the other person
reviews and approves. Nobody commits the whole app in one commit. Paired work gets `Co-authored-by:`.
Commits are never reassigned afterward. The README's contributions section matches the history.

**What each person can explain to Jon:**
- Pavan: why the AI reads and judges, how its answers are verified, how the agent chooses steps and
  refuses unsafe ones, what happens when the model is down.
- Anu: how each employee is matched by explicit rules, how every dollar is calculated and why the AI never
  does it, how a finding is routed, why review history cannot be edited, what the checks do and do not prove.

## Timeline

The brief's core works by Friday night; the agent and pages come Saturday; Sunday is for checking and
sharing the repo. If time runs out, cut from the bottom of the priority list, never the top.

| Day | Pavan | Anu | Together |
| --- | --- | --- | --- |
| Thu Oct 29 | Two-factor sign-in, Groq key; site plumbing; review the contract | Repo setup with docs and data; data contract | Agree labels and file owners |
| Fri Oct 30 | AI answer formats; reading TXT and PDF; AI layer and one saved run | Employee loader; matching and cost; checks, flags and timing | Evening: every module merged by a reviewed pull request (tag v0.1.0) |
| Sat Oct 31 | Agent and sources, saved runs on PSB-2026-02 and -03; Agent activity page | Storage and routing; Review queue, Employee impact, History and Export pages | Wire together, every number matches `docs/expected.md` (tag v0.4.0); rehearsal with Aditya playing Jon |
| Sun Nov 1 | Stretch if the core is done; README sections | Stretch if the core is done; README sections | Fresh-clone test, fixes, contributions from the real history, tag v1.0.0, send Jon the link |
| Mon Nov 2 |  |  | Morning: two rehearsals, replay on and off. 4:00 PM ET: present |

**Priority if time runs short:** see `docs/requirements.md`. Anything unfinished goes in the README with
the reason, as the brief asks.

## Repo, versions and team documentation (B10, P4)

Run the repo the way a company team would: protected main branch, pull requests, tagged versions and short
written records. Jon opens the repo before the meeting.

- Nobody pushes to `main`; each change is a branch and a pull request reviewed by the other person.
- Tests run automatically on every pull request; show the passing badge in the README.
- Versions: v0.1.0 contract, schemas, data and employee loader (Fri), v0.4.0 core wired (Sat), v0.7.0 pages and
  README, v1.0.0 after the fresh-clone test (Sun).
  Each tag gets a few lines in `CHANGELOG.md`.
- Decision records in `docs/decisions/`, one short page each (context, decision, alternatives,
  consequences): AI reads and code checks; layered verification; strict date formats; append-only review
  history; exact decimal money; stable finding IDs; auto-approval rule and approval mode; fictional policy
  site, Groq free tier and replay of a saved run; config-driven data; work location decides the jurisdiction.

## README, AI disclosure and limitations (B9, B10)

The README is short and written in your own words: concrete numbers, no buzzwords, no emojis.

**README sections:** 1. What Maya does, in three sentences. 2. Setup and run (one install command, one run
command, one test command, how to get a free Groq key; without a key, the sample pair still runs from the
saved run and the app says which setting is missing). 3. Architecture and one line per module. 4. How the
agent works. 5. Routing. 6. Assumptions. 7. Validation cases and how to reproduce each. 8. Limitations.
9. Use of AI. 10. Individual contributions, matching the commit history. 11. Unfinished work and why.
12. Next steps.

**Use of AI (B9):**
- In the app: Groq free tier; what the AI does (plans the run, reads each section, judges each change,
  writes explanations); what it never does (calculate money, match employees, approve anything unclear);
  the verification layers V1 to V6; replay if Groq is down; only synthetic data is sent to the model.
- In development: describe accurately how the code and documents were produced, who wrote and reviewed what,
  and what the tests cover. Whatever is written must be true, and each person must be able to explain every
  module.

**Limitations to state (one-line answers ready):**
- Built for numbered policy sections; long real regulations need a more flexible reader.
- Scanned PDFs are not supported.
- One level of jurisdiction: no city or county minimum wages, tipped wages or youth wages.
- Hybrid staff: the split of hours between two jurisdictions is not recorded, so a possible shortfall is sent to the reviewer instead of being priced.
- Weekly overtime only; base wage treated as the regular rate; standard hours, not timecards.
- A change that starts mid-week means that workweek is paid at two rates; Maya treats it as a full week.
- A change that took effect before the review date may mean back pay is owed; it is not calculated.
- Raises for people just above the new minimum are not costed.
- Salaried non-exempt staff and state exempt-salary thresholds are not modelled.
- Unemployment tax changes are matched but not priced; the wage base is not modelled.
- Verification limit: exact quotes show the AI did not invent text, not that it read the policy correctly.
  Recomputation, consistency checks, expected answers and a reviewer reduce that risk, but a plausible
  misreading of a real policy could still pass.
- Single local user; reviewer name is typed, no sign-in.

**Next steps:** back pay for late-applied changes, city and county rates, address-based jurisdiction lookup,
two-person approval, more real government sources, an accuracy scorecard on a larger set of policies.

## Ten-minute demo flow

Present from the live app, both speaking, with at most one slide at the end. Rehearse twice with a timer.

| Minutes | Who | What to show |
| --- | --- | --- |
| 0 to 1 | Pavan | The problem in one sentence; what Maya does; the guardrails line |
| 1 to 3 | Pavan | Run the agent on PSB-2026-02: the log fills with PLAN, TOOL, AI, CHECK and RESULT lines; 9 findings |
| 3 to 5 | Anu | Section 1.1 Avalon: excerpts, who is affected and why, the written math, $273.19 a week; open E001's overtime; show E071 (remote) |
| 5 to 6 | Anu | Section 2.1 Calder in Future ($142.80), then switch the as-of date to 2027-01-01 and watch it move to Current |
| 6 to 7 | Anu | Section 2.3 held for review (no date) and 3.2 as wording only; then the company policy no-change pair (6 of 6) |
| 7 to 8 | Anu | Approve and dismiss with comments; restart the app; history is still there; download both CSVs |
| 8 to 9 | Pavan | Live change: publish PSB-2026-03; the agent finds only the Meridian raise, 6 employees, $98.65 a week coming; one-click sign-off |
| 9 to 10 | Both | Limitations, next steps, and one line: Rollcall stops bad payments in this run; Maya stops them in future runs as soon as a policy changes |

**Backup:** if Groq fails or hits its limit live, the agent replays the saved run (labelled as a replay);
the manual upload of the sample pair still works.

**Sources:**
- Jon's assignment email (brief reproduced in `docs/requirements.md`)
- Aditya's call notes: agent, automatic intake, human in the loop, live background view
- Rollcall.ai use cases: https://rollcall-use-cases.vercel.app/
