"""FRED observations.

The public observations payload is a dict with an `observations` list. Each
observation has `date` and `value`. Missing values arrive as the string ".".

Spreads are ICE BofA option-adjusted spreads published in percent. This module
converts them to basis points. Treasury yields stay in percent.
"""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

import pandas as pd
import requests
import yaml

from sources import SourceUnavailable

ROOT = Path(__file__).resolve().parents[1]
OBSERVATIONS_URL = "https://api.stlouisfed.org/fred/series/observations"
TIMEOUT = 60


def _series_file() -> dict:
    with (ROOT / "config" / "series.yaml").open(encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle)
    if not isinstance(loaded, dict):
        raise SourceUnavailable("config/series.yaml did not contain a mapping.")
    return loaded


def _get_observations(series_id: str, start: date) -> pd.DataFrame:
    key = os.getenv("FRED_API_KEY", "").strip()
    if not key:
        raise SourceUnavailable(
            "Add a free FRED API key. Create an account at fred.stlouisfed.org, "
            "open Account, then API Keys, and put the key in .env as FRED_API_KEY."
        )
    response = requests.get(
        OBSERVATIONS_URL,
        params={
            "series_id": series_id,
            "api_key": key,
            "file_type": "json",
            "observation_start": start.isoformat(),
        },
        timeout=TIMEOUT,
        headers={"User-Agent": "ai-credit-watch/0.1 (educational)"},
    )
    if response.status_code != 200:
        raise SourceUnavailable(
            f"FRED returned HTTP {response.status_code} for {series_id}."
        )
    try:
        payload = response.json()
    except ValueError as exc:
        raise SourceUnavailable(f"FRED did not return JSON for {series_id}.") from exc
    observations = payload.get("observations") if isinstance(payload, dict) else None
    if not isinstance(observations, list):
        keys = list(payload) if isinstance(payload, dict) else type(payload).__name__
        raise SourceUnavailable(f"FRED response for {series_id} has no observations list. Keys: {keys}.")
    rows = []
    for observation in observations:
        if not isinstance(observation, dict) or "date" not in observation or "value" not in observation:
            found = list(observation) if isinstance(observation, dict) else type(observation).__name__
            raise SourceUnavailable(f"FRED observation for {series_id} is missing date or value. Keys: {found}.")
        raw = observation["value"]
        if raw in {".", "", None}:
            value = float("nan")
        else:
            value = float(raw)
        rows.append({"date": observation["date"], "value": value})
    frame = pd.DataFrame(rows, columns=["date", "value"])
    frame["date"] = pd.to_datetime(frame["date"]).dt.date
    return frame


def fetch_credit_spreads(start: date) -> pd.DataFrame:
    """ICE BofA OAS in basis points.

    Columns: date, series_id, label, value_bp.
    """
    frames = []
    for item in _series_file().get("spreads", []):
        observed = _get_observations(item["id"], start)
        observed["series_id"] = item["id"]
        observed["label"] = item["label"]
        observed["value_bp"] = observed["value"] * 100
        frames.append(observed.drop(columns=["value"]))
    if not frames:
        raise SourceUnavailable("config/series.yaml has no spread series.")
    return pd.concat(frames, ignore_index=True)


def fetch_treasury_yields(start: date) -> pd.DataFrame:
    """Constant-maturity Treasury yields, in percent.

    Columns: date, series_id, maturity_years, yield_percent.
    """
    frames = []
    for item in _series_file().get("treasuries", []):
        observed = _get_observations(item["id"], start)
        observed["series_id"] = item["id"]
        observed["maturity_years"] = float(item["years"])
        observed["yield_percent"] = observed["value"]
        frames.append(observed.drop(columns=["value"]))
    if not frames:
        raise SourceUnavailable("config/series.yaml has no Treasury series.")
    return pd.concat(frames, ignore_index=True)
