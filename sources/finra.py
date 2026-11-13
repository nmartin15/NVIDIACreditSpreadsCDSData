"""Corporate bond prints.

The FINRA API catalog refused an anonymous call (HTTP 401), and no Public
credential has been checked yet. This module does not guess a trade-level
dataset. It reads a spreadsheet the user exports from FINRA's own website.

Expected columns in data/manual_bond_prints.csv:
trade_date, ticker, label, yield_percent, maturity
Optional: price, size_par, trade_time
"""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd

from sources import SourceUnavailable

ROOT = Path(__file__).resolve().parents[1]
PRINTS = ROOT / "data" / "manual_bond_prints.csv"
REQUIRED = ["trade_date", "ticker", "label", "yield_percent", "maturity"]


def fetch_bond_prints() -> pd.DataFrame:
    """Bond prints ready for a G-spread.

    Columns: trade_date, ticker, label, yield_percent, maturity, price, size_par, trade_time.
    yield_percent is the bond's yield in percent. maturity is a date.
    """
    if not PRINTS.exists():
        client = os.getenv("FINRA_CLIENT_ID", "").strip()
        if client:
            raise SourceUnavailable(
                "A FINRA client id is in .env, but the probe has not confirmed a per-bond "
                "trade dataset on that credential. Run scripts/probe_sources.py before any "
                "FINRA parser is written. Until then, export prints from FINRA's website "
                "to data/manual_bond_prints.csv."
            )
        raise SourceUnavailable(
            "NVIDIA bond trades are not loaded. FINRA's public catalog needs a free "
            "credential, and this project will not guess trade fields or scrape FINRA's "
            "website. Export the bonds you care about to data/manual_bond_prints.csv, "
            "or add FINRA_CLIENT_ID and FINRA_CLIENT_SECRET to .env and re-run the probe."
        )
    frame = pd.read_csv(PRINTS)
    missing = [column for column in REQUIRED if column not in frame.columns]
    if missing:
        raise SourceUnavailable(
            f"data/manual_bond_prints.csv is missing {missing}. "
            f"It needs {REQUIRED}. Optional columns: price, size_par, trade_time."
        )
    for column in ("price", "size_par", "trade_time"):
        if column not in frame.columns:
            frame[column] = pd.NA
    frame["trade_date"] = pd.to_datetime(frame["trade_date"]).dt.date
    frame["maturity"] = pd.to_datetime(frame["maturity"]).dt.date
    frame["yield_percent"] = pd.to_numeric(frame["yield_percent"], errors="coerce")
    frame["price"] = pd.to_numeric(frame["price"], errors="coerce")
    frame["size_par"] = pd.to_numeric(frame["size_par"], errors="coerce")
    frame["ticker"] = frame["ticker"].astype(str).str.upper()
    return frame[REQUIRED + ["price", "size_par", "trade_time"]]
