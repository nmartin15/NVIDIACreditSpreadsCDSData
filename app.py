"""Is credit repricing NVIDIA because of the AI debt buildout?"""

import os
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from panels import auctions, banks, cds_tape, equities, market_spreads

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

st.set_page_config(
    page_title="Is credit repricing NVIDIA?",
    layout="wide",
)


def render_header() -> None:
    refreshed = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    st.title("Is credit repricing NVIDIA?")
    st.write(
        "The AI buildout is being funded with debt. "
        "This page asks whether that cost is showing up in NVIDIA's own protection, "
        "the insurance on its senior debt, rather than only in the companies borrowing to buy its chips."
    )
    st.caption(f"Screen loaded {refreshed}. NVIDIA only. Other names stay off until this read is clear.")


def sidebar() -> tuple[str, bool]:
    with st.sidebar:
        if st.button("Refresh", type="primary", width="stretch"):
            st.cache_data.clear()
            st.rerun()
        history = st.radio("Share-price history", ["3 months", "6 months", "1 year", "2 years"], index=1)
        recording = st.toggle("Larger type", value=False)
        if not os.getenv("FRED_API_KEY", "").strip():
            st.info("Add FRED_API_KEY to .env for the broad-market spread and the bond comparison.")
    return history, recording


history, recording = sidebar()
render_header()
cds_tape.render_spread(recording)
st.divider()
market_spreads.render(history, recording)
st.divider()
cds_tape.render_blotter(recording)
st.divider()
banks.render(recording)
st.divider()
equities.render(history, recording)
st.divider()
auctions.render(recording)
