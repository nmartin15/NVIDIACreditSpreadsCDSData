"""Press-reported CDS premiums. Citations, with the contract maturity kept visible."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from panels.common import (
    active_roster,
    apply_chart,
    color_for,
    display_name,
    pretty_date,
    reported_cds,
)

INSURED = 10_000_000


def _dollars(basis_points: float) -> int:
    return int(round(basis_points / 10_000 * INSURED))


def _is_five_year(tenor: object) -> bool:
    return str(tenor).strip().upper() == "5Y"


def _tenor_phrase(tenor: object) -> str:
    if _is_five_year(tenor):
        return "5-year contract"
    text = str(tenor).strip()
    if text.lower() in {"", "nan", "unspecified", "none"}:
        return "Tenor not stated in the article"
    return text


def _is_five_year_mask(frame: pd.DataFrame) -> pd.Series:
    return frame["tenor"].map(_is_five_year)


def _add_company(fig: go.Figure, company: str, history: pd.DataFrame, color: str) -> None:
    five = history[_is_five_year_mask(history)].sort_values("date")
    other = history[~_is_five_year_mask(history)].sort_values("date")
    if not five.empty:
        fig.add_trace(
            go.Scatter(
                x=five["date"],
                y=five["level_bp"],
                mode="lines+markers+text",
                name=f"{company}, 5-year",
                line=dict(color=color, width=3),
                marker=dict(size=11, color=color),
                text=[f"{value:.0f}" for value in five["level_bp"]],
                textposition="top center",
                customdata=[_dollars(value) for value in five["level_bp"]],
                hovertemplate=(
                    "%{x|%b %-d, %Y}<br>%{y:.0f} bp · 5-year"
                    "<br>$%{customdata:,} a year on $10 million<extra>" + company + "</extra>"
                ),
            )
        )
    if not other.empty:
        fig.add_trace(
            go.Scatter(
                x=other["date"],
                y=other["level_bp"],
                mode="markers+text",
                name=f"{company}, tenor not stated",
                marker=dict(symbol="diamond", size=16, color=color, line=dict(width=1.5, color="#1F1A17")),
                text=[f"{value:.0f}" for value in other["level_bp"]],
                textposition="bottom center",
                customdata=[_dollars(value) for value in other["level_bp"]],
                hovertemplate=(
                    "%{x|%b %-d, %Y}<br>%{y:.0f} bp · tenor not stated"
                    "<br>$%{customdata:,} a year on $10 million<extra>" + company + "</extra>"
                ),
            )
        )


def _draw(levels: pd.DataFrame, roster: list[dict], recording: bool, stressed: bool) -> None:
    chosen = levels[levels["name"].eq("CRWV") if stressed else levels["name"].ne("CRWV")]
    if chosen.empty:
        return
    fig = go.Figure()
    for item in roster:
        history = chosen[chosen["name"] == item["ticker"]]
        if history.empty:
            continue
        _add_company(fig, display_name(item["ticker"], roster), history, color_for(item["ticker"], roster))
    fig.update_yaxes(title="Annual premium, basis points", rangemode="tozero", ticksuffix=" bp")
    fig.update_xaxes(title="")
    apply_chart(fig, recording)
    if stressed:
        fig.update_layout(height=300)
    st.plotly_chart(fig, use_container_width=True)


def render(show_linked: bool, show_peers: bool, recording: bool) -> None:
    st.subheader("Where the CDS premium stands")
    roster = active_roster(show_linked, show_peers)
    allowed = {item["ticker"] for item in roster}
    levels = reported_cds()
    levels = levels[levels["name"].isin(allowed)].copy()
    if levels.empty:
        st.warning("No reported CDS rows match the companies turned on in the sidebar.")
        return
    newest = max(levels["date"])
    st.write(
        f"Newest figure in this file: **{pretty_date(newest)}**. "
        "The time in the header is when this screen loaded."
    )
    with st.container(border=True):
        st.markdown("**How to read the number**")
        st.write(
            "A CDS spread is the annual premium for insurance against a default, in basis points of the amount insured. "
            "100 basis points is 1 percent a year, so 139 basis points is about $139,000 a year to insure $10 million. "
            "The usual newspaper quote is the five-year contract on the company's senior debt. "
            "That is a different number from a bond's extra yield over Treasuries, which is the comparison in the bond section."
        )
        st.write(
            "The July NVIDIA and Oracle prints are five-year contracts. "
            "The November 6 NVIDIA and Oracle articles did not name a maturity. "
            "A five-year premium and a longer contract are different instruments, so those November points are diamonds and are not connected to the five-year line."
        )

    latest_rows = levels.sort_values("date").groupby("name", as_index=False).tail(1)
    order = [item["ticker"] for item in roster if item["ticker"] in set(latest_rows["name"])]
    latest_rows = latest_rows.set_index("name").loc[order].reset_index()
    columns = st.columns(len(latest_rows))
    for column, row in zip(columns, latest_rows.itertuples(index=False)):
        history = levels[levels["name"] == row.name].sort_values("date")
        five = history[_is_five_year_mask(history)]
        with column:
            with st.container(border=True):
                st.markdown(f"**{display_name(row.name, roster)}**")
                st.metric(
                    _tenor_phrase(row.tenor),
                    f"{row.level_bp:.0f} bp",
                    help=f"{pretty_date(row.date)}. {row.source}. {row.note}",
                )
                st.caption(pretty_date(row.date))
                st.write(f"About **${_dollars(row.level_bp):,}** a year to insure $10 million.")
                if len(five) >= 2:
                    change = float(five.iloc[-1]["level_bp"] - five.iloc[0]["level_bp"])
                    st.write(
                        f"5-year change: {five.iloc[0]['level_bp']:.0f} bp on {pretty_date(five.iloc[0]['date'])} "
                        f"→ {five.iloc[-1]['level_bp']:.0f} bp on {pretty_date(five.iloc[-1]['date'])} "
                        f"({change:+.0f} bp)."
                    )
                elif len(five) == 1 and _is_five_year(row.tenor):
                    st.write("One 5-year print is on file, so there is no earlier 5-year level to difference.")
                if not _is_five_year(row.tenor) and not five.empty:
                    prior = five.iloc[-1]
                    gap = float(row.level_bp - prior.level_bp)
                    st.write(
                        f"Last confirmed 5-year print: {prior.level_bp:.0f} bp on {pretty_date(prior.date)}. "
                        f"This article is {gap:+.0f} bp versus that print, and the maturity was not stated."
                    )

    st.write(
        "Lines are five-year premiums. Diamonds are articles that quoted a level and did not say which maturity. "
        "The axis starts at zero so the height is the premium."
    )
    _draw(levels, roster, recording, stressed=False)
    if (levels["name"] == "CRWV").any():
        st.write("CoreWeave sits on its own scale. Its premium is several times the investment-grade names.")
        _draw(levels, roster, recording, stressed=True)

    show = levels.sort_values(["date", "name"], ascending=[False, True]).copy()
    show["Company"] = show["name"].map(lambda ticker: display_name(ticker, roster))
    show["Date"] = show["date"].map(pretty_date)
    show["Premium"] = show["level_bp"].map(lambda value: f"{value:.0f} bp")
    show["Per $10 million"] = show["level_bp"].map(lambda value: f"${_dollars(value):,} / year")
    show["Contract"] = show["tenor"].map(_tenor_phrase)
    show = show.rename(columns={"source": "Source", "url": "Article", "note": "Note"})
    st.dataframe(
        show[["Date", "Company", "Premium", "Per $10 million", "Contract", "Source", "Article", "Note"]],
        column_config={"Article": st.column_config.LinkColumn("Article")},
        hide_index=True,
        use_container_width=True,
    )
    st.caption(
        "Each row keeps the article it came from. "
        "November 6 NVIDIA and Oracle levels were described as approximate. "
        "CoreWeave that day is a five-year spread, attributed to Deutsche Bank via CNBC. "
        "A basis-point gap is comparable across rows only when the Contract column matches."
    )
