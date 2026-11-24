"""Optional observed ETF validation data from Yahoo Finance daily adjusted prices.

IEF remains a distinct 7-10Y ETF series. It never replaces the modelled constant-maturity 10Y bond.
Only completed months are retained. Daily adjusted closes include distribution/split adjustments.
The raw response, retrieval URL and SHA-256 are retained for reproducibility.
"""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pandas as pd

from lifecycle.config import raw_dir
from lifecycle.data.normalize import build_panel, write_raw
from lifecycle.data.schema import finalize_rows

FUNDS = {"IEF": "ust_7_10_etf", "GLD": "gold"}


def monthly_returns(document: dict, cutoff: str) -> pd.Series:
    result = document["chart"]["result"][0]
    dates = pd.to_datetime(result["timestamp"], unit="s", utc=True).tz_convert("America/New_York").tz_localize(None)
    prices = pd.Series(result["indicators"]["adjclose"][0]["adjclose"], index=dates).dropna()
    closes = prices.resample("ME").last().loc[:cutoff]
    # The first partial fund month supplies the initial price, so its return is omitted.
    return closes.pct_change(fill_method=None).dropna()


def ingest(cutoff: str = "2026-09-30") -> dict:
    reports = []
    folder = raw_dir() / "yahoo_responses"
    folder.mkdir(exist_ok=True)
    for ticker, series_id in FUNDS.items():
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
        response = httpx.get(url, params={"range": "max", "interval": "1d", "events": "div,splits"},
                             headers={"User-Agent": "Mozilla/5.0"}, timeout=60, follow_redirects=True)
        response.raise_for_status()
        document = response.json()
        values = monthly_returns(document, cutoff)
        if values.empty or (values <= -1).any():
            raise ValueError(f"Invalid adjusted-price returns for {ticker}")
        retrieved = datetime.now(timezone.utc).isoformat()
        (folder / f"{ticker}.json").write_bytes(response.content)
        report = {"ticker": ticker, "series_id": series_id, "url": str(response.url),
                  "retrieved_at": retrieved, "sha256": hashlib.sha256(response.content).hexdigest(),
                  "first_month": str(values.index[0].date()), "last_month": str(values.index[-1].date()),
                  "months": len(values), "definition": "monthly change in month-end daily adjusted close"}
        reports.append(report)
        rows = [{"month_end": d, "series_id": series_id, "value": v, "quantity": "total_return",
                 "provenance": "observed", "source": f"public:yahoo.adjusted_close.{ticker}"}
                for d, v in values.items()]
        write_raw(finalize_rows(rows), "public_etfs", ticker)
    (folder / "manifest.json").write_text(json.dumps(reports, indent=2), encoding="utf-8")
    return {"sources": reports, "panel": build_panel()}


def ingest_snapshot(path: Path) -> dict:
    """Restore the frozen monthly return observations used by the delivered report."""
    frame = pd.read_csv(path, parse_dates=["month_end", "vintage", "available_from"], float_precision="round_trip")
    if set(frame["series_id"]) != set(FUNDS.values()):
        raise ValueError("The ETF snapshot must contain exactly IEF and GLD series")
    for ticker, series_id in FUNDS.items():
        rows = frame[frame["series_id"] == series_id]
        if not rows["source"].eq(f"public:yahoo.adjusted_close.{ticker}").all():
            raise ValueError(f"Unexpected source for {ticker}")
        write_raw(finalize_rows(rows.to_dict("records")), "public_etfs", ticker)
    return {"snapshot_sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "panel": build_panel()}


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path)
    args = parser.parse_args()
    result = ingest_snapshot(args.snapshot) if args.snapshot else ingest()
    print(json.dumps(result, indent=2, default=str))
