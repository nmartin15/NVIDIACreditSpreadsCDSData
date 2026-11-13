"""NVIDIA's share price. One line, no headline marks on the plot."""

from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from panels.common import apply_chart, color_for, load_closes, pretty_date, unavailable, window_start
from sources import SourceUnavailable


def render(history: str, recording: bool) -> None:
    st.subheader("Did the stock move with the credit?")
    start = window_start(history)
    try:
        closes, failures = load_closes(("NVDA",), start.isoformat())
    except SourceUnavailable as exc:
        unavailable(exc)
        return
    except Exception as exc:
        unavailable(exc)
        return
    closes = closes.sort_values("date")
    last = closes.iloc[-1]
    previous = closes.iloc[-2] if len(closes) > 1 else None
    delta = None
    if previous is not None:
        change = float(last["close"] - previous["close"])
        percent = change / float(previous["close"]) * 100
        delta = f"{change:+.2f} ({percent:+.1f}%) vs {pretty_date(previous['date'])}"
    st.metric("Last close", f"${float(last['close']):,.2f}", delta=delta)
    chart = go.Figure()
    chart.add_trace(
        go.Scatter(
            x=closes["date"],
            y=closes["close"],
            mode="lines",
            name="NVDA",
            line=dict(color=color_for("NVDA"), width=2.5),
            hovertemplate="%{x|%b %-d, %Y}<br>$%{y:.2f}<extra>NVDA</extra>",
        )
    )
    chart.update_yaxes(title="Close, $")
    chart.update_xaxes(title="")
    apply_chart(chart, recording)
    chart.update_layout(showlegend=False, height=320)
    st.plotly_chart(chart, use_container_width=True)
    st.caption(
        f"Source: Yahoo Finance daily closes, pulled with the yfinance library "
        f"([finance.yahoo.com](https://finance.yahoo.com/quote/NVDA/)). "
        f"Last close {pretty_date(last['date'])}. This is the share price, not a credit spread."
    )
    if failures:
        st.caption("Missing prices: " + "; ".join(failures))
