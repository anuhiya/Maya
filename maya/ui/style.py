"""Theme CSS that config.toml cannot express, and the eDelta logo (P2, A6)."""
import base64
import html
from functools import lru_cache
from pathlib import Path

import streamlit as st

from maya import state

ASSETS = Path(__file__).resolve().parents[2] / "assets"
LOGO, ICON = ASSETS / "edelta-logo.png", ASSETS / "edelta-icon.png"
BG, SURFACE, INK, MUTED, LINE, ACCENT = "#07081F", "#0B0D33", "#F3F5F9", "#9AA3C7", "#151A52", "#66B3FF"
DEEP_BLUE, DEEPER_BLUE, ACCENT_TEXT = "#0F1E80", "#001174", "#07081F"
GOOD, WARN, BAD = "#4ADE9A", "#F5B94A", "#FF6B6B"
FOOTER_TEXT = ("eDelta Maya. Prototype built for eDelta Consulting. Synthetic, illustrative data. "
               "Place names are real; wage rates, rules and dates are illustrative, not the actual law.")
SIDEBAR_LOGO_WIDTH, PRODUCT_NAME = 120, "Maya"

CSS = """
<style>
@import url("https://fonts.googleapis.com/css2?family=Asta+Sans:wght@400;500;600&display=swap");
@import url("https://fonts.googleapis.com/css2?family=Montserrat:wght@600;700&display=swap");
[data-testid="stMainBlockContainer"] { padding-top: 1.5rem; }
[data-testid="stHeader"] { background: transparent; height: 0; min-height: 0; }
[data-testid="stSidebarHeader"] { height: 1.5rem; min-height: 0; padding: 0.4rem 0.8rem 0 0.8rem; margin: 0; }
[data-testid="stSidebar"] { border-right: 1px solid rgba(102,179,255,0.20); }
[data-testid^="stBaseButton-"], [data-testid="stDownloadButton"] button { border-radius: 72px; font-weight: 600; }
[data-testid="stBaseButton-primary"] { background: #66B3FF; color: #07081F; border: 1px solid #66B3FF; }
[data-testid="stBaseButton-primary"] p { color: #07081F; background: transparent; }
[data-testid="stBaseButton-primary"]:disabled { background: #151A52; border-color: rgba(102,179,255,0.20); }
[data-testid="stBaseButton-primary"]:disabled p { color: #9AA3C7; }
[data-testid="stBaseButton-secondary"] { background: transparent; color: #66B3FF; border: 1px solid #66B3FF; }
[data-testid="stBaseButton-secondary"] p { color: #66B3FF; }
[data-testid="stBaseButton-secondary"]:disabled, [data-testid="stBaseButton-secondary"]:disabled p { color: #9AA3C7; border-color: rgba(102,179,255,0.20); }
[data-testid^="stBaseButton"] { user-select: none; }
[data-testid="stFormSubmitButton"] button { white-space: nowrap; padding-left: 1rem; padding-right: 1rem; }
[class*="st-key-row_"], [class*="st-key-rowsel_"] { text-align: left; }
[class*="st-key-row_"] .mq-meta, [class*="st-key-rowsel_"] .mq-meta { text-align: left; margin-left: 0; }
[class*="st-key-row_"] [data-testid="stMarkdownContainer"], [class*="st-key-rowsel_"] [data-testid="stMarkdownContainer"] { text-align: left; }
[class*="st-key-preset_row"] button { min-height: 1.8rem; padding: 0.1rem 0.8rem; }
[class*="st-key-preset_row"] button p { font-size: 0.76rem; white-space: nowrap; }
[class*="st-key-ribbon_ready"], [class*="st-key-ribbon_decision"], [class*="st-key-ribbon_wording"], [class*="st-key-ribbon_open"] { width: auto !important; flex: 0 0 auto !important; }
[class*="st-key-ribbon_row"] { gap: 0.4rem; flex-wrap: wrap; }
[class*="st-key-ribbon_row"] > * { flex: 0 0 auto !important; width: auto !important; }
[class*="st-key-publish_card"] [data-baseweb="select"] > div { font-size: 0.8rem; padding-left: 0.3rem; }
[class*="st-key-ribbon_"] button { min-width: 2.2rem; min-height: 2.2rem; padding: 0; border-radius: 999px; font-family: "IBM Plex Mono", monospace; font-weight: 600; }
[class*="st-key-ribbon_ready"] button { background: #0B2E24; border-color: #4ADE9A; color: #4ADE9A; }
[class*="st-key-ribbon_ready"] button p { color: #4ADE9A; }
[class*="st-key-ribbon_decision"] button { background: #33260A; border-color: #F5B94A; color: #F5B94A; }
[class*="st-key-ribbon_decision"] button p { color: #F5B94A; }
[class*="st-key-ribbon_wording"] button { background: #151A52; border-color: #9AA3C7; color: #C9CFE8; }
[class*="st-key-ribbon_wording"] button p { color: #C9CFE8; }
[class*="st-key-ribbon_"][class*="_sel_"] button { box-shadow: 0 0 0 2px #F3F5F9; }
.mq-pagefoot { color: #9AA3C7; font-size: 0.75rem; text-align: center; margin: 2.5rem 0 0.5rem 0; padding-top: 0.8rem; border-top: 1px solid rgba(102,179,255,0.20); }
[data-testid="stSidebarUserContent"] { padding-top: 0.2rem; }
.mq-logo { display: block; margin: 0 0 0.2rem 0; }
.mq-product { font-family: Montserrat, sans-serif; font-weight: 600; font-size: 0.8rem; letter-spacing: 0.02em; color: #66B3FF; margin: 0 0 0.8rem 0; }
.mq-kicker { color: #9AA3C7; font-size: 0.72rem; font-weight: 600; letter-spacing: 0.1em; text-transform: uppercase; margin-bottom: 0.1rem; }
.mq-kicker::before { content: "\\203A"; color: #66B3FF; font-weight: 700; margin-right: 0.45rem; }
.mq-title { font-family: Montserrat, sans-serif; font-weight: 600; font-size: 1.6rem; letter-spacing: -0.01em; margin: 0 0 0.6rem 0; }
.mq-cards { display: grid; grid-template-columns: repeat(4, 1fr); gap: 0.6rem; margin: 0.5rem 0 1rem 0; }
.mq-cards.three { grid-template-columns: repeat(3, 1fr); }
.mq-card { background: #0B0D33; border: 1px solid rgba(102,179,255,0.20); border-radius: 16px; padding: 0.8rem 0.9rem; }
.mq-card .label { color: #9AA3C7; font-size: 0.78rem; }
.mq-card .value { font-family: Montserrat, sans-serif; font-weight: 600; font-size: 1.7rem; letter-spacing: -0.01em; line-height: 1.2; }
.mq-card .value.review { color: #F5B94A; }
.mq-card .sub { color: #9AA3C7; font-size: 0.76rem; }
.mq-group { font-family: Montserrat, sans-serif; font-weight: 600; font-size: 1.05rem; margin: 0.9rem 0 0.2rem 0; }
.mq-meta { color: #9AA3C7; font-size: 0.78rem; margin: -0.3rem 0 0.7rem 0.2rem; line-height: 1.5; }
.mq-meta .why { color: #F5B94A; }
.mq-meta .ok { color: #4ADE9A; }
.mq-chip { display: inline-block; font-size: 0.74rem; font-weight: 500; border-radius: 999px; padding: 0.05rem 0.6rem; margin: 0 0.3rem 0.2rem 0; background: #151A52; color: #F3F5F9; }
.mq-chip.mono { font-family: "IBM Plex Mono", monospace; }
.mq-chip.good { background: #0B2E24; color: #4ADE9A; }
.mq-chip.review { background: #33260A; color: #F5B94A; }
.mq-chip.future { background: #0F1E80; color: #66B3FF; }
.mq-chip.critical { background: #3A1218; color: #FF6B6B; }
.mq-chip.accent { background: #0F1E80; color: #66B3FF; }
.mq-kv { display: grid; grid-template-columns: 160px 1fr; gap: 0.35rem 1rem; font-size: 0.88rem; margin: 0.4rem 0 0.8rem 0; }
.mq-kv .k { color: #9AA3C7; font-size: 0.72rem; font-weight: 600; letter-spacing: 0.05em; text-transform: uppercase; white-space: nowrap; align-self: center; }
.mq-kv .v { font-family: "IBM Plex Mono", monospace; overflow-wrap: normal; }
.mq-bignum { font-family: Montserrat, sans-serif; font-weight: 700; font-size: 2rem; letter-spacing: -0.01em; line-height: 1.2; }
.mq-bignum span { font-size: 0.9rem; font-weight: 600; color: #9AA3C7; }
.mono { font-family: "IBM Plex Mono", monospace; }
.mq-ref { color: #9AA3C7; font-size: 0.8rem; }
.mq-head { font-family: Montserrat, sans-serif; font-weight: 600; font-size: 1.5rem; letter-spacing: -0.01em; line-height: 1.3; margin: 0.2rem 0 0.6rem 0; }
.mq-box { background: #0B0D33; border: 1px solid rgba(102,179,255,0.20); border-radius: 16px; padding: 0.6rem 0.8rem; margin-bottom: 0.6rem; font-size: 0.9rem; }
.mq-box .label { color: #9AA3C7; font-size: 0.72rem; font-weight: 600; letter-spacing: 0.04em; text-transform: uppercase; margin-bottom: 0.15rem; }
.mq-box.held { background: #33260A; border-color: #F5B94A; color: #F3F5F9; }
.mq-sub { font-family: Montserrat, sans-serif; font-weight: 600; font-size: 1.05rem; margin: 1rem 0 0.4rem 0; }
.mq-exc { border-radius: 16px; padding: 0.6rem 0.8rem; margin-bottom: 0.5rem; font-family: "IBM Plex Mono", monospace; font-size: 0.82rem; white-space: pre-wrap; line-height: 1.55; }
.mq-exc .src { color: #9AA3C7; font-size: 0.74rem; margin-bottom: 0.3rem; }
.mq-exc.old { background: #3A1218; }
.mq-exc.new { background: #0B2E24; }
.mq-exc del { text-decoration: line-through; background: transparent; color: #FF6B6B; font-weight: 600; }
.mq-exc mark { background: #1F6B49; color: #FFFFFF; padding: 0 0.15rem; border-radius: 3px; font-weight: 600; }
.mq-table { width: 100%; border-collapse: collapse; font-size: 0.86rem; background: #0B0D33; border: 1px solid rgba(102,179,255,0.20); }
.mq-table th { text-align: left; color: #9AA3C7; font-weight: 600; font-size: 0.72rem; letter-spacing: 0.05em; text-transform: uppercase; padding: 0.4rem 0.6rem; border-bottom: 1px solid rgba(102,179,255,0.20); }
.mq-table td { padding: 0.4rem 0.6rem; border-bottom: 1px solid rgba(102,179,255,0.20); vertical-align: top; }
.mq-table.kv td:first-child, .mq-table.kv th:first-child { width: 160px; min-width: 160px; max-width: 160px; white-space: nowrap; color: #9AA3C7; }
.mq-table td.mono { font-family: "IBM Plex Mono", monospace; }
[class*="st-key-row_"], [class*="st-key-rowsel_"] { border-bottom: 1px solid rgba(102,179,255,0.20); padding: 0.4rem 0.6rem 0.2rem 0.6rem; gap: 0; }
[class*="st-key-rowsel_"] { background: #0F1E80; border-left: 3px solid #66B3FF; }
[class*="st-key-pick_"] button { justify-content: flex-start; text-align: left; padding: 0; min-height: 0; font-weight: 600; }
[class*="st-key-pick_"] button, [class*="st-key-pick_"] button > div { justify-content: flex-start !important; }
[class*="st-key-pick_"] [data-testid="stMarkdownContainer"] { width: 100%; }
[class*="st-key-pick_"] button p { text-align: left !important; width: 100%; }
.mq-when { text-align: right; font-family: "IBM Plex Mono", monospace; font-size: 0.78rem; color: #9AA3C7; }
.st-key-signoff button, .st-key-clear_filters button, .st-key-confirm_yes button, .st-key-publish button { white-space: nowrap; }
.mq-scroll { overflow-x: auto; }
.mq-table td.nw, .mq-table th.nw, .mq-table td:first-child, .mq-table th:first-child, .mq-table td.mono:not(.wrap) { white-space: nowrap; }
.mq-table td.wrap, .mq-table th.wrap { min-width: 16rem; }
.mq-table td.calc, .mq-table th.calc { min-width: 26rem; white-space: normal; overflow-wrap: normal; word-break: normal; }
.mq-table td, .mq-table th { overflow-wrap: normal; word-break: normal; }
.mq-hist { font-size: 0.86rem; border-left: 3px solid rgba(102,179,255,0.20); padding: 0.1rem 0 0.1rem 0.7rem; margin-bottom: 0.5rem; }
.mq-hist .when { font-family: "IBM Plex Mono", monospace; color: #9AA3C7; font-size: 0.76rem; }
.mq-foot { color: #9AA3C7; font-size: 0.75rem; line-height: 1.4; }
.mq-log { background: #0B0D33; border: 1px solid rgba(102,179,255,0.20); border-radius: 16px; padding: 0.4rem 0.8rem; max-height: 30rem; overflow-y: auto; }
.mq-line { display: grid; grid-template-columns: 4.4rem 4.6rem 1fr; gap: 0.6rem; align-items: baseline; padding: 0.3rem 0; border-bottom: 1px solid rgba(102,179,255,0.20); font-size: 0.86rem; }
.mq-line:last-child { border-bottom: 0; }
.mq-line .at { font-family: "IBM Plex Mono", monospace; color: #9AA3C7; font-size: 0.76rem; }
.mq-line .txt { overflow-wrap: anywhere; }
.mq-line .txt.mono { font-family: "IBM Plex Mono", monospace; font-size: 0.8rem; }
.mq-line .rp { display: block; color: #9AA3C7; font-size: 0.72rem; }
.mq-tag { display: inline-block; text-align: center; font-weight: 600; font-size: 0.72rem; letter-spacing: 0.04em; border-radius: 6px; padding: 0.05rem 0.45rem; }
.mq-tag.plan { background: #0F1E80; color: #66B3FF; }
.mq-tag.tool { background: #151A52; color: #F3F5F9; }
.mq-tag.ai { background: #33260A; color: #F5B94A; }
.mq-tag.pass { background: #0B2E24; color: #4ADE9A; }
.mq-tag.fail { background: #3A1218; color: #FF6B6B; }
.mq-tag.result { background: #66B3FF; color: #07081F; }
.mq-item { font-size: 0.88rem; margin-bottom: 0.3rem; overflow-wrap: anywhere; }
.mq-item .when { font-family: "IBM Plex Mono", monospace; color: #9AA3C7; font-size: 0.76rem; }
.mq-item a { color: #66B3FF; }
@property --d { syntax: "<integer>"; initial-value: 0; inherits: false; }
@property --t { syntax: "<integer>"; initial-value: 0; inherits: false; }
@property --o { syntax: "<integer>"; initial-value: 0; inherits: false; }
.mq-strip { background: #0F1E80; color: #F3F5F9; border-radius: 16px; padding: 0.55rem 0.9rem; font-size: 0.86rem; margin-bottom: 0.8rem; }
.mq-live { margin-bottom: 0.7rem; }
.mq-now { display: flex; justify-content: space-between; align-items: center; gap: 0.8rem; font-size: 0.92rem; }
.mq-dot { display: inline-block; width: 0.7rem; height: 0.7rem; border-radius: 999px; background: #66B3FF; margin-right: 0.5rem; }
.mq-dot.idle { background: #9AA3C7; }
.mq-dot.pulse { animation: mq-pulse 1.6s ease-in-out infinite; }
.mq-spin { display: inline-block; width: 0.7rem; height: 0.7rem; border: 2px solid #9AA3C7; border-top-color: transparent; border-radius: 999px; margin-right: 0.35rem; vertical-align: -1px; animation: mq-turn 1s linear infinite; }
.mq-scan { position: relative; overflow: hidden; }
.mq-scan::after { content: ""; position: absolute; left: 0; right: 0; top: 0; height: 2.2rem; background: linear-gradient(180deg, transparent, rgba(102,179,255,0.16), transparent); animation: mq-sweep 3.2s ease-in-out infinite; pointer-events: none; }
.mq-fade { animation: mq-in 0.9s ease-out; }
.mq-count { counter-reset: d var(--d) t var(--t) o var(--o); animation: mq-up 1.4s ease-out; }
.mq-count::before { content: "$" counter(d) "." counter(t) counter(o); }
.mq-lanes { display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.5rem; margin-bottom: 0.4rem; }
.mq-lane { border: 1px dashed rgba(102,179,255,0.20); border-radius: 12px; padding: 0.5rem; font-size: 0.82rem; min-height: 4rem; }
.mq-lane.on { border: 1px solid #66B3FF; background: #0F1E80; }
.mq-landed { margin-top: 0.4rem; font-family: "IBM Plex Mono", monospace; font-size: 0.78rem; animation: mq-in 0.9s ease-out; }
.mq-split { display: flex; height: 0.7rem; border-radius: 999px; overflow: hidden; background: #151A52; margin-bottom: 0.4rem; }
.mq-seg.ai { background: #F5B94A; }
.mq-seg.code { background: #66B3FF; }
.mq-seg.person { background: #4ADE9A; }
.mq-pipe { display: flex; flex-wrap: wrap; gap: 0.3rem; }
.mq-state { font-size: 0.72rem; color: #9AA3C7; text-align: center; margin-top: -0.3rem; }
.mq-state.done { color: #4ADE9A; }
.mq-state.failed { color: #FF6B6B; }
.mq-state.running { color: #66B3FF; }
[class*="st-key-node_"] button { border-radius: 14px; min-height: 3rem; padding: 0.2rem 0.3rem; }
[class*="st-key-node_"] button p { font-size: 0.74rem; overflow-wrap: normal; word-break: normal; hyphens: none; }
[class*="st-key-node_"][class*="_done"] button { border-color: #4ADE9A; }
[class*="st-key-node_"][class*="_failed"] button { border-color: #FF6B6B; }
[class*="st-key-node_"][class*="_running"] button { border-color: #66B3FF; animation: mq-pulse 1.6s ease-in-out infinite; }
[class*="st-key-node_"][class*="_sel"] button { background: #0F1E80; }
@keyframes mq-pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.45; } }
@keyframes mq-turn { to { transform: rotate(360deg); } }
@keyframes mq-sweep { 0% { top: -2.2rem; } 100% { top: 100%; } }
@keyframes mq-in { from { opacity: 0; transform: translateY(4px); } }
@keyframes mq-up { from { --d: 0; --t: 0; --o: 0; } }
@media (prefers-reduced-motion: reduce) { .mq-dot.pulse, .mq-spin, .mq-scan::after, .mq-fade, .mq-count, .mq-landed, [class*="st-key-node_"] button { animation: none !important; } }
@media (max-width: 900px) { .mq-cards { grid-template-columns: repeat(2, 1fr); } }
</style>
"""


def inject_css() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def esc(text) -> str:
    """HTML-escape a displayed string and keep dollar signs from rendering as math."""
    return html.escape(str(text)).replace("$", "&#36;")


def md(text) -> str:
    """Escape dollar signs in a plain markdown string (st.error, st.caption)."""
    return str(text).replace("$", "\\$")


def chip(text: str, kind: str = "") -> str:
    return f'<span class="mq-chip {kind}">{esc(text)}</span>'


def wordmark() -> str:
    """Text fallback when the logo file is missing: eDelta with Delta in the accent colour."""
    return ('<span style="font-family:Montserrat,sans-serif;font-weight:600;font-size:2rem;'
            f'letter-spacing:-0.01em">e<span style="color:{ACCENT}">Delta</span></span>')


@lru_cache(maxsize=4)
def _data_uri(path: str) -> str:
    return "data:image/png;base64," + base64.b64encode(Path(path).read_bytes()).decode("ascii")


def logo_html(width: int | None = None, height: int | None = None, path=None) -> str:
    """The logo as it is (no recolouring, cropping or redrawing), sized by one side so the ratio holds.
    It goes straight on the page background. Without the file it falls back to the text wordmark."""
    try:
        uri = _data_uri(str(path or LOGO))
    except OSError:
        return wordmark()
    size = f"width:{width}px;height:auto" if width else f"height:{height}px;width:auto"
    return f'<img class="mq-logo" src="{uri}" alt="eDelta" style="{size}">'


def product_html() -> str:
    """The product name under the sidebar logo, so the sidebar reads as eDelta Maya."""
    return f'<div class="mq-product">{html.escape(PRODUCT_NAME)}</div>'


def footer_html() -> str:
    """The footer shown at the bottom of every page."""
    return f'<div class="mq-pagefoot">{html.escape(FOOTER_TEXT)}</div>'


def page_icon() -> str:
    """The browser tab icon: the circular e mark, or a plain Streamlit icon when its file is missing."""
    return str(ICON) if ICON.is_file() else ":material/circle:"


def empty_page(cfg: dict, kicker: str, title: str) -> bool:
    """The clean empty state of a findings page: its header, one line and a pointer. True when it was shown."""
    if not state.is_empty(cfg):
        return False
    st.markdown(f'<div class="mq-kicker">{esc(kicker)}</div><div class="mq-title">{esc(title)}</div>',
                unsafe_allow_html=True)
    st.info(state.EMPTY_LINE)
    return True
