"""Shared loading for the Employee impact, Review history and Export pages (B5).

Uses the Review queue's pair, as-of date and filters from st.session_state, so every page agrees.
"""
from dataclasses import dataclass

import streamlit as st

from maya.ai.llm import LLMError, MissingSettingError
from maya.ai.replay import ReplayError
from maya.employees import load_employees
from maya.ingest import ReadingError
from maya.timing import parse_date
from maya.ui import review_queue as rq
from maya.ui.style import chip, esc, md


@dataclass
class View:
    comparison: rq.Comparison
    as_of: object
    items: list
    shown: list
    problems: int


def active_filters() -> dict:
    return {k: st.session_state.get(k, ph) for k, (_, ph) in rq.FILTERS.items()}


def build_view(cfg: dict, conn) -> View:
    """Compare the selected pair and apply the shared filters. Raises the reading errors."""
    rq.keep_context()
    pairs = rq.policy_pairs(cfg)
    if not pairs:
        raise ReadingError("No policy pairs found. Check the policies and site sections of maya.config.yaml.")
    pair = st.session_state.get("pair")
    pair = pair if pair in pairs else pairs[0]
    as_of = st.session_state.get("as_of") or parse_date(str(cfg["as_of_date"]))
    comparison = rq._cached_compare(cfg, pair, rq._stamp(cfg, pair))
    loaded = load_employees(cfg=cfg)
    items = rq.build_items(cfg, comparison, as_of, loaded.employees, conn)
    return View(comparison, as_of, items, rq.apply_filters(items, active_filters()), len(loaded.problems))


def load_view(cfg: dict, conn) -> View | None:
    """build_view with the page's red error states; None when nothing can be shown."""
    try:
        view = build_view(cfg, conn)
    except ReadingError as err:
        st.error(md(f"Could not read the selected policy files: {err}"))
        return None
    except (MissingSettingError, ReplayError, LLMError) as err:
        st.error(md(str(err)))
        return None
    if view.problems:
        st.warning(f"{view.problems} employee data problems found; see the employee file checks.")
    return view


def filter_chips(as_of) -> None:
    """Show the active filters and the as-of date as chips (read only)."""
    chosen = {k: v for k, v in active_filters().items() if v != rq.FILTERS[k][1]}
    chips = [chip(f"As of {as_of.isoformat()}", "mono")]
    chips += [chip(f"{rq.FILTERS[k][0]}: {v}", "accent") for k, v in chosen.items()]
    if not chosen:
        chips.append(chip("No filters, all findings"))
    st.markdown("".join(chips), unsafe_allow_html=True)
    st.caption("Change the filters on the Review queue. They apply to this page and both exports.")


def no_match() -> None:
    st.info("No findings match these filters. Use Clear filters on the Review queue to see all.")


def title(kicker: str, text: str) -> None:
    st.markdown(f'<div class="mq-kicker">{esc(kicker)}</div><div class="mq-title">{esc(text)}</div>',
                unsafe_allow_html=True)
