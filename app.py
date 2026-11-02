"""Streamlit entry: logo, sidebar links and page routing (A4, A6, B5)."""
import streamlit as st

from maya.ui import (agent_activity, employee_impact, export, proposed_law, review_history, review_queue,
                     sources_page, style)

FOOTER = ("Synthetic, illustrative data. AI reads and judges; code checks and calculates; "
          "a person decides anything unclear.")


def agent_page() -> None:
    agent_activity.render(queue_page=queue_page)


PAGES = [
    ("Agent activity", "agent-activity", agent_page),
    ("Review queue", "review-queue", review_queue.render),
    ("Employee impact", "employee-impact", employee_impact.render),
    ("Proposed law", "proposed-law", proposed_law.render),
    ("Review history", "review-history", review_history.render),
    ("Export", "export", export.render),
    ("Sources", "sources", sources_page.render),
]

st.set_page_config(page_title="eDelta Maya", page_icon=style.page_icon(), layout="wide")
style.inject_css()

pages = [
    st.Page(fn, title=title, url_path=path, default=(i == 0))
    for i, (title, path, fn) in enumerate(PAGES)
]
queue_page = pages[1]

current = st.navigation(pages, position="hidden")  # the sidebar shows the logo first, then the links

with st.sidebar:
    st.markdown(style.logo_html(width=style.SIDEBAR_LOGO_WIDTH) + style.product_html(), unsafe_allow_html=True)
    for page in pages:
        st.page_link(page)
    st.markdown(f'<div class="mq-foot">{style.esc(FOOTER)}</div>', unsafe_allow_html=True)

current.run()
st.markdown(style.footer_html(), unsafe_allow_html=True)
