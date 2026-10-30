# 001: The AI reads and judges; code verifies and calculates

Status: accepted. Requirements: B1, B4, B9, V1 to V3.

## Context

Maya must read policy text and work out who is affected and what it costs. A language model reads
natural language well but can invent quotes, misread numbers and do arithmetic wrongly. Payroll figures
and approvals must be exactly right and explainable to a reviewer.

## Decision

The AI plans the run, extracts facts from each section, judges substantive versus wording only, and
writes headlines, reasons and recommended actions. Code does everything that must be exact: it reads
and splits files, checks every AI answer, parses dates, matches employees by explicit rules R1 to R4,
calculates money with Decimal, routes findings and stores the history. The AI never matches an employee,
never calculates money and has no tool to approve anything.

Every AI answer is verified in layers: its JSON must fit the schema, every quote and value must appear
word for word in the source section (V1), numbers and dates are recomputed by code and compared with the
AI's claim (V2), and category, jurisdiction and change type are checked for consistency (V3). A failed
check gets one retry; a second failure goes to the reviewer. A person makes the final call (V6).

## Alternatives

- Let the AI do the whole job, including cost. Rejected: not reproducible and not auditable.
- No AI, rules only. Rejected: cannot judge wording versus substance or read varied phrasing.
- Trust the AI when it is confident. Rejected: confidence is not evidence; flag, never assume.

## Consequences

- Every number on screen can be traced to code and a source quote.
- Checks show the AI did not invent text, not that it understood the policy, so a reviewer still signs
  off.
- More code to write and test, and an AI answer that fails checks costs a retry or a reviewer's time.
