# Expected answers (fixed before the code)

Worked out from the team's own synthetic data (bulletins in `data/policies/`, employees in
`data/employees.csv`) independently of the app's code. It is frozen: tests and the demo must match it
exactly, and if code disagrees, the code is wrong. Change it only by agreement between both people, with the
reason in the pull request. Requirement: V4. Full working: `notes/policy-notes.md` and
`notes/employee-data-notes.md`.

As-of date: 2026-11-02 (toggle: 2027-01-01)
Main pair: Payroll Standards Bulletin PSB-2026-01 (gov_rules_v1, issued July 1, 2026) vs PSB-2026-02
(gov_rules_v2, issued October 15, 2026). 9 sections vs 10.

## Sections

| Section | Change (old rule to new rule, effective date) | Change type and timing | Affected employees and weekly cost (written math) | Route |
| --- | --- | --- | --- | --- |
| 1.1 Minimum Wage, New York City | $16.00 to $17.25 per hour, November 1, 2026 | substantive, current | 10 affected, $273.19 a week (R1; see edge cases). E076 hybrid: needs review, not in totals | auto-approval candidate |
| 1.2 Unemployment Insurance Contribution Rate, New York City | 2.7% to 3.1% of taxable wages, January 1, 2027 | substantive, future | 25 non-contractors, no dollar figure (R2) | auto-approval candidate |
| 1.3 Pay Statements, New York City | adds "the hours worked at each rate of pay", January 1, 2027 | substantive, future | 25 non-contractors (R4 pay statement), no pay change | reviewer: new or changed wording |
| 1.4 Wage Notice at Hire, New York City | new section, January 1, 2027 | added, future | no current employees, future hires only (R4) | reviewer: section added |
| 2.1 Minimum Wage, Los Angeles | $14.50 to $15.50 per hour, January 1, 2027 | substantive, future | 7 affected, $142.80 a week (R1). E078 hybrid: needs review, not in totals | auto-approval candidate |
| 2.2 Quarterly Wage Report Filing, Los Angeles | 30 to 20 calendar days after quarter end, January 1, 2027 | substantive, future | 24 non-contractors in the filing, no pay change (R3) | reviewer: filing deadline change |
| 2.3 Annual Earnings Report, Los Angeles | once to twice each calendar year; date line removed | substantive, unknown | 24 non-contractors (R4) | reviewer: "No effective date found in section 2.3" |
| 3.1 Minimum Wage, Chicago | unchanged ($13.75) | identical | none | none |
| 3.2 Overtime Pay, Chicago | reworded; same 40 hours and one and one-half times | wording only | nobody, no cost | no action |
| 3.3 New Hire Reporting, Chicago | 20 to 10 calendar days; date "To be determined" | substantive, unknown | no current employees, future hires only (R4) | reviewer: unclear date |

Route is one of: auto-approval candidate, reviewer (with the reason), no action, none.

## Totals

- Findings: 9. Auto-approval candidates: 3. To the reviewer: 5. Wording only: 1. Identical sections: 1.
- Weekly increase in effect: $273.19. Weekly increase coming: $142.80.
- As-of 2027-01-01: in effect $415.99, coming $0.00.
- Annualized (52 weeks): in effect $14,205.88, coming $7,425.60.

## No-change pair

Company pay policy HR-PAY-04 (company_pay_policy_v1 vs v2, byte-identical):
"No changes detected: 6 of 6 sections identical. 0 findings, $0.00."

## Live demo version

Publish PSB-2026-03 (gov_rules_v3). One change: 3.1 Minimum Wage, Chicago, $13.75 to $15.00, effective
January 1, 2027. Substantive, future. 6 affected: E048 $36.00, E055 $31.25, E064 $9.98, E065 $0.22,
E072 $12.00, E080 $9.20 = $98.65 a week coming. Auto-approval candidate (Ready to approve in Pre-approve
mode). The other 9 sections are identical. After publishing: in effect $273.19, coming $241.45; as-of
2027-01-01: in effect $514.64.

## Employee edge cases

| Employee ID | Jurisdiction | Type | Wage | Hours per week | Expected result and cost |
| --- | --- | --- | --- | --- | --- |
| E017 | New York City | hourly FT | $16.00 | 38 | affected by 1.1, at the current minimum: 1.25 x 38 h = $47.50 |
| E020 | New York City | hourly FT | $17.24 | 40 | affected by 1.1, one cent below: 0.01 x 40 h = $0.40 |
| E004 | New York City | hourly FT | $17.25 | 40 | not affected by 1.1, exactly at the new minimum |
| E013 | New York City | hourly PT | $17.25 | 30 | not affected by 1.1, exactly at the new minimum |
| E077 | New York City | hourly FT, hybrid (secondary Chicago) | $17.60 | 40 | not affected by 1.1, above; no hybrid flag because Chicago's minimum is lower |
| E001 | New York City | hourly FT, overtime | $17.06 | 42 | affected by 1.1: 0.19 x 40 h + 0.19 x 1.5 x 2 h = $8.17 |
| E015 | New York City | hourly PT | $16.86 | 20 | affected by 1.1: 0.39 x 20 h = $7.80 |
| E002 | New York City | hourly FT, onsite, lives in Los Angeles | $16.36 | 40 | affected by 1.1 (work location, not home): 0.89 x 40 h = $35.60 |
| E073 | New York City | hourly FT, remote, Chicago office | $16.80 | 40 | affected by 1.1 (home is the work location): 0.45 x 40 h = $18.00 |
| E079 | New York City | hourly FT, hybrid in one jurisdiction | $16.10 | 40 | affected by 1.1: 1.15 x 40 h = $46.00 |
| E016 | New York City | salaried exempt | $16.35 (annual $34,000) | 45 | excluded from 1.1 (exempt); classification warning still to decide |
| E023 | New York City | contractor | $15.00 | 20 | excluded from 1.1, classification warning (below the new minimum) |
| E076 | Los Angeles | hourly FT, hybrid (secondary New York City) | $15.80 | 40 | under 1.1: "Needs review: works part of the week in New York City", upper bound 1.45 x 40 h = $58.00, not in totals; under 2.1: not affected (above $15.50) |
| E025 | Los Angeles | hourly PT | $14.55 | 22 | affected only by the future change 2.1: 0.95 x 22 h = $20.90 (future) |
| E071 | Los Angeles | hourly FT, remote, New York City office | $15.10 | 40 | affected by 2.1 only, not by 1.1: 0.40 x 40 h = $16.00 (future) |
| E047 | Los Angeles | contractor | $14.00 | 20 | excluded from 2.1, classification warning |
| E078 | Chicago | hourly PT, hybrid (secondary Los Angeles) | $15.20 | 24 | under 2.1: "Needs review: works part of the week in Los Angeles", upper bound 0.30 x 24 h = $7.20, not in totals; under 3.1 (v3): not affected |
| E080 | Chicago | hourly FT, overtime, new hire | $14.80 | 44 | affected by 3.1 in v3: 0.20 x 40 h + 0.20 x 1.5 x 4 h = $9.20 (future) |
| E068 | Chicago | hourly FT, lives in Los Angeles | $15.00 | 45 | not affected by 3.1 in v3, exactly at the new minimum |

## Optional X1 numbers

Employer FICA 7.65% on the in-effect total: 0.0765 x $273.19 = $20.90 a week; annualized (52 weeks):
0.0765 x $14,205.88 = $1,086.75 (computed from the annualized total, then rounded once). Weekly increase in effect annualized: $14,205.88. Lines flagged instead of calculated:
unemployment contribution (rate changes on taxable wages, no wage base modelled) and back pay (needs
reviewer input).

## Proposed law scenario (A9)

Worked out by hand from `data/employees.csv`, apart from the app's code. Nothing above this heading changes.
The document is `data/policies/proposed/proposed_bill_v1.txt` (bill HB-2026-117, stage Proposed, not a review status).
One section, 1.1 Minimum Wage, Los Angeles, effective July 1, 2027: the minimum would be $17.00 an hour. As of
2026-11-02 it is in the future, so it is shown apart and is never added to the in-effect or coming totals.

**Correction (baseline check).** The first hand calculation priced the bill from today's wages and gave $635.01 a week.
That double counted the $142.80 coming under section 2.1, because 2.1 already lifts seven Los Angeles employees to $15.50 from
January 1, 2027, before the bill's date. The bill is therefore priced from the wage after existing changes: the higher of
the employee's wage and the Los Angeles minimum already coming ($15.50). The check: 635.01 - 142.80 = 492.21.

**If enacted.** Matching rule R1 and the same cost method as the main pair: an hourly full-time or part-time
Los Angeles employee whose wage after existing changes is below $17.00 is affected; weekly difference = gap x regular hours
(up to 40) + gap x 1.5 x hours beyond 40; each amount rounded half up to the cent.

| Employee ID | Wage now | Wage after existing changes | Target | Hours | Calculation | Weekly |
| --- | --- | --- | --- | --- | --- | --- |
| E025 | $14.55 | $15.50 | $17.00 | 22 | 1.50 x 22 | $33.00 |
| E030 | $15.92 | $15.92 | $17.00 | 12 | 1.08 x 12 | $12.96 |
| E034 | $15.13 | $15.50 | $17.00 | 40 | 1.50 x 40 | $60.00 |
| E037 | $14.84 | $15.50 | $17.00 | 40 | 1.50 x 40 | $60.00 |
| E039 | $15.50 | $15.50 | $17.00 | 38 | 1.50 x 38 | $57.00 |
| E042 | $14.50 | $15.50 | $17.00 | 45 | 1.50 x 40 + 1.50 x 1.5 x 5 | $71.25 |
| E044 | $15.49 | $15.50 | $17.00 | 40 | 1.50 x 40 | $60.00 |
| E046 | $14.66 | $15.50 | $17.00 | 20 | 1.50 x 20 | $30.00 |
| E071 | $15.10 | $15.50 | $17.00 | 40 | 1.50 x 40 | $60.00 |
| E076 | $15.80 | $15.80 | $17.00 | 40 | 1.20 x 40 | $48.00 |

- Affected: 10 Los Angeles employees (the seven raised by 2.1 are E025, E034, E037, E042, E044, E046 and E071). Weekly total:
  33.00 + 12.96 + 60.00 + 60.00 + 57.00 + 71.25 + 60.00 + 30.00 + 60.00 + 48.00 = **$492.21 a week**.
- Annualized (52 weeks): 492.21 x 52 = **$25,594.92**.
- Employer Social Security and Medicare estimate, 7.65 percent of the weekly total: 0.0765 x 492.21 = **$37.65 a week**;
  annualized, computed from the annualized total and rounded once: 0.0765 x 25,594.92 = **$1,958.01**.
- Total with the tax estimate: 492.21 + 37.65 = **$529.86 a week**; 25,594.92 + 1,958.01 = **$27,552.93 a year**.
- Affected employees by jurisdiction: Los Angeles 10, New York City 0, Chicago 0.
- Los Angeles, not affected (wage at or above $17.00): E026, E027, E028, E033, E035, E036, E040, E041, E043, E045 (10).
- Los Angeles, excluded: contractors E029 and E047 (E047 at $14.00 gets a classification warning), salaried exempt
  E031, E032, E038 and E074 (6). Los Angeles total: 10 + 10 + 6 = 26 employees.
- Hybrid rule: E076 works in Los Angeles (primary) with a secondary New York City, so it is matched in Los Angeles and counted. E078
  works in Chicago (primary) with a secondary Los Angeles, so it is not counted: "Needs review: works part of the week in
  Los Angeles", upper bound 1.80 x 24 = $43.20 (its wage after existing changes is still $15.20), never in any total. $7.20 of that
  bound is already flagged under 2.1, so the two bounds are not added. E022 (salaried exempt) has no row.
- Date: July 1, 2027 is after 2026-11-02 (future). At an as-of date of 2027-07-01 or later it moves to current.
- What to prepare: update the Los Angeles rate table to $17.00 from July 1, 2027 for the 10 affected employees, send the
  affected employees a notice of their new rate, set the effective date in payroll, review E078's split of hours and
  E047's classification, and add a budget line of $529.86 a week.

**If not enacted.** The bulletin's Los Angeles minimum ($15.50 from January 1, 2027) stays; change in cost **$0.00**. The risk of
not preparing, such as back pay or penalties if it passes, is shown as "Needs reviewer input" and never calculated.

## Real proposed bills (A9)

Real bill texts, synthetic workforce. The bill text was saved unaltered from the official page (see
`data/policies/proposed/real/`); every figure below is worked out by hand from `data/employees.csv`, apart from the
app's code. Retrieved November 1, 2026. Real-bill totals are separate and never added to the in-effect or coming totals.
Trust flag for every real bill: informational only.

### New York City Council Introduction 757 of 2026 (Int 0757-2026), status "Committee"

Source: legistar.council.nyc.gov, file Int 0757-2026, "A Local Law to amend the administrative code of the city of New
York, in relation to the establishment of the minimum wage". Prime sponsor Sandy Nurse. Introduced March 10, 2026;
last action "Referred to Comm by Council" (Committee on Consumer and Worker Protection). Not enacted.

What the text says: Schedule 1 employers (more than 500 employees nationwide) pay at least $20 an hour on or after
January 1, 2027. Schedule 2 employers (500 or fewer employees nationwide) pay at least $19 an hour on or after
January 1, 2027. Later steps run to 2031 and are not priced here. Government employers and employees are excluded.
Food service workers who receive tips may be paid at least two-thirds of the minimum wage in cash. Overtime follows
New York law. The local law takes effect 180 days after it becomes law.

Applies to this company? The data holds 80 employees, so Schedule 2 ($19) is used, assuming the company has 500 or
fewer employees nationwide (the data cannot show more). The data has no tip information, so tipped food service
workers are priced at the full minimum, which makes the figures an upper bound for them. New York City employees: 28.

Method: the existing minimum wage method. Baseline = wage after existing changes = the higher of the wage and the
$17.25 New York City minimum already in effect from November 1, 2026 (bulletin 1.1). Weekly difference = gap x regular
hours (up to 40) + gap x 1.5 x hours beyond 40, rounded half up to the cent. Target $19.00. As of 2026-11-02 the date
January 1, 2027 is in the future.

| Employee ID | Wage now | Wage after existing changes | Target | Hours | Calculation | Weekly |
| --- | --- | --- | --- | --- | --- | --- |
| E001 | $17.06 | $17.25 | $19.00 | 42 | 1.75 x 40 + 1.75 x 1.5 x 2 | $75.25 |
| E002 | $16.36 | $17.25 | $19.00 | 40 | 1.75 x 40 | $70.00 |
| E004 | $17.25 | $17.25 | $19.00 | 40 | 1.75 x 40 | $70.00 |
| E012 | $17.85 | $17.85 | $19.00 | 24 | 1.15 x 24 | $27.60 |
| E013 | $17.25 | $17.25 | $19.00 | 30 | 1.75 x 30 | $52.50 |
| E014 | $16.83 | $17.25 | $19.00 | 48 | 1.75 x 40 + 1.75 x 1.5 x 8 | $91.00 |
| E015 | $16.86 | $17.25 | $19.00 | 20 | 1.75 x 20 | $35.00 |
| E017 | $16.00 | $17.25 | $19.00 | 38 | 1.75 x 38 | $66.50 |
| E018 | $18.98 | $18.98 | $19.00 | 38 | 0.02 x 38 | $0.76 |
| E020 | $17.24 | $17.25 | $19.00 | 40 | 1.75 x 40 | $70.00 |
| E021 | $16.20 | $17.25 | $19.00 | 45 | 1.75 x 40 + 1.75 x 1.5 x 5 (83.125) | $83.13 |
| E024 | $16.30 | $17.25 | $19.00 | 40 | 1.75 x 40 | $70.00 |
| E073 | $16.80 | $17.25 | $19.00 | 40 | 1.75 x 40 | $70.00 |
| E077 | $17.60 | $17.60 | $19.00 | 40 | 1.40 x 40 | $56.00 |
| E079 | $16.10 | $17.25 | $19.00 | 40 | 1.75 x 40 | $70.00 |

- Affected: 15 New York City employees. Weekly total: 75.25 + 70.00 + 70.00 + 27.60 + 52.50 + 91.00 + 35.00 + 66.50 +
  0.76 + 70.00 + 83.13 + 70.00 + 70.00 + 56.00 + 70.00 = **$907.74 a week**.
- Annualized (52 weeks): 907.74 x 52 = **$47,202.48**.
- Employer Social Security and Medicare estimate, 7.65 percent: 0.0765 x 907.74 = **$69.44 a week**; annualized, from the
  annualized total, rounded once: 0.0765 x 47,202.48 = **$3,610.99**.
- Total with the tax estimate: 907.74 + 69.44 = **$977.18 a week**; 47,202.48 + 3,610.99 = **$50,813.47 a year**.
- Affected employees by jurisdiction: New York City 15, Los Angeles 0, Chicago 0.
- Not affected (wage at or above $19.00 after existing changes): E003, E005, E007, E008, E009, E010, E019 (7).
- Excluded: salaried exempt E006, E016, E022 and contractors E011, E023, E075. E023 is paid $15.00, below $19.00, so it gets
  a classification warning.
- Hybrid: E076 works in Los Angeles (primary) with New York City as the secondary jurisdiction, so it is "Needs review:
  works part of the week in New York City", upper bound 3.20 x 40 = **$128.00**, never in any total.
- New York City total: 15 + 7 + 6 = 28 employees.
- If not enacted: the $17.25 minimum stays; change in cost $0.00; risk of not preparing is "Needs reviewer input".

### New York State Assembly A6086 of 2025 to 2026, status "IN ASSEMBLY COMMITTEE" (Assembly Labor)

Source: nysenate.gov, bill 2025-A6086, "AN ACT to amend the labor law, in relation to the minimum wage outside of New
York city and the counties of Nassau, Suffolk, and Westchester". Sponsor M. of A. Bronson. Introduced February 26, 2025;
last action "referred to labor" on January 7, 2026. Not enacted. It would set $17.00 on and after January 1, 2026 for
the rest of the state and takes effect immediately.

Expected: **Not applicable to this company, covers: outside the city of New York and the counties of Nassau, Suffolk,
and Westchester.** The synthetic company's employees work in New York City, Los Angeles and Chicago, so none is covered.
No cost is calculated: affected employees 0, weekly cost not shown.

### Los Angeles citywide minimum wage initiative ("Olympic Wage"), status "Approved for Circulation"

Source: the City Clerk's pages for citizen-sponsored initiatives (clerk.lacity.gov, ballot measures and petition text, and the
petition status table). Title "Increase to Minimum Wage; Changes to Wage/Labor Standards (Olympic Wage)". Request for title and
summary filed December 29, 2025; official title and summary January 8, 2026; approved for circulation January 21, 2026, expires
January 21, 2028; no petition filed as of retrieval (November 1, 2026). Not enacted. The proponent contact is a law firm.

What the saved text says (the City Clerk's official title and summary; the 27-page proposed ordinance on the same page is a scanned
PDF with no text layer, so it is saved unaltered but cannot be read by the app): the minimum wage in the City of Los Angeles would
rise to $25.00 an hour for employers with 26 or more employees and $20.00 an hour for smaller employers, to $30.00 by 2030 (2032
for smaller employers) and at least 3 percent a year after. No effective date is stated, so the timing is unknown. The $20.00
tier does not apply (the data holds 80 employees). Later steps are not priced.

Method as above: baseline = the higher of the wage and the $15.50 Los Angeles minimum already coming in the bulletin (2.1),
target $25.00. The bill states no date, so the bulletin minimum is treated as already in place; this is an assumption the page states.

| Employee ID | Wage now | After existing | Hours | Calculation | Weekly |
| --- | --- | --- | --- | --- | --- |
| E025 | $14.55 | $15.50 | 22 | 9.50 x 22 | $209.00 |
| E026 | $17.51 | $17.51 | 48 | 7.49 x 40 + 7.49 x 1.5 x 8 | $389.48 |
| E027 | $24.34 | $24.34 | 44 | 0.66 x 40 + 0.66 x 1.5 x 4 | $30.36 |
| E028 | $22.26 | $22.26 | 16 | 2.74 x 16 | $43.84 |
| E030 | $15.92 | $15.92 | 12 | 9.08 x 12 | $108.96 |
| E033 | $22.51 | $22.51 | 48 | 2.49 x 40 + 2.49 x 1.5 x 8 | $129.48 |
| E034 | $15.13 | $15.50 | 40 | 9.50 x 40 | $380.00 |
| E035 | $23.67 | $23.67 | 40 | 1.33 x 40 | $53.20 |
| E036 | $19.03 | $19.03 | 37.5 | 5.97 x 37.5 | $223.88 |
| E037 | $14.84 | $15.50 | 40 | 9.50 x 40 | $380.00 |
| E039 | $15.50 | $15.50 | 38 | 9.50 x 38 | $361.00 |
| E040 | $24.18 | $24.18 | 40 | 0.82 x 40 | $32.80 |
| E041 | $21.23 | $21.23 | 37.5 | 3.77 x 37.5 | $141.38 |
| E042 | $14.50 | $15.50 | 45 | 9.50 x 40 + 9.50 x 1.5 x 5 | $451.25 |
| E043 | $24.31 | $24.31 | 40 | 0.69 x 40 | $27.60 |
| E044 | $15.49 | $15.50 | 40 | 9.50 x 40 | $380.00 |
| E045 | $19.82 | $19.82 | 40 | 5.18 x 40 | $207.20 |
| E046 | $14.66 | $15.50 | 20 | 9.50 x 20 | $190.00 |
| E071 | $15.10 | $15.50 | 40 | 9.50 x 40 | $380.00 |
| E076 | $15.80 | $15.80 | 40 | 9.20 x 40 | $368.00 |

- Affected: 20 Los Angeles employees. Weekly total **$4,487.43 a week**; annualized (x 52) **$233,346.36**.
- Employer tax estimate: 0.0765 x 4,487.43 = **$343.29 a week**; 0.0765 x 233,346.36 = **$17,851.00 a year**.
- Total with the tax estimate: **$4,830.72 a week**; **$251,197.36 a year**.
- Not affected: none. Excluded: contractors E029 and E047 (E047 at $14.00 gets a classification warning), salaried exempt E031, E032,
  E038, E074. Los Angeles total: 20 + 6 = 26 employees.
- Hybrid: E078 works in Chicago (primary) with Los Angeles as secondary: "Needs review", upper bound 9.80 x 24 = **$235.20**, never in a total.
- Timing: unknown (no date stated), so the amounts are "if enacted, from an unstated date".

### Bills looked at and not used

- Los Angeles, Council File 14-1371-S13 (Ordinance No. 188610, hotel and airport workers): already enacted (effective
  September 8, 2025) and the ordinance text could not be downloaded from an official page, so it is not used.
- Chicago: no pending minimum wage ordinance was found on official pages, so none is used.
