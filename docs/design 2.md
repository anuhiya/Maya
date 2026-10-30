# Maya: design (P2)

Visual reference: the Maya canvas (claude.ai artifact, pages Agent, Review queue, Employee impact,
Review history, Export, Sources). Take screenshots of it and drop them into Claude Code when building
each page. This file is the part Claude Code must follow exactly.

## Why it looks like this (be ready to say this to Jon)

- First impressions form in 17 to 50 ms, and simple, familiar layouts score highest (Google research).
- About 80% of eye fixations land on the left half of a screen (Nielsen Norman Group), so navigation and
  the queue sit on the left and the decision sits where the eye ends.
- People judge good-looking tools as easier to use (aesthetic-usability effect, Kurosu and Kashimura).
- Contrast meets WCAG: 4.5:1 for text, 3:1 for controls. Colour is never the only signal: every status
  also has a word.

## Palette: Terracotta & Paper

| Token | Hex | Use |
| --- | --- | --- |
| bg | #F3EEE6 | page background |
| surface | #FFFCF7 | cards, panels |
| ink | #23201C | main text |
| muted | #6B6259 | secondary text |
| line | #E5DCCD | borders, dividers |
| accent | #B5472A | primary button, wordmark full stop, selected item |
| good / good-bg | #3D6640 / #E4EEDF | approved, passed checks |
| review / review-bg | #8A5A0F / #F6E7C4 | needs review, flags |
| future / future-bg | #34557A / #DDE6F0 | future-dated changes |
| critical / critical-bg | #A23A2C / #F5DCD6 | errors, removed text |
| sidebar footer text | #5C544A | small text on bg (passes contrast) |

## Type

- Headings: Fraunces (600), slight negative letter spacing.
- Body and controls: Instrument Sans (400, 500, 600).
- Numbers, money, IDs, dates, excerpts: IBM Plex Mono.
- All from Google Fonts.

## Logo

Lowercase wordmark "maya." in Fraunces 600 with the full stop in the accent colour. No icon. Browser tab:
the accent full stop or a lowercase "m".

## Layout

- Left sidebar: wordmark, page links (Agent activity, Review queue, Employee impact, Review history,
  Export, and Sources once that stretch page is built), footer line "Synthetic, illustrative data. AI reads and judges; code checks and
  calculates; a person decides anything unclear."
- Top bar on the queue: policy pair, as-of date toggle (2026-11-02 / 2027-01-01), approval mode
  (Pre-approve by default; the Auto-approve option is stretch), Export CSVs.
- Summary cards: changes found, need a decision, ready to approve, weekly increase in effect, weekly
  increase coming.
- Filters row: jurisdiction, change category, review status, timing, clear filters, note "Filters also
  apply to both exports."
- Queue and detail: grouped list (Needs review / Current / Future) with the finding detail beside or
  below it: headline, status chips, recommended action, owner, why it was routed, flags box ("Held for
  review: not guessed"), evidence from the source (old in critical-bg with the old value struck through,
  new in good-bg with the new value highlighted, file and section cited, date line quoted), extracted
  facts table, who is affected with written math, reviewer decision form, this finding's history.
- Agent page: status badge, goal, tool chips, guardrails line, live log with tags PLAN, TOOL, AI, CHECK,
  RESULT, each tag its own colour and word, and the manual upload of an old and a new file. The mode switch
  (Automatic / Step by step) is stretch.

## Copy rules (decided after a trial build)

- Never show the internal rule name ("rule A1"), section signs or middle dots as separators. Automatic
  decisions read "Auto-approved". Use words: "Section 1.1", "wages".
- No em dashes, no emojis.
- A missing or unclear date reads "Unclear date" or "No effective date found in section 2.2".
- Filters have explicit placeholders and a "Clear filters" button; radio options must be readable
  (contrast 4.5:1); no raw link buttons.
- Escape dollar signs in every displayed string so they do not render as math.
- No "Page not found" pop-ups: use `st.navigation` and one page module per sidebar item.

## Streamlit notes

- Put the palette and fonts in `.streamlit/config.toml` theme settings where the installed Streamlit
  version supports them; inject the rest with one CSS block in `maya/ui/style.py`. Check the installed
  version's theming options first instead of guessing.
- Keep custom CSS small and in one place. No emojis in the UI. No em dashes in any copy.
