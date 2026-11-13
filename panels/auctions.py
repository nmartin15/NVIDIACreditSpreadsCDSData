"""Treasury auction scorecard, written as demand rather than as a tape."""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import streamlit as st

from panels.common import load_auctions, pretty_date, unavailable
from sources import SourceUnavailable

TERMS = ["2-Year", "3-Year", "5-Year", "7-Year", "10-Year", "20-Year", "30-Year"]


def _word(current: float, average: float, higher_is_better: bool, band: float) -> str:
    if pd.isna(current) or pd.isna(average):
        return "—"
    gap = current - average
    if abs(gap) < band:
        return "In line"
    higher = gap > 0
    if higher_is_better:
        return "Stronger" if higher else "Weaker"
    return "Higher" if higher else "Lower"


def _share(part: float, whole: float) -> float:
    if pd.isna(part) or pd.isna(whole) or whole == 0:
        return float("nan")
    return part / whole


def scorecard(auctions: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for term in TERMS:
        group = auctions[auctions["security_term"] == term].sort_values("auction_date")
        if group.empty:
            rows.append({"term": term, "missing": True})
            continue
        latest = group.iloc[-1]
        prior = group.iloc[:-1].tail(6)
        dealer = _share(latest["primary_dealer_accepted"], latest["competitive_accepted"])
        indirect = _share(latest["indirect_accepted"], latest["competitive_accepted"])
        dealer_avg = prior.apply(
            lambda row: _share(row["primary_dealer_accepted"], row["competitive_accepted"]),
            axis=1,
        ).mean()
        indirect_avg = prior.apply(
            lambda row: _share(row["indirect_accepted"], row["competitive_accepted"]),
            axis=1,
        ).mean()
        rows.append(
            {
                "term": term,
                "missing": False,
                "auction_date": latest["auction_date"],
                "high_yield": latest["high_yield"],
                "bid_to_cover": latest["bid_to_cover"],
                "bid_avg": prior["bid_to_cover"].mean(),
                "dealer": dealer,
                "dealer_avg": dealer_avg,
                "indirect": indirect,
                "indirect_avg": indirect_avg,
                "reopening": bool(latest["reopening"]),
                "history": int(prior["bid_to_cover"].notna().sum()),
                "feed": latest["feed"],
            }
        )
    return pd.DataFrame(rows)


def _paint(column: str, value: str) -> str:
    good = {"Bidding": {"Stronger"}, "Dealer demand": {"Lower"}, "Buyer demand": {"More"}}
    bad = {"Bidding": {"Weaker"}, "Dealer demand": {"Higher"}, "Buyer demand": {"Less"}}
    if value in good.get(column, set()):
        return "background-color: #E5F4EA; color: #1B4332"
    if value in bad.get(column, set()):
        return "background-color: #FDECEC; color: #9B2226"
    return ""


def _indirect_word(current: float, average: float) -> str:
    word = _word(current, average, higher_is_better=True, band=0.01)
    if word == "Stronger":
        return "More"
    if word == "Weaker":
        return "Less"
    return word


def _sentence(row: pd.Series) -> str:
    if row.get("missing"):
        return "The latest 10-year auction was not in the file, so there is no base-rate reading yet."
    bidding = _word(row["bid_to_cover"], row["bid_avg"], True, 0.05)
    dealers = _word(row["dealer"], row["dealer_avg"], False, 0.01)
    when = pretty_date(row["auction_date"])
    yield_text = f"{row['high_yield']:.2f}%"
    if bidding == "Weaker" or dealers == "Higher":
        tone = "Demand looks softer than the recent run of 10-year auctions."
    elif bidding == "Stronger" and dealers == "Lower":
        tone = "Demand looks healthier than the recent run of 10-year auctions."
    else:
        tone = "Demand is mixed against the recent run of 10-year auctions."
    reopen = " This one is a reopening, so the comparison is less clean." if row["reopening"] else ""
    return (
        f"The latest 10-year auction cleared at {yield_text} on {when}. "
        f"{tone} The yield is the base cost of borrowing. It is not NVIDIA's own rate.{reopen}"
    )


def _table(card: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for record in card.itertuples(index=False):
        if record.missing:
            rows.append(
                {
                    "Maturity": record.term.replace("-Year", "-year"),
                    "Auction": "—",
                    "Yield": "—",
                    "Bids per $1": "—",
                    "Bidding": "—",
                    "Dealers took": "—",
                    "Dealer demand": "—",
                    "Indirect buyers": "—",
                    "Buyer demand": "—",
                    "Note": "No auction in this history",
                }
            )
            continue
        note = []
        if record.reopening:
            note.append("Reopening")
        if record.history < 6:
            note.append(f"Average uses {record.history} earlier auctions")
        rows.append(
            {
                "Maturity": record.term.replace("-Year", "-year"),
                "Auction": pretty_date(record.auction_date),
                "Yield": f"{record.high_yield:.2f}%",
                "Bids per $1": f"{record.bid_to_cover:.2f}x",
                "Bidding": _word(record.bid_to_cover, record.bid_avg, True, 0.05),
                "Dealers took": "—" if pd.isna(record.dealer) else f"{record.dealer:.0%}",
                "Dealer demand": _word(record.dealer, record.dealer_avg, False, 0.01),
                "Indirect buyers": "—" if pd.isna(record.indirect) else f"{record.indirect:.0%}",
                "Buyer demand": _indirect_word(record.indirect, record.indirect_avg),
                "Note": ", ".join(note),
            }
        )
    return pd.DataFrame(rows)


def render(recording: bool) -> None:
    del recording
    st.subheader("Check: is this just the Treasury market?")
    st.write(
        "Every credit spread sits on top of the Treasury yield. "
        "If investors were dumping government debt, NVIDIA's protection would look worse for that reason alone. "
        "A stronger auction, with more bids and dealers holding less, means the base rate still found buyers."
    )
    try:
        end = date.today()
        auctions = load_auctions((end - timedelta(days=500)).isoformat(), end.isoformat())
        card = scorecard(auctions)
        ten_year = card[card["term"] == "10-Year"]
        if not ten_year.empty:
            st.markdown(f"**{_sentence(ten_year.iloc[0])}**")
        table = _table(card)
        painted = table.style
        for column in ("Bidding", "Dealer demand", "Buyer demand"):
            painted = painted.map(lambda value, column=column: _paint(column, value), subset=[column])
        st.dataframe(painted, hide_index=True, use_container_width=True)
        feed = "U.S. Treasury"
        feeds = auctions["feed"].dropna().unique() if "feed" in auctions.columns else []
        if len(feeds):
            feed = feeds[0]
        as_of = pretty_date(max(auctions["auction_date"])) if len(auctions) else "unknown"
        st.caption(
            f"Source: {feed}, auction results from TreasuryDirect "
            f"([treasurydirect.gov](https://www.treasurydirect.gov/TA_WS/securities/search)). "
            f"Latest auction in this table closed {as_of}. "
            "Green is healthier demand than the average of the previous auctions of that maturity "
            "(up to six). Red is weaker. "
            "The gap versus the when-issued yield at 1:00 p.m. New York time is not in this feed, so it is not shown."
        )
    except (SourceUnavailable, Exception) as exc:
        unavailable(exc)
