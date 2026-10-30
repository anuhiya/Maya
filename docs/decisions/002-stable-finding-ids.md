# 002: Stable finding IDs

Status: accepted. Requirements: B2, B6, B7.

## Context

Review history is append-only and keyed by finding. When a newer version of a bulletin arrives, the
same section must keep the same ID, or earlier decisions detach from it. File names and version labels
(gov_rules_v2, gov_rules_v3) change with every version, and AI output varies between runs, so neither can
be part of the ID.

## Decision

A finding ID is the first 12 hex characters of SHA-256 over `policy_family | section | category`.

- `policy_family` is a stable name read from `maya.config.yaml`, the same for every version of a
  bulletin. It is never a file name or version.
- `section` is the section number as written, for example `1.1`.
- `category` is one of the five shared labels.

The function is `finding_id` in `maya/models.py`. A test checks that the same section in gov_rules_v2 and
gov_rules_v3 gets the same ID.

## Alternatives

- Random IDs. Rejected: a rerun would create new IDs and orphan decisions.
- Hash including the file name or version. Rejected: every new version would break history.
- Hash of the section text. Rejected: any wording change would create a new finding.
- A counter. Rejected: depends on run order.

## Consequences

- A decision on 3.1 in v2 still shows against 3.1 in v3, which is what a reviewer expects.
- If the AI changes a section's category between runs, the ID changes; that is surfaced as a new
  finding rather than hidden.
- Renumbering sections in a new bulletin creates new IDs. Acceptable for the numbered policies in scope.
- `maya.config.yaml` needs a policy family name per policy (not yet present; to be added).
