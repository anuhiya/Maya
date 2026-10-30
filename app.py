"""Streamlit entry: sidebar wordmark and page routing (A4, B5)."""
import streamlit as st

PAGES = [
    ("Agent activity", "agent-activity"),
    ("Review queue", "review-queue"),
    ("Employee impact", "employee-impact"),
    ("Review history", "review-history"),
    ("Export", "export"),
]


def placeholder(title: str):
    """Build a page function that says the page is not built yet."""
    def render() -> None:
        st.title(title)
        st.write("Not built yet")
    return render


st.set_page_config(page_title="maya.", page_icon=":material/circle:", layout="wide")

pages = [
    st.Page(placeholder(title), title=title, url_path=path, default=(i == 0))
    for i, (title, path) in enumerate(PAGES)
]

with st.sidebar:
    st.markdown(
        '<span style="font-family:Fraunces,serif;font-weight:600;font-size:2rem;'
        'letter-spacing:-0.02em">maya<span style="color:#B5472A">.</span></span>',
        unsafe_allow_html=True,
    )

st.navigation(pages).run()
