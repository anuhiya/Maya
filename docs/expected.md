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
| 1.1 Minimum Wage, Avalon | $16.00 to $17.25 per hour, November 1, 2026 | substantive, current | 10 affected, $273.19 a week (R1; see edge cases). E076 hybrid: needs review, not in totals | auto-approval candidate |
| 1.2 Unemployment Insurance Contribution Rate, Avalon | 2.7% to 3.1% of taxable wages, January 1, 2027 | substantive, future | 25 non-contractors, no dollar figure (R2) | auto-approval candidate |
| 1.3 Pay Statements, Avalon | adds "the hours worked at each rate of pay", January 1, 2027 | substantive, future | 25 non-contractors (R4 pay statement), no pay change | reviewer: new or changed wording |
| 1.4 Wage Notice at Hire, Avalon | new section, January 1, 2027 | added, future | no current employees, future hires only (R4) | reviewer: section added |
| 2.1 Minimum Wage, Calder | $14.50 to $15.50 per hour, January 1, 2027 | substantive, future | 7 affected, $142.80 a week (R1). E078 hybrid: needs review, not in totals | auto-approval candidate |
| 2.2 Quarterly Wage Report Filing, Calder | 30 to 20 calendar days after quarter end, January 1, 2027 | substantive, future | 24 non-contractors in the filing, no pay change (R3) | reviewer: filing deadline change |
| 2.3 Annual Earnings Report, Calder | once to twice each calendar year; date line removed | substantive, unknown | 24 non-contractors (R4) | reviewer: "No effective date found in section 2.3" |
| 3.1 Minimum Wage, Meridian | unchanged ($13.75) | identical | none | none |
| 3.2 Overtime Pay, Meridian | reworded; same 40 hours and one and one-half times | wording only | nobody, no cost | no action |
| 3.3 New Hire Reporting, Meridian | 20 to 10 calendar days; date "To be determined" | substantive, unknown | no current employees, future hires only (R4) | reviewer: unclear date |

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

Publish PSB-2026-03 (gov_rules_v3). One change: 3.1 Minimum Wage, Meridian, $13.75 to $15.00, effective
January 1, 2027. Substantive, future. 6 affected: E048 $36.00, E055 $31.25, E064 $9.98, E065 $0.22,
E072 $12.00, E080 $9.20 = $98.65 a week coming. Auto-approval candidate (Ready to approve in Pre-approve
mode). The other 9 sections are identical. After publishing: in effect $273.19, coming $241.45; as-of
2027-01-01: in effect $514.64.

## Employee edge cases

| Employee ID | Jurisdiction | Type | Wage | Hours per week | Expected result and cost |
| --- | --- | --- | --- | --- | --- |
| E017 | Avalon | hourly FT | $16.00 | 38 | affected by 1.1, at the current minimum: 1.25 x 38 h = $47.50 |
| E020 | Avalon | hourly FT | $17.24 | 40 | affected by 1.1, one cent below: 0.01 x 40 h = $0.40 |
| E004 | Avalon | hourly FT | $17.25 | 40 | not affected by 1.1, exactly at the new minimum |
| E013 | Avalon | hourly PT | $17.25 | 30 | not affected by 1.1, exactly at the new minimum |
| E077 | Avalon | hourly FT, hybrid (secondary Meridian) | $17.60 | 40 | not affected by 1.1, above; no hybrid flag because Meridian's minimum is lower |
| E001 | Avalon | hourly FT, overtime | $17.06 | 42 | affected by 1.1: 0.19 x 40 h + 0.19 x 1.5 x 2 h = $8.17 |
| E015 | Avalon | hourly PT | $16.86 | 20 | affected by 1.1: 0.39 x 20 h = $7.80 |
| E002 | Avalon | hourly FT, onsite, lives in Calder | $16.36 | 40 | affected by 1.1 (work location, not home): 0.89 x 40 h = $35.60 |
| E073 | Avalon | hourly FT, remote, Meridian office | $16.80 | 40 | affected by 1.1 (home is the work location): 0.45 x 40 h = $18.00 |
| E079 | Avalon | hourly FT, hybrid in one jurisdiction | $16.10 | 40 | affected by 1.1: 1.15 x 40 h = $46.00 |
| E016 | Avalon | salaried exempt | $16.35 (annual $34,000) | 45 | excluded from 1.1 (exempt); classification warning still to decide |
| E023 | Avalon | contractor | $15.00 | 20 | excluded from 1.1, classification warning (below the new minimum) |
| E076 | Calder | hourly FT, hybrid (secondary Avalon) | $15.80 | 40 | under 1.1: "Needs review: works part of the week in Avalon", upper bound 1.45 x 40 h = $58.00, not in totals; under 2.1: not affected (above $15.50) |
| E025 | Calder | hourly PT | $14.55 | 22 | affected only by the future change 2.1: 0.95 x 22 h = $20.90 (future) |
| E071 | Calder | hourly FT, remote, Avalon office | $15.10 | 40 | affected by 2.1 only, not by 1.1: 0.40 x 40 h = $16.00 (future) |
| E047 | Calder | contractor | $14.00 | 20 | excluded from 2.1, classification warning |
| E078 | Meridian | hourly PT, hybrid (secondary Calder) | $15.20 | 24 | under 2.1: "Needs review: works part of the week in Calder", upper bound 0.30 x 24 h = $7.20, not in totals; under 3.1 (v3): not affected |
| E080 | Meridian | hourly FT, overtime, new hire | $14.80 | 44 | affected by 3.1 in v3: 0.20 x 40 h + 0.20 x 1.5 x 4 h = $9.20 (future) |
| E068 | Meridian | hourly FT, lives in Calder | $15.00 | 45 | not affected by 3.1 in v3, exactly at the new minimum |

## Optional X1 numbers

Employer FICA 7.65% on the in-effect total: 0.0765 x $273.19 = $20.90 a week; annualized (52 weeks):
0.0765 x $14,205.88 = $1,086.75 (computed from the annualized total, then rounded once). Weekly increase in effect annualized: $14,205.88. Lines flagged instead of calculated:
unemployment contribution (rate changes on taxable wages, no wage base modelled) and back pay (needs
reviewer input).
