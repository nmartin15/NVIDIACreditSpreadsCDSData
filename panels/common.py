"""Shared loading, caching, and chart styling. Panels call sources only through here."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st
import yaml

from sources.dtcc import fetch_credit_cds
from sources.equities import fetch_closes
from sources.finra import fetch_bond_prints
from sources.fred import fetch_credit_spreads, fetch_treasury_yields
from sources.treasury import fetch_auctions

ROOT = Path(__file__).resolve().parents[1]
RANGES = {
    "3 months": 92,
    "6 months": 183,
    "1 year": 366,
    "2 years": 731,
}


def load_yaml(name: str) -> dict | list:
    with (ROOT / "config" / name).open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def names() -> list[dict]:
    roster = load_yaml("names.yaml")
    return list(roster.get("names", []))


def display_name(ticker: str, roster: list[dict] | None = None) -> str:
    for item in roster or names():
        if item["ticker"] == ticker:
            return item["display_name"]
    return ticker


def color_for(ticker: str, roster: list[dict] | None = None) -> str:
    for item in roster or names():
        if item["ticker"] == ticker:
            return item.get("color", "#1F4E79")
    return "#1F4E79"


def active_roster(show_linked: bool, show_peers: bool) -> list[dict]:
    chosen = []
    for item in names():
        tier = item.get("tier")
        if tier == "core" or (tier == "linked" and show_linked) or (tier == "peer" and show_peers):
            chosen.append(item)
    return chosen


def window_start(label: str, today: date | None = None) -> date:
    today = today or date.today()
    return today - timedelta(days=RANGES[label])


def pretty_date(value: date) -> str:
    return f"{value.strftime('%b')} {value.day}, {value.year}"


def apply_chart(fig, recording: bool) -> None:
    fig.update_layout(
        template="plotly_dark" if recording else "plotly_white",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(size=18 if recording else 15, color="#F4F1EA" if recording else "#1F1A17"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        margin=dict(l=8, r=8, t=28, b=8),
        hovermode="x unified",
        height=460 if recording else 420,
    )


def unavailable(exc: Exception) -> None:
    st.warning("This section is unavailable.")
    st.write(str(exc))


@st.cache_data(ttl=300, show_spinner=False)
def load_auctions(start: str, end: str) -> pd.DataFrame:
    return fetch_auctions(date.fromisoformat(start), date.fromisoformat(end))


@st.cache_data(ttl=300, show_spinner=False)
def load_spreads(start: str) -> pd.DataFrame:
    return fetch_credit_spreads(date.fromisoformat(start))


@st.cache_data(ttl=300, show_spinner=False)
def load_yields(start: str) -> pd.DataFrame:
    return fetch_treasury_yields(date.fromisoformat(start))


@st.cache_data(ttl=300, show_spinner=False)
def load_closes(tickers: tuple[str, ...], start: str) -> tuple[pd.DataFrame, tuple[str, ...]]:
    frame = fetch_closes(list(tickers), date.fromisoformat(start))
    return frame, tuple(frame.attrs.get("failures", []))


@st.cache_data(ttl=300, show_spinner=False)
def load_cds(report_days: int = 10) -> tuple[pd.DataFrame, tuple[str, ...]]:
    frame = fetch_credit_cds(report_days)
    return frame, tuple(frame.attrs.get("failures", []))


@st.cache_data(ttl=300, show_spinner=False)
def load_prints() -> pd.DataFrame:
    return fetch_bond_prints()


def reported_cds() -> pd.DataFrame:
    frame = pd.read_csv(ROOT / "data" / "reported_cds.csv")
    frame["date"] = pd.to_datetime(frame["date"]).dt.date
    frame["level_bp"] = pd.to_numeric(frame["level_bp"])
    return frame


def events() -> list[dict]:
    loaded = load_yaml("events.yaml") or {}
    return list(loaded.get("events", []))


def context_cards() -> list[dict]:
    loaded = load_yaml("context.yaml") or {}
    return list(loaded.get("cards", []))
