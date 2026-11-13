"""DTCC SEC public credit tape.

The dashboard site publishes a bucket name, then a Cumulative.json index.
Each SEC credit day has a `fullFilePath`. This client follows that path.
It does not invent a filename.

The Price, Price notation, and Price currency columns were empty on the
2026-11-12 file. Callers should read Fixed rate-Leg 1, Spread-Leg 1,
Spread notation-Leg 1, and the upfront payment fields instead.
"""

from __future__ import annotations

import io
import re
import zipfile
from datetime import date

import pandas as pd
import requests

from sources import SourceUnavailable

BUCKET_URL = "https://pddata.dtcc.com/ppd/api/general/bucketname"
TIMEOUT = 90
FILE_DATE = re.compile(r"(\d{4})_(\d{2})_(\d{2})")
NEEDED = [
    "Dissemination Identifier",
    "Action type",
    "Event type",
    "Execution Timestamp",
    "Effective Date",
    "Expiration Date",
    "Notional amount-Leg 1",
    "Notional currency-Leg 1",
    "Fixed rate-Leg 1",
    "Spread-Leg 1",
    "Spread notation-Leg 1",
    "Other payment amount",
    "Other payment type",
    "Other payment currency",
    "Underlier ID-Leg 1",
    "Underlier ID source-Leg 1",
    "Underlying Asset Name",
    "UPI FISN",
    "Asset Class",
]


def _session() -> requests.Session:
    http = requests.Session()
    http.headers["User-Agent"] = "ai-credit-watch/0.1 (educational)"
    return http


def _bucket(http: requests.Session) -> str:
    response = http.get(BUCKET_URL, timeout=TIMEOUT)
    if response.status_code != 200:
        raise SourceUnavailable(f"DTCC bucket name returned HTTP {response.status_code}.")
    bucket = response.text.strip().strip('"')
    if not bucket or any(char in bucket for char in " /\\"):
        raise SourceUnavailable(f"DTCC bucket name was not usable: {bucket!r}.")
    return bucket


def _index(http: requests.Session, bucket: str) -> list[dict]:
    response = http.get(
        f"https://{bucket}.s3.amazonaws.com/dashboard/Cumulative.json",
        timeout=TIMEOUT,
    )
    if response.status_code != 200:
        raise SourceUnavailable(f"DTCC cumulative index returned HTTP {response.status_code}.")
    try:
        payload = response.json()
    except ValueError as exc:
        raise SourceUnavailable("DTCC cumulative index was not JSON.") from exc
    records = payload.get("SEC_CR") if isinstance(payload, dict) else None
    if not isinstance(records, list):
        keys = list(payload) if isinstance(payload, dict) else type(payload).__name__
        raise SourceUnavailable(f"DTCC index has no SEC_CR list. Keys: {keys}.")
    return [record for record in records if isinstance(record, dict)]


def _report_day(record: dict) -> date | None:
    name = str(record.get("fileName") or "")
    matched = FILE_DATE.search(name)
    if not matched:
        return None
    return date(int(matched.group(1)), int(matched.group(2)), int(matched.group(3)))


def _read_zip(content: bytes, report_day: date) -> pd.DataFrame:
    try:
        archive = zipfile.ZipFile(io.BytesIO(content))
    except zipfile.BadZipFile as exc:
        raise SourceUnavailable(f"DTCC file for {report_day} was not a zip.") from exc
    members = [name for name in archive.namelist() if name.lower().endswith(".csv")]
    if not members:
        raise SourceUnavailable(f"DTCC zip for {report_day} contained no CSV.")
    frame = pd.read_csv(archive.open(members[0]), dtype=str, keep_default_na=False)
    missing = [column for column in NEEDED if column not in frame.columns]
    if missing:
        raise SourceUnavailable(
            f"DTCC file for {report_day} is missing {missing}. Not guessing replacement columns."
        )
    slim = frame.loc[frame["Asset Class"].str.upper() == "CR", NEEDED].copy()
    slim = slim[slim["UPI FISN"].str.contains("CDS", case=False, na=False)]
    slim.insert(0, "report_date", report_day)
    return slim.rename(
        columns={
            "Dissemination Identifier": "dissemination_id",
            "Action type": "action",
            "Event type": "event_type",
            "Execution Timestamp": "execution_time",
            "Effective Date": "effective_date",
            "Expiration Date": "expiration_date",
            "Notional amount-Leg 1": "notional",
            "Notional currency-Leg 1": "notional_currency",
            "Fixed rate-Leg 1": "fixed_rate",
            "Spread-Leg 1": "spread",
            "Spread notation-Leg 1": "spread_notation",
            "Other payment amount": "payment_amount",
            "Other payment type": "payment_type",
            "Other payment currency": "payment_currency",
            "Underlier ID-Leg 1": "underlier_id",
            "Underlier ID source-Leg 1": "underlier_source",
            "Underlying Asset Name": "asset_name",
            "UPI FISN": "upi_fisn",
            "Asset Class": "asset_class",
        }
    )


def fetch_credit_cds(report_days: int = 10) -> pd.DataFrame:
    """Single-name and index CDS rows from the latest SEC cumulative files.

    Columns: report_date, dissemination_id, action, event_type, execution_time,
    effective_date, expiration_date, notional, notional_currency, fixed_rate,
    spread, spread_notation, payment_amount, payment_type, payment_currency,
    underlier_id, underlier_source, asset_name, upi_fisn, asset_class.

    Text fields stay as reported. `report_date` is the date in the filename.
    """
    http = _session()
    try:
        records = _index(http, _bucket(http))
    except requests.RequestException as exc:
        raise SourceUnavailable(f"DTCC could not be reached. {exc}.") from exc
    dated = []
    for record in records:
        report_day = _report_day(record)
        path = record.get("fullFilePath")
        if report_day is None or not isinstance(path, str) or not path:
            continue
        dated.append((report_day, path))
    chosen = sorted(dated, key=lambda item: item[0], reverse=True)[:report_days]
    if not chosen:
        raise SourceUnavailable("DTCC index had no SEC credit files with a fullFilePath.")
    frames = []
    failures = []
    for report_day, path in chosen:
        try:
            response = http.get(path, timeout=TIMEOUT)
        except requests.RequestException as exc:
            failures.append(f"{report_day}: {exc}")
            continue
        if response.status_code != 200:
            failures.append(f"{report_day}: HTTP {response.status_code}")
            continue
        try:
            frames.append(_read_zip(response.content, report_day))
        except SourceUnavailable as exc:
            failures.append(str(exc))
    if not frames:
        detail = "; ".join(failures) or "no files"
        raise SourceUnavailable(f"DTCC credit files could not be read. {detail}.")
    combined = pd.concat(frames, ignore_index=True)
    combined.attrs["failures"] = failures
    return combined
