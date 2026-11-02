# Reading and comparing (B1, B2, V1 to V3)

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
