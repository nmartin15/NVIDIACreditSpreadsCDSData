"""Hit each public source once, save the raw body, and print field names.

Run this before writing a parser. It does not map responses into dashboard
columns. Missing credentials are reported and skipped; one failed source
does not stop the others.

    python scripts/probe_sources.py
"""

from __future__ import annotations

import csv
import io
import json
import os
import sys
import traceback
import zipfile
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import requests
import yfinance as yf
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "samples"
TIMEOUT = 90
USER_AGENT = "ai-credit-watch-probe/0.1 (educational; source discovery)"


def section(title: str) -> None:
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


def redact_url(url: str) -> str:
    parts = urlparse(url)
    query = []
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        if key.lower() in {"api_key", "apikey", "access_token", "client_secret"}:
            value = "***"
        query.append((key, value))
    return urlunparse(parts._replace(query=urlencode(query)))


def save_bytes(name: str, data: bytes) -> Path:
    SAMPLES.mkdir(parents=True, exist_ok=True)
    path = SAMPLES / name
    path.write_bytes(data)
    print(f"  saved {path.relative_to(ROOT)} ({len(data)} bytes)")
    return path


def save_text(name: str, text: str) -> Path:
    return save_bytes(name, text.encode("utf-8"))


def save_json(name: str, payload: object) -> Path:
    return save_text(name, json.dumps(payload, indent=2, default=str))


def describe(payload: object, label: str) -> None:
    print(f"  {label}: {type(payload).__name__}")
    if isinstance(payload, dict):
        print(f"  keys ({len(payload)}): {list(payload)}")
    elif isinstance(payload, list):
        print(f"  rows: {len(payload)}")
        if payload and isinstance(payload[0], dict):
            print(f"  record keys ({len(payload[0])}): {list(payload[0])}")
        elif payload:
            print(f"  first item type: {type(payload[0]).__name__}")


def request(method: str, url: str, **kwargs: object) -> requests.Response:
    kwargs.setdefault("timeout", TIMEOUT)
    headers = {"User-Agent": USER_AGENT}
    extra = kwargs.pop("headers", None)
    if isinstance(extra, dict):
        headers.update(extra)
    print(f"  {method.upper()} {redact_url(url)}")
    response = requests.request(method, url, headers=headers, **kwargs)
    content_type = response.headers.get("content-type", "")
    print(
        f"  status {response.status_code} "
        f"content-type {content_type} bytes {len(response.content)}"
    )
    return response


def loads_json(response: requests.Response) -> object:
    try:
        return response.json()
    except ValueError:
        return None


def probe_fred() -> None:
    section("FRED")
    key = os.getenv("FRED_API_KEY", "").strip()
    if not key:
        print("  SKIP: FRED_API_KEY is empty. Copy .env.example to .env and add a key.")
        return

    start = (date.today() - timedelta(days=21)).isoformat()
    for series_id in ("DGS10", "BAMLC0A0CM"):
        print(f"\n  series {series_id}")
        response = request(
            "GET",
            "https://api.stlouisfed.org/fred/series/observations",
            params={
                "series_id": series_id,
                "api_key": key,
                "file_type": "json",
                "observation_start": start,
            },
        )
        payload = loads_json(response)
        save_text(
            f"fred_{series_id.lower()}.json",
            response.text if payload is None else json.dumps(payload, indent=2),
        )
        if payload is None:
            print(f"  body is not JSON. first 400 chars:\n{response.text[:400]}")
            continue
        describe(payload, "root")
        observations = payload.get("observations") if isinstance(payload, dict) else None
        if isinstance(observations, list):
            print(f"  observations: {len(observations)}")
            if observations and isinstance(observations[0], dict):
                print(f"  observation keys: {list(observations[0])}")
                print(f"  first observation: {observations[0]}")
                print(f"  last observation: {observations[-1]}")


def _print_treasury_body(name: str, response: requests.Response) -> None:
    payload = loads_json(response)
    if payload is None:
        save_text(name + ".txt", response.text[:20000])
        print(f"  body is not JSON. first 400 chars:\n{response.text[:400]}")
        return
    save_json(name + ".json", payload)
    describe(payload, "root")
    if isinstance(payload, list) and payload and isinstance(payload[0], dict):
        interesting = [
            key
            for key in payload[0]
            if any(
                token in key.lower()
                for token in (
                    "cusip",
                    "term",
                    "auction",
                    "yield",
                    "bid",
                    "cover",
                    "accept",
                    "dealer",
                    "direct",
                    "indirect",
                    "reopen",
                    "security",
                )
            )
        ]
        print(f"  keys matching auction fields: {interesting}")


def probe_treasury() -> None:
    section("TreasuryDirect")
    end = date.today()
    start = end - timedelta(days=45)
    calls = [
        (
            "treasury_auctioned_note",
            "https://www.treasurydirect.gov/TA_WS/securities/auctioned",
            {"format": "json", "type": "Note", "days": "30", "pagesize": "3"},
        ),
        (
            "treasury_auctioned_bond",
            "https://www.treasurydirect.gov/TA_WS/securities/auctioned",
            {"format": "json", "type": "Bond", "days": "120", "pagesize": "3"},
        ),
        (
            "treasury_search_note",
            "https://www.treasurydirect.gov/TA_WS/securities/search",
            {
                "format": "json",
                "type": "Note",
                "startDate": start.isoformat(),
                "endDate": end.isoformat(),
            },
        ),
        (
            "treasury_search_note_datefield",
            "https://www.treasurydirect.gov/TA_WS/securities/search",
            {
                "format": "json",
                "type": "Note",
                "startDate": start.isoformat(),
                "endDate": end.isoformat(),
                "dateFieldName": "auctionDate",
            },
        ),
    ]
    for name, url, params in calls:
        print(f"\n  {name}")
        try:
            response = request("GET", url, params=params)
            _print_treasury_body(name, response)
        except Exception as exc:
            print(f"  FAILED {name}: {exc}")

    section("Treasury Fiscal Data fallback")
    print("\n  auctions_query page size 2")
    try:
        response = request(
            "GET",
            "https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/od/auctions_query",
            params={"page[size]": "2", "sort": "-auction_date"},
        )
        _print_treasury_body("treasury_fiscaldata_auctions", response)
    except Exception as exc:
        print(f"  FAILED fiscal data: {exc}")


def _finra_field_names(metadata: object) -> list[str]:
    names: list[str] = []
    if not isinstance(metadata, dict):
        return names
    for key in ("fields", "dataset", "schema", "columns"):
        block = metadata.get(key)
        if isinstance(block, list):
            for item in block:
                if isinstance(item, dict):
                    for candidate in ("name", "fieldName", "field", "id"):
                        if isinstance(item.get(candidate), str):
                            names.append(item[candidate])
                            break
                elif isinstance(item, str):
                    names.append(item)
        elif isinstance(block, dict):
            nested = block.get("fields") or block.get("columns")
            if isinstance(nested, list):
                return _finra_field_names({key: nested})
    return names


def _looks_like_trade_tape(field_names: list[str]) -> bool:
    folded = [name.lower() for name in field_names]
    has_id = any("cusip" in name or "isin" in name for name in folded)
    has_price = any("price" in name or "yield" in name for name in folded)
    has_trade = any(
        token in name
        for name in folded
        for token in ("trade", "execut", "transact", "print")
    )
    return has_id and has_price and has_trade


def probe_finra() -> None:
    section("FINRA")
    client_id = os.getenv("FINRA_CLIENT_ID", "").strip()
    client_secret = os.getenv("FINRA_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        print(
            "  SKIP auth: FINRA_CLIENT_ID or FINRA_CLIENT_SECRET is empty. "
            "A public catalog list is still attempted without a token."
        )
        token = None
    else:
        token_response = request(
            "POST",
            "https://ews.fpg.finra.org/fip/rest/ews/oauth2/access_token",
            params={"grant_type": "client_credentials"},
            auth=(client_id, client_secret),
            data={"grant_type": "client_credentials"},
        )
        token_body = loads_json(token_response)
        if isinstance(token_body, dict):
            redacted = {
                key: ("***" if "token" in key.lower() or "secret" in key.lower() else value)
                for key, value in token_body.items()
            }
            save_json("finra_token.json", redacted)
            describe(token_body, "token response")
            token = token_body.get("access_token")
            if not isinstance(token, str) or not token:
                print("  no access_token field in the token response")
                token = None
        else:
            save_text("finra_token.txt", token_response.text[:4000])
            print(f"  token body is not JSON. first 400 chars:\n{token_response.text[:400]}")
            token = None

    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    print("\n  dataset catalog")
    catalog_response = request(
        "GET",
        "https://api.finra.org/datasets",
        params={"group": "fixedIncomeMarket"},
        headers=headers,
    )
    catalog = loads_json(catalog_response)
    if catalog is None:
        save_text("finra_datasets.txt", catalog_response.text[:20000])
        print(f"  catalog is not JSON. first 400 chars:\n{catalog_response.text[:400]}")
        return
    save_json("finra_datasets_fixedIncomeMarket.json", catalog)
    describe(catalog, "catalog")

    datasets: list[dict] = []
    if isinstance(catalog, list):
        datasets = [item for item in catalog if isinstance(item, dict)]
    elif isinstance(catalog, dict):
        for key in ("datasets", "data", "items", "results"):
            block = catalog.get(key)
            if isinstance(block, list):
                datasets = [item for item in block if isinstance(item, dict)]
                print(f"  dataset list is under key {key!r} ({len(datasets)} rows)")
                break
        if not datasets:
            print("  could not find a list of datasets. top-level keys printed above.")

    names: list[str] = []
    for item in datasets:
        for key in ("name", "dataset", "datasetName", "id"):
            if isinstance(item.get(key), str):
                names.append(item[key])
                break
    print(f"  dataset names ({len(names)}): {names}")
    if datasets:
        print(f"  catalog record keys: {list(datasets[0])}")

    trade_like: list[str] = []
    summary_rows: list[dict] = []
    for name in names:
        print(f"\n  metadata {name}")
        meta_response = request(
            "GET",
            f"https://api.finra.org/metadata/group/fixedIncomeMarket/name/{name}",
            headers=headers,
        )
        metadata = loads_json(meta_response)
        if metadata is None:
            save_text(f"finra_metadata_{name}.txt", meta_response.text[:20000])
            print("  metadata is not JSON")
            continue
        save_json(f"finra_metadata_{name}.json", metadata)
        fields = _finra_field_names(metadata)
        if not fields and isinstance(metadata, dict):
            describe(metadata, "metadata root")
        else:
            print(f"  fields ({len(fields)}): {fields}")
        is_trade = _looks_like_trade_tape(fields)
        if is_trade:
            trade_like.append(name)
        summary_rows.append(
            {"dataset": name, "field_count": len(fields), "trade_tape_shape": is_trade}
        )

        print(f"  sample rows {name}")
        data_response = request(
            "GET",
            f"https://api.finra.org/data/group/fixedIncomeMarket/name/{name}",
            params={"limit": "2"},
            headers=headers,
        )
        data_payload = loads_json(data_response)
        if data_payload is None:
            save_text(f"finra_sample_{name}.txt", data_response.text[:20000])
            first_line = data_response.text.splitlines()[0] if data_response.text else ""
            print(f"  sample is not JSON. first line: {first_line[:300]}")
        else:
            save_json(f"finra_sample_{name}.json", data_payload)
            describe(data_payload, "sample")

    save_json("finra_trade_tape_scan.json", summary_rows)
    print("\n  FINRA trade-tape scan")
    if not names:
        print("  INCONCLUSIVE: the catalog response did not yield dataset names.")
    elif trade_like:
        print(f"  POSSIBLE per-CUSIP trade datasets: {trade_like}")
    else:
        print(
            "  NO per-CUSIP trade tape in the datasets returned for group "
            "fixedIncomeMarket. None of the metadata field lists contained a "
            "CUSIP or ISIN together with a price or yield and a trade/execution field."
        )


def _csv_preview(text: str, limit_rows: int = 3) -> tuple[list[str], int, list[list[str]]]:
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    if not rows:
        return [], 0, []
    header = rows[0]
    body = rows[1:]
    return header, len(body), body[:limit_rows]


def probe_dtcc() -> None:
    section("DTCC SEC credit cumulative slice")
    print(
        "  The SEC dashboard calls /ppd/api/general/bucketname, then loads "
        "Cumulative.json from https://{bucket}.s3.amazonaws.com/dashboard/."
    )
    bucket_response = request("GET", "https://pddata.dtcc.com/ppd/api/general/bucketname")
    bucket = bucket_response.text.strip().strip('"')
    save_text("dtcc_bucketname.txt", bucket_response.text)
    if bucket_response.status_code != 200 or not bucket or " " in bucket or "/" in bucket:
        print(f"  bucket name response is not usable: {bucket_response.text[:200]!r}")
        return
    print(f"  bucket: {bucket}")
    index_url = f"https://{bucket}.s3.amazonaws.com/dashboard/Cumulative.json"
    response = request("GET", index_url)
    payload = loads_json(response)
    if not isinstance(payload, dict):
        save_text("dtcc_cumulative_index.txt", response.text[:20000])
        print("  cumulative index is not a JSON object")
        return
    save_json("dtcc_cumulative_index.json", payload)
    print(f"  index keys: {list(payload)}")
    records = payload.get("SEC_CR")
    if not isinstance(records, list) or not records:
        print("  SEC_CR is missing or empty. No file downloaded.")
        return
    first = records[0]
    describe(records, "SEC_CR")
    if isinstance(first, dict):
        print(f"  latest record: {json.dumps(first)}")
    file_url = first.get("fullFilePath") if isinstance(first, dict) else None
    file_name = first.get("fileName") if isinstance(first, dict) else None
    if not isinstance(file_url, str) or not file_url:
        print("  latest SEC_CR record has no fullFilePath. Not guessing a URL.")
        return
    print(f"  downloading {file_name} from fullFilePath")
    file_response = request("GET", file_url)
    zip_name = file_name if isinstance(file_name, str) and file_name.endswith(".zip") else "dtcc_sec_credit.zip"
    save_bytes(zip_name, file_response.content)
    try:
        with zipfile.ZipFile(io.BytesIO(file_response.content)) as archive:
            print(f"  zip members: {archive.namelist()}")
            csv_members = [name for name in archive.namelist() if name.lower().endswith(".csv")]
            if not csv_members:
                print("  zip has no CSV member")
                return
            member = csv_members[0]
            raw = archive.read(member)
            text = raw.decode("utf-8-sig", errors="replace")
            save_text(Path(member).name, text)
            header, row_count, preview = _csv_preview(text)
            print(f"  csv {member}: {row_count} data rows, {len(header)} columns")
            print(f"  columns: {header}")
            for row in preview:
                print(f"  row: {row}")
    except zipfile.BadZipFile:
        print("  downloaded body is not a zip. first 200 bytes saved with the response above.")


def probe_equities() -> None:
    section("yfinance")
    ticker = yf.Ticker("NVDA")
    history = ticker.history(period="5d", auto_adjust=False)
    print(f"  history rows: {len(history)}")
    print(f"  columns: {list(history.columns)}")
    print(f"  index name: {history.index.name}")
    if len(history):
        print(f"  first index: {history.index[0]}")
        print(f"  last index: {history.index[-1]}")
    save_text("yfinance_nvda_5d.csv", history.to_csv())


def main() -> int:
    load_dotenv(ROOT / ".env")
    SAMPLES.mkdir(parents=True, exist_ok=True)
    print(f"samples directory: {SAMPLES}")
    probes = (probe_fred, probe_treasury, probe_finra, probe_dtcc, probe_equities)
    failed = 0
    for probe in probes:
        try:
            probe()
        except Exception as exc:
            failed += 1
            section(f"{probe.__name__} FAILED")
            print(f"  {type(exc).__name__}: {exc}")
            traceback.print_exc()
    section("done")
    print(f"  probes that raised: {failed} of {len(probes)}")
    print("  raw bodies are in samples/ and are gitignored.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
