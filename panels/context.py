"""Short sourced cards that explain why NVIDIA's credit is in the story."""

from __future__ import annotations

from datetime import date

import streamlit as st

from panels.common import context_cards, pretty_date


def render(recording: bool) -> None:
    del recording
    cards = context_cards()
    if not cards:
        return
    st.subheader("Reporting behind the names, newest first")
    st.write(
        "These are background articles. The date on each card is when the event happened, "
        "which can be months before this screen was refreshed."
    )
    cards = sorted(cards, key=lambda card: str(card.get("date") or ""), reverse=True)
    columns = st.columns(len(cards))
    for column, card in zip(columns, cards):
        when = card.get("date") or ""
        try:
            when = pretty_date(date.fromisoformat(str(when)))
        except ValueError:
            when = str(when)
        with column:
            with st.container(border=True):
                st.markdown(f"**{card.get('title', '')}**")
                st.write(card.get("text", ""))
                source = card.get("source") or "Source"
                url = card.get("url") or ""
                if url:
                    st.caption(f"{when} · [{source}]({url})")
                else:
                    st.caption(f"{when} · {source}")
