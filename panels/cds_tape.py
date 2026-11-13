"""NVIDIA prints on the public DTCC credit tape, newest session first."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from analytics.spreads import (
    approx_par_spread_bp,
    coupon_bp_from_fixed_rate,
    parse_notional,
    upfront_points,
)
from panels.common import apply_chart, load_cds, names, pretty_date, unavailable
from sources import SourceUnavailable


def _nvidia() -> dict:
    for item in names():
        if item.get("ticker") == "NVDA":
            return item
    return {"ticker": "NVDA", "display_name": "NVIDIA", "tape_names": ["NVIDIA"], "underlier_ids": []}


def _is_nvidia(row: pd.Series, name: dict) -> bool:
    underlier = str(row["underlier_id"]).strip().upper()
    asset = str(row["asset_name"]).upper()
    ids = {str(value).strip().upper() for value in name.get("underlier_ids") or []}
    if underlier and underlier in ids:
        return True
    return any(str(tape_name).upper() in asset for tape_name in name.get("tape_names") or [])


def _approx(row: pd.Series) -> float | None:
    if str(row["payment_type"]).strip().upper() not in {"", "UFRO"}:
        return None
    notional = parse_notional(row["notional"])
    if notional is None:
        return None
    try:
        coupon = coupon_bp_from_fixed_rate(float(row["fixed_rate"]))
        payment = float(row["payment_amount"])
    except (TypeError, ValueError):
        return None
    if pd.isna(payment):
        return None
    return approx_par_spread_bp(coupon, upfront_points(payment, notional))


def _coupon(value: object) -> str:
    if value in {"", None} or pd.isna(value):
        return "—"
    return f"{coupon_bp_from_fixed_rate(float(value)):.0f} bp"


def _when(value: object) -> str:
    text = str(value or "").replace("Z", "")
    if "T" not in text:
        return text
    day, clock = text.split("T", 1)
    try:
        stamp = pd.Timestamp(day)
        label = f"{stamp.strftime('%b')} {stamp.day}"
    except ValueError:
        label = day
    return f"{label} {clock[:5]} UTC"


def _money(value: object) -> str:
    if value in {"", None} or pd.isna(value):
        return "—"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    return f"${number:,.0f}"


def _load_nvidia() -> tuple[pd.DataFrame, list[str]]:
    tape, failures = load_cds(5)
    fresh = tape[(tape["action"] == "NEWT") & (tape["event_type"] == "TRAD")].copy()
    matched = fresh[fresh.apply(lambda row: _is_nvidia(row, _nvidia()), axis=1)].copy()
    if not matched.empty:
        matched["approx_bp"] = matched.apply(_approx, axis=1)
    return matched, failures


def _priced_chart(matched: pd.DataFrame, recording: bool) -> None:
    """The few prints with a real size, against the coupon on the contract."""
    priced = matched.dropna(subset=["approx_bp"]).sort_values("execution_time")
    if priced.empty:
        st.caption(
            "DTCC published the upfront in dollars on these trades and masked the notional, "
            "so none of them can be turned into a spread."
        )
        return
    coupons = priced["fixed_rate"].map(
        lambda value: coupon_bp_from_fixed_rate(float(value)) if value not in {"", None} else float("nan")
    )
    labels = [
        f"{_when(row.execution_time)}  ·  {row.notional}"
        for row in priced.itertuples(index=False)
    ]
    levels = [float(value) for value in priced["approx_bp"]]
    chart = go.Figure()
    chart.add_bar(
        y=labels,
        x=levels,
        orientation="h",
        name="Approximate spread",
        marker_color="#1B4332",
        text=[f"{value:.0f}" for value in levels],
        textposition="outside",
        textfont=dict(color="#1B4332"),
        cliponaxis=False,
        hovertemplate="%{y}<br>%{x:.0f} bp<extra></extra>",
    )
    coupon_line = float(coupons.median()) if coupons.notna().any() else 100.0
    chart.add_vline(x=coupon_line, line_dash="dash", line_color="#9B2226")
    chart.add_trace(
        go.Scatter(
            x=[None],
            y=[None],
            mode="lines",
            line=dict(color="#9B2226", dash="dash", width=2),
            name=f"{coupon_line:.0f} bp coupon",
        )
    )
    chart.update_xaxes(
        title="Approximate spread, basis points",
        range=[0, max(levels) * 1.18],
    )
    chart.update_yaxes(title="")
    apply_chart(chart, recording)
    chart.update_layout(
        height=max(280, 64 * len(priced) + 90),
        margin=dict(l=8, r=36, t=36, b=8),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
    )
    st.plotly_chart(chart, width="stretch")
    above = int((priced["approx_bp"] > coupon_line).sum())
    st.caption(
        f"Source: DTCC Data Repository, SEC public price dissemination, cumulative credit file "
        f"([pddata.dtcc.com](https://pddata.dtcc.com/ppd/secdashboard)). "
        f"DTCC publishes the notional, the coupon, and the upfront dollars. It does not publish a spread. "
        f"Each bar is calculated here. {above} of {len(priced)} cleared the {coupon_line:.0f} bp coupon, "
        "so the buyer paid cash upfront on top of that coupon. "
        "The other new trades are in the print list under the yardstick. DTCC masked their notional, "
        "so the upfront dollars cannot be turned into a spread."
    )


def render_spread(recording: bool) -> None:
    st.subheader("How NVIDIA protection is trading")
    st.write(
        "This is the price of insuring NVIDIA's senior debt, in basis points a year. "
        "The contract coupon is 100 bp. The market rarely trades exactly there, so the buyer or seller also pays an upfront, "
        "a lump of cash at the start. The approximate spread adds that cash back in, using a 4.5-year duration, "
        "so a bar at 135 bp means the protection is trading 35 bp through the coupon."
    )
    try:
        with st.spinner("Reading the latest NVIDIA prints…"):
            matched, _failures = _load_nvidia()
    except SourceUnavailable as exc:
        unavailable(exc)
        return
    except Exception as exc:
        unavailable(exc)
        return
    if matched.empty:
        st.warning("The latest CDS files loaded, and none of the new trades were NVIDIA.")
        return

    priced = matched.dropna(subset=["approx_bp"])
    days = sorted(matched["report_date"].unique())
    latest_day = days[-1]
    prior_day = days[-2] if len(days) > 1 else None
    latest = matched[matched["report_date"] == latest_day]
    prior = matched[matched["report_date"] == prior_day] if prior_day is not None else matched.iloc[0:0]
    latest_priced = latest["approx_bp"].dropna()
    prior_priced = prior["approx_bp"].dropna()
    latest_median = None if latest_priced.empty else float(latest_priced.median())
    prior_median = None if prior_priced.empty else float(prior_priced.median())
    spread_delta = None
    if latest_median is not None and prior_median is not None:
        spread_delta = f"{latest_median - prior_median:+.0f} bp vs {pretty_date(prior_day)}"
    spread_col, through_col = st.columns(2)
    spread_col.metric(
        f"Latest session, {pretty_date(latest_day)}",
        "—" if latest_median is None else f"{latest_median:.0f} bp",
        delta=spread_delta,
        delta_color="inverse",
        help="Median approximate spread of the prints whose notional DTCC published in full.",
    )
    through_col.metric(
        "Through the 100 bp coupon",
        "—" if latest_median is None else f"{latest_median - 100:+.0f} bp",
        help="The coupon is the running premium. The upfront is the extra cash that pulls the economic spread off 100 bp.",
    )
    _priced_chart(matched, recording)


def render_blotter(recording: bool) -> None:
    del recording
    st.subheader("The prints behind that spread")
    st.write(
        "Upfront is cash, in dollars, paid when the trade is done. It is not the spread. "
        "The coupon is the annual premium on the contract, here 100 bp. "
        "Approximate spread is the whole point of the row: coupon plus that upfront, turned into a running premium. "
        "DTCC does not publish it. Where the notional is masked, the cell says Size hidden, because the upfront dollars have no denominator."
    )
    try:
        matched, failures = _load_nvidia()
    except SourceUnavailable as exc:
        unavailable(exc)
        return
    except Exception as exc:
        unavailable(exc)
        return
    if matched.empty:
        st.warning("The latest CDS files loaded, and none of the new trades were NVIDIA.")
        return

    show = matched.sort_values(["report_date", "execution_time"], ascending=[False, False]).head(15).copy()
    show["When"] = show["execution_time"].map(_when)
    show["Name on the tape"] = show["asset_name"]
    show["Notional"] = show["notional"]
    show["Coupon"] = show["fixed_rate"].map(_coupon)
    show["Upfront"] = show["payment_amount"].map(_money)
    show["Approx spread"] = show["approx_bp"].map(lambda value: "Size hidden" if pd.isna(value) else f"{value:.0f} bp")
    st.dataframe(
        show[["When", "Name on the tape", "Notional", "Coupon", "Upfront", "Approx spread"]],
        hide_index=True,
        width="stretch",
    )
    st.caption(
        "Source: DTCC Data Repository, SEC public price dissemination, cumulative credit file "
        "([pddata.dtcc.com](https://pddata.dtcc.com/ppd/secdashboard)). "
        "Name, notional, coupon, and upfront are copied from that file. "
        "Approximate spread is calculated here from the coupon and the upfront, using a 4.5-year duration. "
        "A notional ending in + is a masked size. Those rows keep the upfront and mark the spread Size hidden."
    )
    if failures:
        st.caption("Files that did not load: " + "; ".join(failures))
