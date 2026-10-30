"""Theme CSS that config.toml cannot express (P2)."""
import html

import streamlit as st

BG, SURFACE, INK, MUTED, LINE, ACCENT = "#F3EEE6", "#FFFCF7", "#23201C", "#6B6259", "#E5DCCD", "#B5472A"

CSS = """
<style>
.mq-kicker { color: #6B6259; font-size: 0.8rem; margin-bottom: 0.1rem; }
.mq-title { font-family: Fraunces, serif; font-weight: 600; font-size: 1.6rem; letter-spacing: -0.02em; margin: 0 0 0.6rem 0; }
.mq-cards { display: grid; grid-template-columns: repeat(5, 1fr); gap: 0.6rem; margin: 0.5rem 0 1rem 0; }
.mq-card { background: #FFFCF7; border: 1px solid #E5DCCD; border-radius: 12px; padding: 0.8rem 0.9rem; }
.mq-card .label { color: #6B6259; font-size: 0.78rem; }
.mq-card .value { font-family: Fraunces, serif; font-weight: 600; font-size: 1.7rem; letter-spacing: -0.02em; line-height: 1.2; }
.mq-card .value.review { color: #8A5A0F; }
.mq-card .sub { color: #6B6259; font-size: 0.76rem; }
.mq-group { font-family: Fraunces, serif; font-weight: 600; font-size: 1.05rem; margin: 0.9rem 0 0.2rem 0; }
.mq-meta { color: #6B6259; font-size: 0.78rem; margin: -0.3rem 0 0.7rem 0.2rem; line-height: 1.5; }
.mq-meta .why { color: #8A5A0F; }
.mq-meta .ok { color: #3D6640; }
.mq-chip { display: inline-block; font-size: 0.74rem; font-weight: 500; border-radius: 999px; padding: 0.05rem 0.6rem; margin: 0 0.3rem 0.2rem 0; background: #E5DCCD; color: #23201C; }
.mq-chip.mono { font-family: "IBM Plex Mono", monospace; }
.mq-chip.good { background: #E4EEDF; color: #3D6640; }
.mq-chip.review { background: #F6E7C4; color: #8A5A0F; }
.mq-chip.future { background: #DDE6F0; color: #34557A; }
.mq-chip.critical { background: #F5DCD6; color: #A23A2C; }
.mq-chip.accent { background: #F5DCD6; color: #B5472A; }
.mq-ref { color: #6B6259; font-size: 0.8rem; }
.mq-head { font-family: Fraunces, serif; font-weight: 600; font-size: 1.5rem; letter-spacing: -0.02em; line-height: 1.3; margin: 0.2rem 0 0.6rem 0; }
.mq-box { background: #FFFCF7; border: 1px solid #E5DCCD; border-radius: 10px; padding: 0.6rem 0.8rem; margin-bottom: 0.6rem; font-size: 0.9rem; }
.mq-box .label { color: #6B6259; font-size: 0.72rem; font-weight: 600; letter-spacing: 0.04em; text-transform: uppercase; margin-bottom: 0.15rem; }
.mq-box.held { background: #F6E7C4; border-color: #8A5A0F; color: #23201C; }
.mq-sub { font-family: Fraunces, serif; font-weight: 600; font-size: 1.05rem; margin: 1rem 0 0.4rem 0; }
.mq-exc { border-radius: 10px; padding: 0.6rem 0.8rem; margin-bottom: 0.5rem; font-family: "IBM Plex Mono", monospace; font-size: 0.82rem; white-space: pre-wrap; line-height: 1.55; }
.mq-exc .src { color: #6B6259; font-size: 0.74rem; margin-bottom: 0.3rem; }
.mq-exc.old { background: #F5DCD6; }
.mq-exc.new { background: #E4EEDF; }
.mq-exc del { text-decoration: line-through; background: transparent; color: #A23A2C; font-weight: 600; }
.mq-exc mark { background: #BFD8B8; color: #23201C; padding: 0 0.15rem; border-radius: 3px; font-weight: 600; }
.mq-table { width: 100%; border-collapse: collapse; font-size: 0.86rem; background: #FFFCF7; border: 1px solid #E5DCCD; }
.mq-table th { text-align: left; color: #6B6259; font-weight: 600; padding: 0.4rem 0.6rem; border-bottom: 1px solid #E5DCCD; }
.mq-table td { padding: 0.4rem 0.6rem; border-bottom: 1px solid #E5DCCD; vertical-align: top; }
.mq-table td.mono { font-family: "IBM Plex Mono", monospace; }
[class*="st-key-row_"], [class*="st-key-rowsel_"] { border-bottom: 1px solid #E5DCCD; padding: 0.4rem 0.6rem 0.2rem 0.6rem; gap: 0; }
[class*="st-key-rowsel_"] { background: #F6E4DC; border-left: 3px solid #B5472A; }
[class*="st-key-pick_"] button { justify-content: flex-start; text-align: left; padding: 0; min-height: 0; font-weight: 600; }
[class*="st-key-pick_"] button p { text-align: left; }
.mq-when { text-align: right; font-family: "IBM Plex Mono", monospace; font-size: 0.78rem; color: #6B6259; }
.st-key-signoff button, .st-key-clear_filters button, .st-key-confirm_yes button, .st-key-publish button { white-space: nowrap; }
.mq-scroll { overflow-x: auto; }
.mq-table td, .mq-table th { overflow-wrap: anywhere; }
.mq-hist { font-size: 0.86rem; border-left: 3px solid #E5DCCD; padding: 0.1rem 0 0.1rem 0.7rem; margin-bottom: 0.5rem; }
.mq-hist .when { font-family: "IBM Plex Mono", monospace; color: #6B6259; font-size: 0.76rem; }
.mq-foot { color: #5C544A; font-size: 0.75rem; line-height: 1.4; }
.mq-log { background: #FFFCF7; border: 1px solid #E5DCCD; border-radius: 12px; padding: 0.4rem 0.8rem; max-height: 30rem; overflow-y: auto; }
.mq-line { display: grid; grid-template-columns: 4.4rem 4.6rem 1fr; gap: 0.6rem; align-items: baseline; padding: 0.3rem 0; border-bottom: 1px solid #E5DCCD; font-size: 0.86rem; }
.mq-line:last-child { border-bottom: 0; }
.mq-line .at { font-family: "IBM Plex Mono", monospace; color: #6B6259; font-size: 0.76rem; }
.mq-line .txt { overflow-wrap: anywhere; }
.mq-line .txt.mono { font-family: "IBM Plex Mono", monospace; font-size: 0.8rem; }
.mq-line .rp { display: block; color: #6B6259; font-size: 0.72rem; }
.mq-tag { display: inline-block; text-align: center; font-weight: 600; font-size: 0.72rem; letter-spacing: 0.04em; border-radius: 6px; padding: 0.05rem 0.45rem; }
.mq-tag.plan { background: #DDE6F0; color: #34557A; }
.mq-tag.tool { background: #E5DCCD; color: #23201C; }
.mq-tag.ai { background: #F6E7C4; color: #8A5A0F; }
.mq-tag.pass { background: #E4EEDF; color: #3D6640; }
.mq-tag.fail { background: #F5DCD6; color: #A23A2C; }
.mq-tag.result { background: #B5472A; color: #FFFFFF; }
.mq-item { font-size: 0.88rem; margin-bottom: 0.3rem; overflow-wrap: anywhere; }
.mq-item .when { font-family: "IBM Plex Mono", monospace; color: #6B6259; font-size: 0.76rem; }
.mq-item a { color: #34557A; }
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
    return ('<span style="font-family:Fraunces,serif;font-weight:600;font-size:2rem;'
            f'letter-spacing:-0.02em">maya<span style="color:{ACCENT}">.</span></span>')
