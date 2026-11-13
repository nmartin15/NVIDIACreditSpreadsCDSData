"""G-spread and the CDS upfront approximation.

G-spread is the bond yield minus the Treasury yield of the same maturity,
in basis points. It is not option-adjusted spread.

The CDS approximation is for display only. It is labeled "approx" wherever
it is shown. Risky duration defaults to 4.5, the rough figure for a 5-year
contract used in the project brief.
"""

from __future__ import annotations

from datetime import date

YEAR_DAYS = 365.25
RISKY_DURATION_5Y = 4.5


def years_to_maturity(maturity: date, trade_date: date) -> float:
    return (maturity - trade_date).days / YEAR_DAYS


def g_spread_bp(bond_yield_percent: float, treasury_yield_percent: float) -> float:
    """Basis points. Both yields are in percent, so the gap is multiplied by 100."""
    return (bond_yield_percent - treasury_yield_percent) * 100


def coupon_bp_from_fixed_rate(fixed_rate: float) -> float:
    """CFTC fixed-rate convention: 0.01 means a 1% coupon, which is 100 bp."""
    return fixed_rate * 10_000


def parse_notional(raw: object) -> float | None:
    """Dollar notional, or None when the tape capped it or left it blank.

    A trailing plus means the true size was larger than the published cap.
    Using the cap as if it were the real size would invent an upfront price.
    """
    if raw is None:
        return None
    text = str(raw).strip().replace(",", "")
    if not text or text.endswith("+") or text.lower() in {"nan", "none"}:
        return None
    try:
        value = float(text)
    except ValueError:
        return None
    if value <= 0:
        return None
    return value


def upfront_points(payment: float, notional: float) -> float:
    """Upfront payment as points of par. One point is 1% of notional."""
    if notional <= 0:
        raise ValueError("Notional must be positive.")
    return payment / notional * 100


def approx_par_spread_bp(
    coupon_bp: float,
    points: float,
    risky_duration: float = RISKY_DURATION_5Y,
) -> float:
    """Rough par spread. Display only, and only with an "approx" label."""
    if risky_duration <= 0:
        raise ValueError("Risky duration must be positive.")
    return coupon_bp + (points * 100) / risky_duration


def daily_bond_yields(prints: pd.DataFrame) -> pd.DataFrame:
    """One yield per bond per day. Trades under $100k par are left out when size is known.

    Columns: trade_date, ticker, label, maturity, yield_percent, price, size_par.
    """
    if prints.empty:
        return prints.copy()
    kept = prints.copy()
    sized = kept["size_par"].notna()
    kept = kept.loc[~sized | (kept["size_par"] >= 100_000)]
    rows = []
    grouped = kept.groupby(["trade_date", "ticker", "label", "maturity"], dropna=False)
    for (trade_date, ticker, label, maturity), group in grouped:
        usable = group.dropna(subset=["yield_percent"])
        weighted = usable.dropna(subset=["size_par"])
        if not weighted.empty and weighted["size_par"].sum() > 0:
            yield_percent = float((weighted["yield_percent"] * weighted["size_par"]).sum() / weighted["size_par"].sum())
            size_par = float(weighted["size_par"].sum())
        elif not usable.empty:
            yield_percent = float(usable["yield_percent"].mean())
            size_par = float("nan")
        else:
            continue
        price = usable["price"].dropna()
        rows.append(
            {
                "trade_date": trade_date,
                "ticker": ticker,
                "label": label,
                "maturity": maturity,
                "yield_percent": yield_percent,
                "price": float(price.iloc[-1]) if not price.empty else float("nan"),
                "size_par": size_par,
            }
        )
    return pd.DataFrame(rows)


def with_g_spreads(prints: pd.DataFrame, treasury_yields: pd.DataFrame) -> pd.DataFrame:
    """Add matched Treasury yield and G-spread, in basis points, to daily bond rows."""
    from analytics.curve import curve_nodes, interpolate_yield

    rows = []
    for record in prints.itertuples(index=False):
        matched = float("nan")
        spread = float("nan")
        try:
            nodes = curve_nodes(treasury_yields, record.trade_date)
            matched = interpolate_yield(nodes, years_to_maturity(record.maturity, record.trade_date))
            spread = g_spread_bp(float(record.yield_percent), matched)
        except (ValueError, TypeError):
            pass
        rows.append(
            {
                "trade_date": record.trade_date,
                "ticker": record.ticker,
                "label": record.label,
                "maturity": record.maturity,
                "yield_percent": record.yield_percent,
                "price": record.price,
                "size_par": record.size_par,
                "treasury_yield": matched,
                "g_spread_bp": spread,
            }
        )
    return pd.DataFrame(rows)
