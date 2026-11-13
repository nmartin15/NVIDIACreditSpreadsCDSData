"""NVIDIA bond yields versus the Treasury yield of the same maturity."""

from __future__ import annotations

from datetime import timedelta

import plotly.express as px
import streamlit as st

from analytics.spreads import daily_bond_yields, with_g_spreads
from panels.common import (
    active_roster,
    apply_chart,
    display_name,
    load_prints,
    load_yields,
    pretty_date,
    unavailable,
    window_start,
)
from sources import SourceUnavailable


def prepared(history: str, show_linked: bool, show_peers: bool):
    prints = load_prints()
    allowed = {item["ticker"] for item in active_roster(show_linked, show_peers)}
    prints = prints[prints["ticker"].isin(allowed)]
    if prints.empty:
        raise SourceUnavailable("The bond spreadsheet has no rows for the companies turned on in the sidebar.")
    daily = daily_bond_yields(prints)
    start = min(daily["trade_date"]) - timedelta(days=7)
    yields = load_yields(start.isoformat())
    priced = with_g_spreads(daily, yields)
    priced = priced[priced["trade_date"] >= window_start(history)]
    return priced


def render(history: str, show_linked: bool, show_peers: bool, recording: bool) -> None:
    st.subheader("What does it cost these companies to borrow, bond by bond?")
    st.write(
        "Each line is a G-spread: the bond's yield minus the Treasury yield of a similar maturity. "
        "It is a plain gap, not an option-adjusted spread. Up means that bond got more expensive to issue."
    )
    try:
        priced = prepared(history, show_linked, show_peers)
    except SourceUnavailable as exc:
        unavailable(exc)
        return
    except Exception as exc:
        unavailable(exc)
        return
    main = priced[priced["ticker"] != "CRWV"]
    stressed = priced[priced["ticker"] == "CRWV"]
    if not main.empty:
        chart = px.line(
            main,
            x="trade_date",
            y="g_spread_bp",
            color="label",
            labels={"trade_date": "", "g_spread_bp": "G-spread, basis points", "label": ""},
        )
        apply_chart(chart, recording)
        st.plotly_chart(chart, use_container_width=True)
    if not stressed.empty:
        st.write("CoreWeave is drawn on its own. Its yield is much higher, and it would flatten everyone else.")
        chart = px.line(
            stressed,
            x="trade_date",
            y="g_spread_bp",
            color="label",
            labels={"trade_date": "", "g_spread_bp": "G-spread, basis points", "label": ""},
        )
        apply_chart(chart, recording)
        chart.update_layout(height=320)
        st.plotly_chart(chart, use_container_width=True)
    latest = priced.sort_values("trade_date").groupby("label", as_index=False).tail(1)
    latest = latest.sort_values("g_spread_bp", ascending=False)
    show = latest.copy()
    show["Company"] = show["ticker"].map(lambda ticker: display_name(ticker))
    show["Trade"] = show["trade_date"].map(pretty_date)
    show["Price"] = show["price"].map(lambda value: "—" if pd.isna(value) else f"{value:.3f}")
    show["Bond yield"] = show["yield_percent"].map(lambda value: f"{value:.2f}%")
    show["Treasury yield"] = show["treasury_yield"].map(lambda value: "—" if pd.isna(value) else f"{value:.2f}%")
    show["G-spread"] = show["g_spread_bp"].map(lambda value: "—" if pd.isna(value) else f"{value:.0f} bp")
    st.dataframe(
        show[["Company", "label", "Trade", "Price", "Bond yield", "Treasury yield", "G-spread"]].rename(
            columns={"label": "Bond"}
        ),
        hide_index=True,
        use_container_width=True,
    )
    st.caption(
        "G-spread, not OAS. Treasury yields are end-of-day FRED figures and the bond trades happen during the day, "
        "so a same-day spread is approximate. Trades under $100,000 are dropped when the file includes a size. "
        "Source: the spreadsheet in data/manual_bond_prints.csv, compared with ICE BofA's Treasury curve via FRED."
    )


# pandas is used in the formatting lambdas above.
import pandas as pd
