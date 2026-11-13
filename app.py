"""AI Credit Watch entry point. Layout only; panels are added in later steps."""

from datetime import datetime, timezone

import streamlit as st

st.set_page_config(
    page_title="AI Credit Watch",
    layout="wide",
)


def render_header() -> None:
    refreshed = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    title_col, button_col = st.columns([5, 1])
    with title_col:
        st.title("AI Credit Watch: Is credit repricing NVIDIA?")
        st.caption(f"Last refreshed {refreshed}")
    with button_col:
        st.write("")
        st.write("")
        if st.button("Refresh", type="primary", use_container_width=True):
            st.cache_data.clear()
            st.rerun()


render_header()
