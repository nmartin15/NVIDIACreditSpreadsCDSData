"""Reported bank efforts to pass on AI-infrastructure credit risk."""

from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from panels.common import ROOT, pretty_date


def render(recording: bool) -> None:
    del recording
    st.subheader("The AI trade, in the loan market")
    st.write(
        "NVIDIA's customers are borrowing to build the data centers that run its chips. "
        "These are the newest reports of banks selling or insuring that debt. "
        "When lenders want off the loans, the open question is whether the cost lands on NVIDIA's own protection, which is the tape above."
    )
    rows = pd.read_csv(ROOT / "data" / "bank_derisking.csv")
    show = rows.copy()
    show["_sort"] = pd.to_datetime(show["date"], errors="coerce")
    show = show.sort_values("_sort", ascending=False, na_position="last").drop(columns="_sort")

    def _when(value: object) -> str:
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return "—"
        text = str(value).strip()
        if not text or text.lower() == "nan":
            return "—"
        try:
            return pretty_date(date.fromisoformat(text))
        except ValueError:
            return text

    show["Date"] = show["date"].map(_when)
    show = show.rename(
        columns={
            "bank": "Bank",
            "action": "What was reported",
            "size_usd": "Size",
            "status": "Status",
            "source": "Source",
            "url": "Article",
        }
    )
    st.dataframe(
        show[["Date", "Bank", "What was reported", "Size", "Status", "Source", "Article"]],
        column_config={"Article": st.column_config.LinkColumn("Article")},
        hide_index=True,
        use_container_width=True,
    )
    st.caption(
        "Source: the news article linked in each row. "
        "There is no market-data feed behind this table. A blank date was blank in the note that row came from."
    )
