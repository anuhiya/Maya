# Policy files: what each shows and the expected answers

All documents are fictional. Government files: Regional Department of Labor, Payroll Standards Bulletins
PSB-2026-01 (old), PSB-2026-02 (new) and PSB-2026-03 (held back). Company file: Larkspur Supply Co. policy
HR-PAY-04. The as-of date for the demo is 2026-11-02. Employee numbers come from `employees.csv` (80 employees);
full per-employee detail is in `employee-data-notes.md`.

## Files and where they go

| File | Put it in | Role |
| --- | --- | --- |
| gov_rules_v1.txt, .pdf | data/policies/ and data/policy_site/ | Old government rules (approved baseline) |
| gov_rules_v2.txt, .pdf | data/policies/ and data/policy_site/ | New government rules (main comparison) |
| gov_rules_v3.txt, .pdf | data/policy_site/_unpublished/ | Held back; "Publish next version" in the live demo |
| company_pay_policy_v1.txt, _v2.txt, company_pay_policy.pdf | data/company_policies/ | Identical pair: the "No changes" case and the trusted company folder |
| employees.csv | data/ | 80 employees |
| scripts/make_policies.py | scripts/ | Rebuilds every policy TXT and PDF in data/ from one source if you change a value |

Every PDF was checked to split into exactly the same sections as its TXT.

## Main pair: PSB-2026-01 to PSB-2026-02 (9 sections to 10)

| Section | Category | Change | Timing | Route | Who is reached |
| --- | --- | --- | --- | --- | --- |
| 1.1 Minimum Wage, Avalon | wages | substantive: $16.00 to $17.25, Nov 1, 2026 | current | auto-approval candidate (Ready to approve) | 10 affected, $273.19 a week (R1); E076 hybrid needs review |
| 1.2 Unemployment Insurance Contribution Rate, Avalon | tax_rate | substantive: 2.7% to 3.1%, Jan 1, 2027 | future | auto-approval candidate | 25 non-contractors, no dollar figure (R2) |
| 1.3 Pay Statements, Avalon | reporting | substantive: adds "the hours worked at each rate of pay" | future | reviewer: new or changed wording | 25 non-contractors (R4 pay statement) |
| 1.4 Wage Notice at Hire, Avalon | reporting | added | future | reviewer: section added | no current employees, future hires only (R4) |
| 2.1 Minimum Wage, Calder | wages | substantive: $14.50 to $15.50, Jan 1, 2027 | future | auto-approval candidate | 7 affected, $142.80 a week (R1); E078 hybrid needs review |
| 2.2 Quarterly Wage Report Filing, Calder | filing_deadline | substantive: 30 to 20 calendar days | future | reviewer: filing deadline change | 24 non-contractors in the filing, no pay change (R3) |
| 2.3 Annual Earnings Report, Calder | reporting | substantive: once to twice a year, date line removed | unknown | reviewer: "No effective date found in section 2.3" | 24 non-contractors (R4) |
| 3.1 Minimum Wage, Meridian | | identical | | none | none |
| 3.2 Overtime Pay, Meridian | | wording only (shall/must, same 40 h and 1.5x) | | no action | nobody, no cost |
| 3.3 New Hire Reporting, Meridian | reporting | substantive: 20 to 10 calendar days, date "To be determined" | unknown | reviewer: unclear date | no current employees, future hires only (R4) |

Summary: 9 changes found (8 substantive or added, 1 wording only); 3 auto-approval candidates; 5 to the
reviewer; 1 identical section.

Classification warnings: E023 (contractor, Avalon, $15.00) on 1.1; E047 (contractor, Calder, $14.00) on 2.1.
Still to decide: E016 (salaried exempt, Avalon, implied $16.35) on 1.1.

## Per-employee weekly increases

| Section | Affected employee: weekly increase |
| --- | --- |
| 1.1 Avalon | E001 $8.17, E002 $35.60, E014 $21.84, E015 $7.80, E017 $47.50, E020 $0.40, E021 $49.88, E024 $38.00, E073 $18.00 (remote), E079 $46.00 (hybrid) |
| 2.1 Calder | E025 $20.90, E034 $14.80, E037 $26.40, E042 $47.50, E044 $0.40, E046 $16.80, E071 $16.00 (remote, Avalon office) |
| 3.1 Meridian (v3) | E048 $36.00, E055 $31.25, E064 $9.98, E065 $0.22, E072 $12.00 (remote), E080 $9.20 (overtime, new hire) |

Hybrid review items, never in totals (indicative upper bound if every hour were paid at that minimum):
E076 on 1.1 (primary Calder, part of the week in Avalon, $15.80, 40 h, up to $58.00);
E078 on 2.1 (primary Meridian, part of the week in Calder, $15.20, 24 h, up to $7.20).

## Totals

| As-of date and versions | Weekly increase in effect | Weekly increase coming |
| --- | --- | --- |
| 2026-11-02, PSB-2026-02 | $273.19 | $142.80 |
| 2026-11-02, after publishing PSB-2026-03 | $273.19 | $241.45 |
| 2027-01-01, after publishing PSB-2026-03 | $514.64 | $0.00 |

## Live demo: PSB-2026-02 to PSB-2026-03

One change only: 3.1 Minimum Wage, Meridian, $13.75 to $15.00, effective January 1, 2027. Future;
auto-approval candidate (Ready to approve in Pre-approve mode); 6 affected, $98.65 a week coming. The other 9
sections are identical.

## No-change pair: company pay policy

Byte-identical. Expected: "No changes detected: 6 of 6 sections identical." Its front matter states the
company rule for remote and hybrid staff (hybrid staff are paid at least the higher of the two minimums).

## Required cases covered

| Required case | Shown by |
| --- | --- |
| Minimum wage increase affecting only some employees | 1.1 Avalon |
| Future change shown separately | 2.1 Calder (and 3.1 in the live demo) |
| Missing effective date | 2.3 Calder |
| Wording change, no impact | 3.2 Meridian |
| No changes | company pay policy pair |

Also covered: unclear date (3.3), added section (1.4), new wording that adds a requirement (1.3), tax rate
(1.2), filing deadline (2.2), remote and hybrid work locations (E071, E073, E076, E078, E079).

## Layout rules the parser relies on

- Everything before the first numbered section (letterhead, bulletin details, notice, purpose, work location)
  is front matter and is not compared.
- Each section: a line "N.N Title", a "Jurisdiction:" line, an "Effective Date:" line (absent in 2.3 of v2 on
  purpose) and exactly one rule sentence.
- Nothing follows the last section, and the PDFs have no page headers or footers, so no stray text lands inside
  a section.
