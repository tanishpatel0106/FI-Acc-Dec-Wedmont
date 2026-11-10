"""US Treasury daily par yield curves (nominal and real), from the official public CSV endpoint.

These are *daily observations of yields*, kept in a separate daily store (data/raw/treasury_daily) for the
market-state terminal. They never enter the monthly backtest panel and are never used as returns.
Each download is written under its retrieval date, so a refresh adds a new vintage instead of overwriting.
"""
import io
import json
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd

from lifecycle.config import raw_dir

BASE = ("https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/"
        "{year}/all?type={kind}&field_tdr_date_value={year}&page&_format=csv")
KINDS = {"nominal": "daily_treasury_yield_curve", "real": "daily_treasury_real_yield_curve"}
TENOR_YEARS = {"1 Mo": 1 / 12, "1.5 Month": 1.5 / 12, "2 Mo": 2 / 12, "3 Mo": 0.25, "4 Mo": 4 / 12, "6 Mo": 0.5,
               "1 Yr": 1, "2 Yr": 2, "3 Yr": 3, "5 Yr": 5, "7 Yr": 7, "10 Yr": 10, "20 Yr": 20, "30 Yr": 30,
               "5 YR": 5, "7 YR": 7, "10 YR": 10, "20 YR": 20, "30 YR": 30}


def store_dir() -> Path:
    p = raw_dir() / "treasury_daily"
    p.mkdir(parents=True, exist_ok=True)
    return p


def pull_treasury_daily(years: tuple[int, ...] | None = None) -> dict:
    from lifecycle.data.http import fetch

    years = years or (date.today().year - 1, date.today().year)
    frames = {}
    log = {"retrieved_at": datetime.now(timezone.utc).isoformat(), "attempts": []}
    for kind, code in KINDS.items():
        parts = []
        for y in years:
            url = BASE.format(year=y, kind=code)
            try:
                path = fetch(url, "treasury_%s_%d.csv" % (kind, y), refresh=True)
                df = pd.read_csv(io.StringIO(path.read_text()))
                parts.append(df)
                log["attempts"].append({"kind": kind, "year": y, "status": "ok", "rows": int(len(df))})
            except Exception as exc:
                log["attempts"].append({"kind": kind, "year": y, "status": "failed", "error": str(exc)[:300]})
        if parts:
            df = pd.concat(parts, ignore_index=True)
            df["Date"] = pd.to_datetime(df["Date"])
            frames[kind] = df.drop_duplicates("Date").sort_values("Date")
    folder = store_dir() / date.today().isoformat()
    folder.mkdir(parents=True, exist_ok=True)
    for kind, df in frames.items():
        df.to_parquet(folder / (kind + ".parquet"), index=False)
    (folder / "refresh_log.json").write_text(json.dumps(log, indent=2))
    return log


def latest() -> dict:
    """Most recent stored daily curves (or an explicit 'not ingested' marker)."""
    root = store_dir()
    vintages = sorted([p for p in root.iterdir() if p.is_dir()])
    for v in reversed(vintages):
        out: dict = {"vintage": v.name, "curves": {}}
        for kind in KINDS:
            f = v / (kind + ".parquet")
            if f.exists():
                df = pd.read_parquet(f)
                row = df.iloc[-1]
                tenors = [(TENOR_YEARS[c], float(row[c]) / 100) for c in df.columns
                          if c in TENOR_YEARS and pd.notna(row[c])]
                tenors.sort()
                out["curves"][kind] = {"observation_date": pd.Timestamp(row["Date"]).date().isoformat(),
                                       "tenors": [t for t, _ in tenors], "par_yield": [y for _, y in tenors],
                                       "n_days": int(len(df))}
        log = v / "refresh_log.json"
        out["refresh_log"] = json.loads(log.read_text()) if log.exists() else None
        if out["curves"]:
            return out
    return {"vintage": None, "curves": {}, "refresh_log": None,
            "status": "not ingested: run `python -m lifecycle.cli market-refresh` (needs network access to "
                      "home.treasury.gov)"}
