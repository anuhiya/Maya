# Maya: requirements (source of truth)

Revised Oct 29, 2026 (second revision, official repo). Every feature, design choice and line of code must
trace to an ID below. If anything in `docs/plan.md` disagrees with this file, this file wins, and Jon's
brief (section B) wins over everything else.

Demo: Monday Nov 2, 2026, 4:00 PM ET. The repo link goes to Jon before the meeting.

---

## B. Jon's written brief (graded, verbatim)

**Assignment: Payroll Regulatory Change Analysis and Impact Assessment**

Build a prototype that compares two versions of a fictional payroll policy, identifies meaningful
changes, and assesses which employees may be affected using a synthetic employee dataset.

| ID | Requirement (verbatim) |
| --- | --- |
| B1 | **Document processing:** Accept old and revised policy documents in TXT or PDF format. Identify changes involving wages, tax rates, filing deadlines, or reporting requirements. Distinguish substantive changes from wording changes. |
| B2 | **Structured findings:** For each change, display the jurisdiction, category, previous rule, updated rule, effective date, and supporting excerpts. Flag missing or ambiguous information instead of making assumptions. |
| B3 | **Employee impact assessment:** Create a synthetic CSV containing at least 50 employees across three jurisdictions. Include employee ID, jurisdiction, hourly wage, weekly hours, and employment type. Match relevant policy changes to affected employees using explicit rules. |
| B4 | **Cost estimation:** For minimum wage changes, calculate the estimated increase in weekly payroll for affected hourly employees. Show the calculation and assumptions. Other change categories may be assessed without a financial estimate. |
| B5 | **Review dashboard:** Display identified changes, affected employees, and estimated payroll impact. Include filters for jurisdiction, change category, and review status. |
| B6 | **Review history:** Allow a reviewer to mark findings as pending, approved, or dismissed, with a comment. Persist these decisions locally and record when they were made. |
| B7 | **Export:** Allow users to download the findings and employee impact results as CSV files. |
| B8 | **Validation examples required:** a minimum wage increase affecting only some employees; a future policy change shown separately from currently effective rules; a missing effective date that requires review; a wording change with no operational impact; a document pair with no changes. |
| B9 | **Stack:** preferred stack allowed; Python, Streamlit, and SQLite are sufficient. AI tools are optional, no paid services required. If AI is used, explain its role and how its output is verified. |
| B10 | **Deliverables:** GitHub repository with source code and clear setup instructions; a working local application; sample policy documents and the synthetic employee CSV; meaningful tests for the matching and cost calculation logic; a short README explaining architecture, assumptions, limitations, and individual contributions. |
| B11 | **Team:** Divide responsibilities so each person owns a meaningful part and understands the whole app; aim for about 10 hours per person; if time runs short, document unfinished features and explain priorities. |
| B12 | **Presentation:** 10 minute demo with both presenting, then questions; share the repository before the meeting. |
| B13 | **Evaluation:** accuracy, traceability to the source documents, code quality, handling of uncertainty, and ability to explain technical decisions. |

## A. Aditya's additions (from calls, Oct 28 to 29; what Jon wants beyond the brief)

| ID | Requirement |
| --- | --- |
| A1 | Jon knows ADP and similar platforms deeply. Follow real payroll practice (effective-dated rules, work-location jurisdiction, overtime, audit trail) and show improvements over those platforms. |
| A2 | Jon wants an AI agent, not a manual tool: it should search the web and government or official sites for new policies, take them in and process them automatically. |
| A3 | Automate definitive changes (a clear $15.00 to $15.50); keep a person in the loop for anything unclear, flagged or needing approval. |
| A4 | Jon likes to see what is happening in the background while it happens: a live view of the agent's steps, as in Rollcall.ai (https://rollcall-use-cases.vercel.app/). Rollcall's rule: "Rules calculate the dollars. AI identifies, explains and groups. A reviewer decides." |

## P. Team requirements

| ID | Requirement |
| --- | --- |
| P1 | No em dashes anywhere: UI text, code comments, docs, commit messages, README. No emojis in the UI or README. |
| P2 | Not a generic template look. Use the chosen design: Terracotta & Paper palette, Fraunces / Instrument Sans / IBM Plex Mono, "maya." wordmark, queue-and-detail layout (see `docs/design.md`). |
| P3 | The agent genuinely uses AI (no code-only shortcuts presented as AI), on the Groq free tier only. No other model provider. |
| P4 | Work like a real team: branch per change, pull requests reviewed by the other person, tagged versions, CHANGELOG, short decision records, a worklog. |
| P5 | Split work 50/50 so each person owns a meaningful part. The commit history must honestly show who did what (pairing credited with `Co-authored-by:`, never reassigned later). The README's contributions section must be accurate. |
| P6 | Each person understands every module well enough to explain it to Jon. |
| P7 | Stand out through engineering depth: tests, CI, traceability, verified AI, clean repo. |
| P8 | Data-driven: policy files, employee CSV, watched sources and the as-of date come from one config file. No jurisdiction names or section numbers hard-coded in logic, so the team's own synthetic policies, company policies and employees drop in without code changes. All expected answers in `docs/expected.md` must pass with that data. |

## V. Verification of AI answers (added after Anu's review)

A word-for-word quote proves the AI is grounded in the document. It does not prove the AI interpreted the
policy correctly. Verification therefore has layers, and the last layer is always a person:

| ID | Layer | Rule |
| --- | --- | --- |
| V1 | Grounding | Every quoted sentence and every value appears word for word in the source section. Necessary, not sufficient. |
| V2 | Independent recomputation | Code, not the AI, extracts every dollar amount, percentage and day count from both versions of a section and compares them. If the AI says a number changed and the code finds it identical, or the reverse, the finding goes to the reviewer. |
| V3 | Consistency | "wording_only" is rejected if any extracted number or date differs. Jurisdiction must match the section's own text. Category must be one of the five allowed labels. Dates must parse in an accepted format. |
| V4 | Expected answers | The expected answers (`docs/expected.md`) are fixed before the code and worked out independently of the app's code. Tests compare the app's output to them on every section. |
| V5 | Repeat run (optional) | Read the same section twice and compare. Disagreement goes to the reviewer. |
| V6 | A person decides | Anything unclear, conflicting or flagged waits for a reviewer. Auto-approved decisions record the checks they passed. |

Limit to state in the README: even all six layers cannot guarantee a correct reading of a real policy.

## X. Extra (only after every B, A, P and V item works)

| ID | Requirement |
| --- | --- |
| X1 | Total cost panel for the whole update plus per-employee totals; anything not calculable is flagged, never guessed. |

---

## How conflicts are resolved (decided, do not reopen without asking)

| Conflict | Decision |
| --- | --- |
| B says fictional policies; A2 says search real web and government sites | The agent's working source is a fictional policy site (the jurisdictions defined in `maya.config.yaml`). It also searches one real source live, the Federal Register API (free, no key), read-only: anything found goes to the reviewer as informational and is never applied to the synthetic employees or cost. |
| B6 allows only pending, approved, dismissed; A3 wants automation | Demo default is Pre-approve: findings that pass the auto-approval rule stay **pending** with a "Ready to approve" label and a person signs them off in one click. In Auto-approve mode they become **approved**, shown as "Auto-approved". No fourth status ever exists. |
| B9 "AI optional"; P3 AI-driven | AI does reading, comparing, judging and explaining on the Groq free tier. Code checks every AI answer and does all matching and money. A saved run replays if Groq is unreachable, and the app names the missing setting. Nothing paid. |
| B3 "explicit rules" | Matching (R1 to R4) and cost are plain code with tests. The AI never matches employees or calculates money. |
| B2 "instead of making assumptions" | Every AI value and quote must appear word for word in the source, numbers are recomputed by code, dates must parse; otherwise a flag goes to the reviewer. |
| B11 about 10 hours; A items add work | A core of about 10 hours each (see `docs/plan.md`, Work split) covers every B item and the core of A and V; stretch items (about 3 hours each) start only after the core matches `docs/expected.md`. If time runs short, cut from the bottom of the priority list and write it in the README. |

## Priority order (cut from the bottom, never the top)

1. AI reading and comparing with checks, excerpts and flags (B1, B2, V1 to V3)
2. Matching and cost with tests (B3, B4)
3. Review history in SQLite (B6)
4. Queue with the three filters and both exports (B5, B7)
5. Agent with live activity log, fictional site, Federal Register check (A2, A4)
6. Auto-approval rule with Pre-approve sign-off (A3); the Auto-approve option is stretch
7. Stretch: hybrid needs-review flag, Sources page, Step by step mode, config clean-up (P8), repeat run (V5)
8. X1 total cost panel

## Expected answers (tests and the demo must match these exactly)

The team's own synthetic policies, company policy and employee list are in `data/`, and the expected answers
were worked out from that data before any code was written (V4). They live in `docs/expected.md`, which has
this shape. Once written, they are frozen: if code disagrees with them, the code is wrong. Change them only
by agreement between both people, and say why in the pull request.

**Per-section table** (one row per section of the main policy pair):

| Section | Change | Expected change type and timing | Affected employees and weekly cost | Route |
| --- | --- | --- | --- | --- |
| (see `docs/expected.md`) | old rule to new rule, with effective date | substantive / wording only / added / removed; current / future / unknown | employee IDs and the written math | auto-approval candidate, reviewer, or no action |

**Totals line:** number of findings, how many pass auto-approval, how many go to the reviewer, how many are
wording only, total weekly increase in effect, total weekly increase coming.

**No-change pair:** "No changes detected: N of N sections identical. 0 findings, $0.00."

**Live demo version:** the one change that is published during the demo, the employees it reaches, and the
weekly cost.

**Employee edge cases** (hand-written rows in the employee CSV, each with its expected result): an employee
below a new minimum, exactly at it, above it, with overtime, part-time, salaried exempt, a contractor below
the minimum (excluded with a classification warning), and one covered only by a future change.

**X1 (optional):** employer FICA 7.65% on the in-effect total, annualized over 52 weeks, per-employee totals
that add up to the panel, and any line that cannot be calculated flagged.

The data must cover the five validation cases in B8: a minimum wage increase affecting only some employees,
a future change shown separately from current rules, a missing effective date, a wording change with no
operational impact, and a pair with no changes.
