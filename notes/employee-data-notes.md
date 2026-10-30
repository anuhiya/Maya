# Employee dataset: notes (80 employees)

Synthetic and fictional. File: `employees.csv`. The brief's five columns come first; the rest are extra payroll fields. Matching always uses `jurisdiction`, the place where the work is performed.

## Minimum wages used (from the policy bulletins)

| Jurisdiction | Current minimum | New minimum | Effective | Timing at as-of 2026-11-02 | Bulletin |
| --- | --- | --- | --- | --- | --- |
| Avalon | $16.00 | $17.25 | November 1, 2026 | in effect | PSB-2026-02, section 1.1 |
| Calder | $14.50 | $15.50 | January 1, 2027 | future | PSB-2026-02, section 2.1 |
| Meridian | $13.75 | $15.00 | January 1, 2027 | future, published live in the demo | PSB-2026-03, section 3.1 |

Every hourly employee earns at least today's minimum where they work, so the data is lawful today and only the new minimums reach anyone.

## Columns

| Column | Meaning |
| --- | --- |
| employee_id | E001 to E080, unique |
| jurisdiction | work location: where the work is performed. Used for matching. For remote staff this is their home |
| hourly_wage | dollars per hour; for salaried staff annual salary / 2080, for information only |
| weekly_hours | standard scheduled hours per week (37.5, 48 and so on) |
| employment_type | hourly_full_time, hourly_part_time, salaried_exempt, contractor |
| full_name | fictional |
| job_title, department | role context |
| hire_date | YYYY-MM-DD; six hires fall in September to October 2026 for new-hire scenarios |
| pay_frequency | weekly, biweekly, semimonthly, per_invoice (contractors) |
| flsa_status | non_exempt, exempt, not_applicable (contractors) |
| overtime_eligible | yes for hourly staff, no for exempt staff and contractors |
| annual_salary | salaried_exempt only |
| work_arrangement | onsite, hybrid or remote |
| office_location | the company office the employee reports to; can differ from jurisdiction for remote staff |
| secondary_jurisdiction | hybrid only: the other jurisdiction where part of the week is worked; blank otherwise |
| residence_jurisdiction | where the person lives, for information; 'Outside' means none of the three |

**Validation rules (loader reports a bad row, never drops it):** work_arrangement is onsite, hybrid or remote; office_location is a known jurisdiction; onsite means office_location equals jurisdiction and no secondary_jurisdiction; remote means residence_jurisdiction equals jurisdiction; secondary_jurisdiction, when present, is a known jurisdiction different from jurisdiction and only on hybrid rows.

## Mix

| Jurisdiction | Total | Hourly FT | Hourly PT | Salaried exempt | Contractor | Onsite | Hybrid | Remote |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Avalon | 28 | 17 | 5 | 3 | 3 | 16 | 7 | 5 |
| Calder | 26 | 16 | 4 | 4 | 2 | 18 | 3 | 5 |
| Meridian | 26 | 15 | 7 | 3 | 1 | 20 | 3 | 3 |
| Total | 80 | 48 | 16 | 10 | 6 | 54 | 13 | 13 |

Non-contractor employees by work location (used by tax, filing and pay statement rules): Avalon 25, Calder 24, Meridian 25.

## Work-location rules (matching)

- **Onsite:** the office is the work location. Six onsite staff live across a border and commute (E002, E020, E039, E041, E052, E068); they are matched by where they work, never where they live.
- **Remote:** the home is the work location. E071 reports to the Avalon office but works from home in Calder, so Calder's minimum applies and Avalon's does not reach them.
- **Hybrid in one jurisdiction:** matched normally (E079).
- **Hybrid across two jurisdictions:** matched by the primary `jurisdiction`. If the hourly wage is below the new minimum of `secondary_jurisdiction`, Maya does not guess the split of hours: the employee is listed under that change as **Needs review: works part of the week in <jurisdiction>** with an indicative upper bound (all hours at that minimum), kept out of the totals. Company policy HR-PAY-04 says hybrid staff are paid at least the higher minimum, so the reviewer can confirm it. If the secondary minimum is lower, nothing is flagged (E077).

## Expected results by change

### Section 1.1, Avalon minimum wage $16.00 to $17.25, effective November 1, 2026 (current, v2)

**Affected: 10 employees, $273.19 a week (current).**

| Employee | Type | Arrangement | Wage | Hours | Weekly increase |
| --- | --- | --- | --- | --- | --- |
| E001 | hourly_full_time | hybrid | $17.06 | 42 | 0.19 x 40 h + 0.19 x 1.5 x 2 h = $8.17 |
| E002 | hourly_full_time | onsite | $16.36 | 40 | 0.89 x 40 h = $35.60 |
| E014 | hourly_full_time | onsite | $16.83 | 48 | 0.42 x 40 h + 0.42 x 1.5 x 8 h = $21.84 |
| E015 | hourly_part_time | onsite | $16.86 | 20 | 0.39 x 20 h = $7.80 |
| E017 | hourly_full_time | onsite | $16.00 | 38 | 1.25 x 38 h = $47.50 |
| E020 | hourly_full_time | onsite | $17.24 | 40 | 0.01 x 40 h = $0.40 |
| E021 | hourly_full_time | hybrid | $16.20 | 45 | 1.05 x 40 h + 1.05 x 1.5 x 5 h = $49.88 |
| E024 | hourly_full_time | hybrid | $16.30 | 40 | 0.95 x 40 h = $38.00 |
| E073 | hourly_full_time | remote | $16.80 | 40 | 0.45 x 40 h = $18.00 |
| E079 | hourly_full_time | hybrid | $16.10 | 40 | 1.15 x 40 h = $46.00 |

Not affected: 12 hourly employees at or above $17.25 (exactly at it: E004, E013).
Excluded: E006, E011, E016, E022, E023, E075 (salaried exempt and contractors).
Classification warning (contractor paid below the new minimum): E023 $15.00.
Needs review, not in totals: E076 (hybrid, primary Calder, works part of the week in Avalon, $15.80, 40 h); indicative upper bound 1.45 x 40 h = $58.00.

### Section 2.1, Calder minimum wage $14.50 to $15.50, effective January 1, 2027 (future, v2)

**Affected: 7 employees, $142.80 a week (future).**

| Employee | Type | Arrangement | Wage | Hours | Weekly increase |
| --- | --- | --- | --- | --- | --- |
| E025 | hourly_part_time | onsite | $14.55 | 22 | 0.95 x 22 h = $20.90 |
| E034 | hourly_full_time | onsite | $15.13 | 40 | 0.37 x 40 h = $14.80 |
| E037 | hourly_full_time | onsite | $14.84 | 40 | 0.66 x 40 h = $26.40 |
| E042 | hourly_full_time | remote | $14.50 | 45 | 1.00 x 40 h + 1.00 x 1.5 x 5 h = $47.50 |
| E044 | hourly_full_time | onsite | $15.49 | 40 | 0.01 x 40 h = $0.40 |
| E046 | hourly_part_time | hybrid | $14.66 | 20 | 0.84 x 20 h = $16.80 |
| E071 | hourly_full_time | remote | $15.10 | 40 | 0.40 x 40 h = $16.00 |

Not affected: 13 hourly employees at or above $15.50 (exactly at it: E039).
Excluded: E029, E031, E032, E038, E047, E074 (salaried exempt and contractors).
Classification warning (contractor paid below the new minimum): E047 $14.00.
Needs review, not in totals: E078 (hybrid, primary Meridian, works part of the week in Calder, $15.20, 24 h); indicative upper bound 0.30 x 24 h = $7.20.

### Section 3.1, Meridian minimum wage $13.75 to $15.00, effective January 1, 2027 (future, v3 (live demo))

**Affected: 6 employees, $98.65 a week (future).**

| Employee | Type | Arrangement | Wage | Hours | Weekly increase |
| --- | --- | --- | --- | --- | --- |
| E048 | hourly_full_time | onsite | $14.10 | 40 | 0.90 x 40 h = $36.00 |
| E055 | hourly_part_time | onsite | $13.75 | 25 | 1.25 x 25 h = $31.25 |
| E064 | hourly_full_time | onsite | $14.79 | 45 | 0.21 x 40 h + 0.21 x 1.5 x 5 h = $9.98 |
| E065 | hourly_part_time | onsite | $14.99 | 22 | 0.01 x 22 h = $0.22 |
| E072 | hourly_part_time | remote | $14.40 | 20 | 0.60 x 20 h = $12.00 |
| E080 | hourly_full_time | onsite | $14.80 | 44 | 0.20 x 40 h + 0.20 x 1.5 x 4 h = $9.20 |

Not affected: 16 hourly employees at or above $15.00 (exactly at it: E068).
Excluded: E049, E054, E059, E060 (salaried exempt and contractors).

## Totals

| As-of date and versions | Weekly increase in effect | Weekly increase coming |
| --- | --- | --- |
| 2026-11-02, bulletin v2 | $273.19 | $142.80 |
| 2026-11-02, after publishing v3 | $273.19 | $241.45 |
| 2027-01-01, after publishing v3 | $514.64 | $0.00 |

Annualized figures use 52 weeks. Hybrid review items are never included in totals.

## Other edge cases

- E016: salaried exempt, Avalon, annual $34,000 (implied $16.35 an hour, below $17.25): excluded; decide whether to show a classification warning.
- E074 (remote, exempt) and E075 (remote, contractor): excluded whatever their arrangement.
- Recent hires (September to October 2026): E052 (2026-09-14), E008 (2026-10-05), E070 (2026-10-12), E043 (2026-10-19), E033 (2026-10-26), E080 (2026-10-28). New-hire rules (Avalon 1.4, Meridian 3.3) apply to future hires only, so these are not matched.
- E022: salaried exempt, hybrid between Avalon and Calder: excluded from wage rules; hybrid flags apply to hourly staff only.
