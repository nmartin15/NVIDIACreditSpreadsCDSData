"""Broad credit spreads, in words a student can read."""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import plotly.express as px
import streamlit as st

from panels.common import apply_chart, load_spreads, load_yaml, pretty_date, unavailable, window_start
from sources import SourceUnavailable


def _shift(series: pd.DataFrame, days: int) -> float | None:
    ordered = series.dropna(subset=["value_bp"]).sort_values("date")
    if ordered.empty:
        return None
    latest_day = ordered.iloc[-1]["date"]
    prior = ordered[ordered["date"] <= latest_day - timedelta(days=days)]
    if prior.empty:
        return None
    return float(ordered.iloc[-1]["value_bp"] - prior.iloc[-1]["value_bp"])


def render(history: str, recording: bool) -> None:
    st.subheader("The yardstick: what other companies pay over Treasuries")
    st.write(
        "The chart above is what it costs to insure NVIDIA. This is the comparison that makes that number mean something: "
        "the extra yield on corporate bonds over Treasuries, for the whole market. "
        "Investment grade, BBB, and high yield. These are bond spreads, not NVIDIA's CDS, so they are a yardstick, not the same instrument."
    )
    try:
        start = window_start(history) - timedelta(days=100)
        spreads = load_spreads(start.isoformat())
        catalog = {item["label"]: item["color"] for item in load_yaml("series.yaml").get("spreads", [])}
        visible = spreads[spreads["date"] >= window_start(history)].dropna(subset=["value_bp"])
        if visible.empty:
            raise SourceUnavailable("FRED returned these series, but none had a number in the selected dates.")
        labels = list(dict.fromkeys(visible["label"]))
        columns = st.columns(len(labels))
        for column, label in zip(columns, labels):
            series = spreads[spreads["label"] == label]
            latest = series.dropna(subset=["value_bp"]).sort_values("date").iloc[-1]
            month = _shift(series, 30)
            quarter = _shift(series, 90)
            with column:
                st.metric(
                    label,
                    f"{latest['value_bp']:.0f} bp",
                    delta=None if month is None else f"{month:+.0f} bp vs a month ago",
                    delta_color="inverse",
                    help=None if quarter is None else f"{quarter:+.0f} bp versus about three months ago. As of {pretty_date(latest['date'])}.",
                )
        chart = px.line(
            visible,
            x="date",
            y="value_bp",
            color="label",
            color_discrete_map=catalog,
            labels={"date": "", "value_bp": "Extra yield, basis points", "label": ""},
        )
        apply_chart(chart, recording)
        st.plotly_chart(chart, use_container_width=True)
        as_of = pretty_date(max(visible["date"]))
        st.caption(
            f"Source: ICE BofA option-adjusted spreads, via FRED at the St. Louis Fed "
            f"([fred.stlouisfed.org](https://fred.stlouisfed.org/)). "
            f"Investment grade is BAMLC0A0CM, BBB is BAMLC0A4CBBB, high yield is BAMLH0A0HYM2. "
            f"As of {as_of}. FRED usually posts the prior business day. "
            "These are bond spreads for the whole market, not NVIDIA's CDS."
        )
    except (SourceUnavailable, Exception) as exc:
        unavailable(exc)
