"""Daily equity closes from Yahoo Finance via yfinance.

yfinance is an unofficial library. A failure for one ticker does not drop
the tickers that succeeded. Columns: date, ticker, close.
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import yfinance as yf

from sources import SourceUnavailable


def fetch_closes(tickers: list[str], start: date) -> pd.DataFrame:
    frames = []
    failures: list[str] = []
    for ticker in tickers:
        try:
            history = yf.Ticker(ticker).history(start=start.isoformat(), auto_adjust=False)
        except Exception as exc:
            failures.append(f"{ticker}: {exc}")
            continue
        if history is None or history.empty or "Close" not in history.columns:
            columns = [] if history is None else list(history.columns)
            failures.append(f"{ticker}: no Close column ({columns}).")
            continue
        frame = history.reset_index()[["Date", "Close"]].rename(columns={"Date": "date", "Close": "close"})
        stamps = pd.to_datetime(frame["date"])
        if stamps.dt.tz is not None:
            stamps = stamps.dt.tz_convert("America/New_York")
        frame["date"] = stamps.dt.date
        frame["ticker"] = ticker
        frames.append(frame[["date", "ticker", "close"]])
    if not frames:
        detail = "; ".join(failures) or "no tickers requested"
        raise SourceUnavailable(f"Yahoo Finance returned no prices. {detail}.")
    combined = pd.concat(frames, ignore_index=True)
    combined.attrs["failures"] = failures
    return combined.sort_values(["ticker", "date"]).reset_index(drop=True)
