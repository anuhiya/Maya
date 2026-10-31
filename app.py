"""Streamlit entry: sidebar wordmark and page routing (A4, B5)."""
import streamlit as st

from maya.ui import agent_activity, employee_impact, export, review_history, review_queue, style

FOOTER = ("Synthetic, illustrative data. AI reads and judges; code checks and calculates; "
          "a person decides anything unclear.")


def agent_page() -> None:
    agent_activity.render(queue_page=queue_page)


PAGES = [
    ("Agent activity", "agent-activity", agent_page),
    ("Review queue", "review-queue", review_queue.render),
    ("Employee impact", "employee-impact", employee_impact.render),
    ("Review history", "review-history", review_history.render),
    ("Export", "export", export.render),
]

st.set_page_config(page_title="maya.", page_icon=":material/circle:", layout="wide")
style.inject_css()

pages = [
    st.Page(fn, title=title, url_path=path, default=(i == 0))
    for i, (title, path, fn) in enumerate(PAGES)
]
queue_page = pages[1]

with st.sidebar:
    st.markdown(style.wordmark(), unsafe_allow_html=True)
    st.markdown(f'<div class="mq-foot">{style.esc(FOOTER)}</div>', unsafe_allow_html=True)

st.navigation(pages).run()
