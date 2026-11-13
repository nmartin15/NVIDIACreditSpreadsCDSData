"""Treasury auction results.

TreasuryDirect search returns a JSON list. There is no field named auctionDate.
The auction close is `competitiveAuctionCloseDate`. Amounts and yields are
strings. Dealer, direct, and indirect accepted amounts are the competitive
awards, and their sum matched `subtotalCompetitiveParAwardedInsideOfOfferingAmount`
on the sampled 10-year note.

`dateFieldName=auctionDate` returns HTTP 500, so this client does not send it.
"""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import requests

from sources import SourceUnavailable

SEARCH_URL = "https://www.treasurydirect.gov/TA_WS/securities/search"
FISCAL_URL = (
    "https://api.fiscaldata.treasury.gov/services/api/fiscal_service/"
    "v1/accounting/od/auctions_query"
)
TIMEOUT = 90
TERMS = ("2-Year", "3-Year", "5-Year", "7-Year", "10-Year", "20-Year", "30-Year")
COLUMNS = [
    "cusip",
    "security_term",
    "auction_date",
    "high_yield",
    "bid_to_cover",
    "primary_dealer_accepted",
    "direct_accepted",
    "indirect_accepted",
    "competitive_accepted",
    "reopening",
    "feed",
]


def _number(raw: object) -> float:
    if raw is None:
        return float("nan")
    text = str(raw).strip().replace(",", "")
    if text == "" or text.lower() == "null":
        return float("nan")
    return float(text)


def _close_date(raw: object) -> date | None:
    text = str(raw or "").strip()
    if not text or text.lower() == "null":
        return None
    return date.fromisoformat(text[:10])


def _from_treasurydirect(security_type: str, start: date, end: date) -> pd.DataFrame:
    response = requests.get(
        SEARCH_URL,
        params={
            "format": "json",
            "type": security_type,
            "startDate": start.isoformat(),
            "endDate": end.isoformat(),
        },
        timeout=TIMEOUT,
        headers={"User-Agent": "ai-credit-watch/0.1 (educational)"},
    )
    if response.status_code != 200:
        raise SourceUnavailable(
            f"TreasuryDirect search for {security_type} returned HTTP {response.status_code}."
        )
    try:
        payload = response.json()
    except ValueError as exc:
        raise SourceUnavailable("TreasuryDirect did not return JSON.") from exc
    if isinstance(payload, dict):
        message = payload.get("error") or payload.get("message") or list(payload)
        raise SourceUnavailable(f"TreasuryDirect search failed: {message}.")
    if not isinstance(payload, list):
        raise SourceUnavailable(f"TreasuryDirect returned {type(payload).__name__}, not a list.")
    if payload and isinstance(payload[0], dict) and "competitiveAuctionCloseDate" not in payload[0]:
        raise SourceUnavailable(
            "TreasuryDirect record has no competitiveAuctionCloseDate. "
            f"Keys: {list(payload[0])[:12]}."
        )
    rows = []
    for record in payload:
        original = str(record.get("originalSecurityTerm") or "")
        residual = str(record.get("securityTerm") or "")
        term = original if original in TERMS else residual
        if term not in TERMS:
            continue
        auction_day = _close_date(record.get("competitiveAuctionCloseDate"))
        if auction_day is None:
            continue
        rows.append(
            {
                "cusip": record.get("cusip") or "",
                "security_term": term,
                "auction_date": auction_day,
                "high_yield": _number(record.get("highYield")),
                "bid_to_cover": _number(record.get("bidToCoverRatio")),
                "primary_dealer_accepted": _number(record.get("primaryDealersCompetitiveParAwarded")),
                "direct_accepted": _number(record.get("directBiddersCompetitiveParAwarded")),
                "indirect_accepted": _number(record.get("indirectBiddersCompetitiveParAwarded")),
                "competitive_accepted": _number(
                    record.get("subtotalCompetitiveParAwardedInsideOfOfferingAmount")
                ),
                "reopening": str(record.get("reopening") or "").strip().lower() == "yes",
                "feed": "U.S. Treasury (TreasuryDirect)",
            }
        )
    return pd.DataFrame(rows, columns=COLUMNS)


def _from_fiscal_data(start: date) -> pd.DataFrame:
    response = requests.get(
        FISCAL_URL,
        params={
            "page[size]": "300",
            "sort": "-auction_date",
            "filter": f"auction_date:gte:{start.isoformat()}",
        },
        timeout=TIMEOUT,
        headers={"User-Agent": "ai-credit-watch/0.1 (educational)"},
    )
    if response.status_code != 200:
        raise SourceUnavailable(f"Treasury Fiscal Data returned HTTP {response.status_code}.")
    try:
        payload = response.json()
    except ValueError as exc:
        raise SourceUnavailable("Treasury Fiscal Data did not return JSON.") from exc
    records = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(records, list):
        keys = list(payload) if isinstance(payload, dict) else type(payload).__name__
        raise SourceUnavailable(f"Treasury Fiscal Data has no data list. Keys: {keys}.")
    if records and "auction_date" not in records[0]:
        raise SourceUnavailable(
            f"Treasury Fiscal Data record has no auction_date. Keys: {list(records[0])[:12]}."
        )
    rows = []
    for record in records:
        term = str(record.get("security_term") or "")
        if term not in TERMS:
            continue
        auction_day = _close_date(record.get("auction_date"))
        if auction_day is None:
            continue
        primary = _number(record.get("primary_dealer_accepted"))
        direct = _number(record.get("direct_bidder_accepted"))
        indirect = _number(record.get("indirect_bidder_accepted"))
        rows.append(
            {
                "cusip": record.get("cusip") or "",
                "security_term": term,
                "auction_date": auction_day,
                "high_yield": _number(record.get("high_yield")),
                "bid_to_cover": _number(record.get("bid_to_cover_ratio")),
                "primary_dealer_accepted": primary,
                "direct_accepted": direct,
                "indirect_accepted": indirect,
                "competitive_accepted": primary + direct + indirect,
                "reopening": str(record.get("reopening") or "").strip().lower() == "yes",
                "feed": "U.S. Treasury (Fiscal Data)",
            }
        )
    frame = pd.DataFrame(rows, columns=COLUMNS)
    return frame.dropna(subset=["high_yield", "bid_to_cover"])


def fetch_auctions(start: date | None = None, end: date | None = None) -> pd.DataFrame:
    """Recent note and bond auctions for the standard coupon maturities.

    Columns: cusip, security_term, auction_date, high_yield, bid_to_cover,
    primary_dealer_accepted, direct_accepted, indirect_accepted,
    competitive_accepted, reopening, feed.

    Yields are in percent. Amounts are par dollars. `reopening` is true or false.
    """
    end = end or date.today()
    start = start or (end - timedelta(days=500))
    frames = []
    errors = []
    for security_type in ("Note", "Bond"):
        try:
            frames.append(_from_treasurydirect(security_type, start, end))
        except (SourceUnavailable, requests.RequestException) as exc:
            errors.append(str(exc))
    if frames and any(len(frame) for frame in frames):
        combined = pd.concat(frames, ignore_index=True)
        combined = combined.drop_duplicates(subset=["cusip", "auction_date", "security_term"])
        return combined.sort_values("auction_date").reset_index(drop=True)
    try:
        fallback = _from_fiscal_data(start)
    except (SourceUnavailable, requests.RequestException) as exc:
        detail = "; ".join(errors) or "no TreasuryDirect rows"
        raise SourceUnavailable(f"Treasury auctions are unavailable. {detail}. Fallback: {exc}.") from exc
    if fallback.empty:
        raise SourceUnavailable("Treasury returned auctions, but none had a yield and a bid-to-cover ratio.")
    return fallback.sort_values("auction_date").reset_index(drop=True)
