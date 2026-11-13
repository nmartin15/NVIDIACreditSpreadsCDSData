"""Treasury curve interpolation.

Yields are in percent. Maturities are years. The curve is linear between the
points it actually has. Requests below 1 year or above 30 years use the 1-year
or 30-year yield. Those two points are required.
"""

from __future__ import annotations

import math
from datetime import date

import pandas as pd

MIN_YEAR = 1.0
MAX_YEAR = 30.0


def interpolate_yield(nodes: dict[float, float], years: float) -> float:
    """Return the linearly interpolated yield for `years`.

    `nodes` maps maturity in years to a yield in percent. Missing points are
    omitted by the caller. The 1-year and 30-year nodes must be present.
    """
    clean: dict[float, float] = {}
    for maturity, yield_percent in nodes.items():
        if yield_percent is None or (isinstance(yield_percent, float) and math.isnan(yield_percent)):
            continue
        clean[float(maturity)] = float(yield_percent)
    if MIN_YEAR not in clean or MAX_YEAR not in clean:
        raise ValueError("Curve needs both the 1-year and 30-year yields.")
    if years <= MIN_YEAR:
        return clean[MIN_YEAR]
    if years >= MAX_YEAR:
        return clean[MAX_YEAR]
    points = sorted(clean)
    for left, right in zip(points, points[1:]):
        if left <= years <= right:
            span = right - left
            weight = 0.0 if span == 0 else (years - left) / span
            return clean[left] + weight * (clean[right] - clean[left])
    raise ValueError(f"No curve segment covers {years} years.")


def curve_nodes(yields: pd.DataFrame, on: date) -> dict[float, float]:
    """Last published yield on or before `on` for each maturity.

    `yields` columns: date, maturity_years, yield_percent.
    """
    frame = yields.copy()
    frame["date"] = pd.to_datetime(frame["date"]).dt.date
    frame = frame[frame["date"] <= on]
    nodes: dict[float, float] = {}
    for maturity, group in frame.groupby("maturity_years"):
        group = group.dropna(subset=["yield_percent"]).sort_values("date")
        if group.empty:
            continue
        nodes[float(maturity)] = float(group.iloc[-1]["yield_percent"])
    return nodes
