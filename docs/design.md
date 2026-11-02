# eDelta: design (P2, changed by A6)

The app was called Maya during early development and is now eDelta (A6).

Visual reference: the eDelta canvas (claude.ai artifact, pages Agent, Review queue, Employee impact,
Review history, Export, Sources). Take screenshots of it and drop them into Claude Code when building
each page. This file is the part Claude Code must follow exactly.

## Why it looks like this

- First impressions form in 17 to 50 ms, and simple, familiar layouts score highest (Google research).
- About 80% of eye fixations land on the left half of a screen (Nielsen Norman Group), so navigation and
  the queue sit on the left and the decision sits where the eye ends.
- People judge good-looking tools as easier to use (aesthetic-usability effect, Kurosu and Kashimura).
- Contrast meets WCAG: 4.5:1 for text, 3:1 for controls. Colour is never the only signal: every status
  also has a word.

## Palette: Dark navy (A6, tokens of Nov 1 evening)

| Token | Hex | Use |
| --- | --- | --- |
| bg | #07081F | page and sidebar background; the logo sits directly on it |
| panel | #0B0D33 | cards, panels, tables, with a 1px border rgba(102,179,255,0.20) |
| ink | #F3F5F9 | main text |
| muted | #9AA3C7 | secondary text, table headers, footers |
| accent | #66B3FF | links, selected item, primary button fill (dark text #07081F), outlined secondary buttons |
| deep blue | #0F1E80, #001174 | selected rows, future-dated chips, gradients |
| good | #4ADE9A on #0B2E24 | approved, passed checks, added text |
| warn | #F5B94A on #33260A | needs review, flags |
| bad | #FF6B6B on #3A1218 | errors, removed text |

Shapes: cards 16px radius, buttons pill (72px), chips fully rounded. Primary button is a blue fill with dark
text, secondary is outlined blue. Table headers are short muted capitals; label-value tables have a fixed 160px
no-wrap label column; no table breaks words mid-word. The kicker is small capitals with a blue chevron.
Every text and background pair in the CSS must reach 4.5:1 (tested in `tests/test_branding.py`).
Colour is never the only signal: Added and Removed are words in the queue and in the excerpt labels, removed
words are struck through and added words are highlighted.

## Type

- Page titles, section headings and big numbers: Montserrat (600). Body: Asta Sans. IDs, quotes and evidence: IBM Plex Mono.
  The sidebar shows the product name "Maya" under the logo. Tab title "eDelta Maya".
- Body and controls: Instrument Sans (400, 500, 600).
- Numbers, money, IDs, dates, excerpts: IBM Plex Mono.
- All from Google Fonts.

## Logo

The eDelta logo, `assets/edelta-logo.png` (an unchanged copy of `assets/image.png`, kept). It is light on dark, so
it goes straight on the page background, never on a white panel. Shown about 120px wide in the sidebar only (above the page
links), aspect ratio kept. No logo or wordmark in page headers. Never recolour, crop or redraw
it. Browser tab: `assets/edelta-icon.png`, the circular "e" mark cut from the logo without changing its pixels. If
a file is missing, the app falls back to the text "eDelta" with "Delta" in the accent colour and a plain tab icon.

## Layout

- Left sidebar: logo, page links (Agent activity, Review queue, Employee impact, Proposed law, Review history,
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

## Decision record: dark navy theme and eDelta logo (A6)

- **Context:** The first design (P2) chose Terracotta & Paper and a "maya." wordmark. The eDelta
  look was later chosen for the whole app, and the supplied logo has white lettering that cannot sit on a light page.
- **Decision (Nov 1, 2026):** The whole app uses a dark navy theme and the eDelta logo. A6 supersedes the palette and
  wordmark parts of P2; fonts, layout and copy rules stay. The SOC item (A7) was dropped and is not built.
- **Alternatives:** A navy sidebar and header only (a split look and two palettes to keep readable); keeping the light
  theme on a navy backing panel for the logo (a panel behind the logo, which the logo is not meant for).
- **Consequences:** Every colour token moved, and status colours became light text on dark tints, checked for
  4.5:1 contrast in a test. The sidebar uses hidden navigation with page links so the logo sits first.
  README and any screenshots still show the old look until they are updated.

## Decision record: palette of Nov 1 evening (A6)

- **Context:** The first navy tokens (#0A1530 and friends) were a stand-in.
- **Decision:** Pavan's tokens replace them: bg #07081F, panel #0B0D33, accent #66B3FF, status colours #4ADE9A,
  #F5B94A and #FF6B6B, fonts Montserrat, Asta Sans and IBM Plex Mono. Footer on every page: "eDelta Maya. Prototype
  built for eDelta Consulting. Synthetic, illustrative data." Tab title "eDelta Maya".
- **Alternatives:** Keeping the first tokens (rejected: they did not match the eDelta site look).
- **Consequences:** Only styling changed. Every number and calculation is untouched. The contrast test covers the new pairs.

## Decision record: real place names on synthetic data (Nov 1, 2026)

- **Context:** The three jurisdictions were fictional (Avalon, Calder, Meridian). Real places are easier to recognise.
- **Decision:** Real place names on synthetic data; The project requires fictional policy and a synthetic dataset.
  Avalon is now New York City, Calder is Los Angeles and Meridian is Chicago. Names only changed: every wage rate, rule, date and
  employee is still synthetic and illustrative. Every bulletin header, the policy site, the Sources page and the footer say so:
  "Synthetic bulletin. Place names are real; wage rates, rules and dates are illustrative, not the actual law."
- **Alternatives:** Keeping the fictional names (rejected: less recognisable); real rates and rules (rejected: the project
  requires a synthetic dataset and invented policy).
- **Consequences:** Every policy file, the employee CSV, the saved replays and the tests were rewritten with one name mapping,
  and every sha256 fingerprint and replay prompt hash was recomputed. No calculation and no frozen number changed.

## Decision record: real proposed bills, informational only (A9)

- **Context:** The Proposed law page showed one illustrative bill. The project reads real policy, but never applies it as if it were law.
- **Decision:** The page has a selector, "Real proposed bills" and "Illustrative bill". A real bill is kept in
  `data/policies/proposed/real/<bill>/` as the official file saved unaltered, a text file extracted from it with no edits, a
  `header.json` (number, title, sponsor, official URL, date retrieved, status at retrieval, trust "informational only") and a
  `facts.json` whose every fact carries a quote that code checks word for word against the saved text (V1). Only official pages
  are used (the New York City Council Legistar site and nysenate.gov). A bill that does not cover this company shows "Not applicable
  to this company, covers: ..." and no cost. The page always says: "Bill text is real; the workforce is synthetic; status may have
  changed since retrieval."
- **Alternatives:** Pricing every bill whatever its scope (rejected: it would guess); using news or tracker sites (rejected: not official).
- **Consequences:** Real-bill totals are separate and never added to the in-effect or coming totals. Facts are read once by a person and
  verified by code, not read live by the AI; the AI summary button is optional and its quotes are verified too.
