"""Read side of the canonical panel: universe return matrices and state variables."""
import json
import os
from dataclasses import dataclass
from functools import lru_cache

import numpy as np
import pandas as pd

from lifecycle.config import processed_dir
from lifecycle.data.series import OPTIONAL_TOLERANCE_MONTHS, SERIES, UNIVERSES


def synthetic_mode() -> bool:
    return os.environ.get("LIFECYCLE_SYNTHETIC", "") == "1"


@lru_cache(maxsize=1)
def _load() -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    if synthetic_mode():
        from lifecycle.data.synthetic import synthetic_panel

        return synthetic_panel()
    out = processed_dir()
    path = out / "panel.parquet"
    if not path.exists():
        raise FileNotFoundError("panel not built: run `make data` (public) or `make ingest-wrds`")
    panel = pd.read_parquet(path)
    panel["month_end"] = pd.to_datetime(panel["month_end"])
    catalog = pd.read_parquet(out / "series_catalog.parquet")
    meta = json.loads((out / "panel_meta.json").read_text())
    return panel, catalog, meta


def reload() -> None:
    _load.cache_clear()
    universe_data.cache_clear()


def panel() -> pd.DataFrame:
    return _load()[0]


def catalog() -> pd.DataFrame:
    return _load()[1]


def meta() -> dict:
    return _load()[2]


def catalog_hash() -> str:
    return str(meta()["catalog_hash"])


def series(series_id: str) -> pd.Series:
    p = panel()
    sub = p[p["series_id"] == series_id]
    if len(sub) == 0:
        raise KeyError("series not in panel: " + series_id)
    return pd.Series(sub["value"].to_numpy(), index=pd.DatetimeIndex(sub["month_end"]), name=series_id).sort_index()


def has_series(series_id: str) -> bool:
    return bool((panel()["series_id"] == series_id).any())


def wide(series_ids: list[str]) -> pd.DataFrame:
    cols = {}
    for sid in series_ids:
        if has_series(sid):
            cols[sid] = series(sid)
    return pd.DataFrame(cols).sort_index()


@dataclass(frozen=True)
class UniverseData:
    name: str
    assets: tuple[str, ...]
    nominal: pd.DataFrame        # month_end x assets, nominal total returns
    inflation: pd.Series         # month_end, CPI NSA monthly inflation
    real: pd.DataFrame           # (1+R)/(1+pi) - 1
    start: pd.Timestamp
    end: pd.Timestamp
    excluded: dict               # optional series left out, with reason
    n_dropped_months: int
    catalog_hash: str

    def real_array(self) -> np.ndarray:
        return self.real.to_numpy(dtype=np.float64)


@lru_cache(maxsize=32)
def universe_data(name: str, start: str | None = None, end: str | None = None) -> UniverseData:
    if name not in UNIVERSES:
        raise KeyError("unknown universe: " + name)
    u = UNIVERSES[name]
    needed = list(u.required) + [u.inflation]
    missing = [s for s in needed if not has_series(s)]
    if len(missing) > 0:
        raise RuntimeError("universe " + name + " is missing required series: " + ", ".join(missing))
    req = wide(needed)
    first = max(req[c].first_valid_index() for c in req.columns)
    last = min(req[c].last_valid_index() for c in req.columns)
    if start is not None:
        first = max(first, pd.Timestamp(start) + pd.offsets.MonthEnd(0))
    if end is not None:
        last = min(last, pd.Timestamp(end) + pd.offsets.MonthEnd(0))
    assets = list(u.required)
    excluded = {}
    for sid in u.optional:
        if not has_series(sid):
            excluded[sid] = "not in panel"
            continue
        s = series(sid)
        s0 = s.first_valid_index()
        s1 = s.last_valid_index()
        slack = (s0.to_period("M") - first.to_period("M")).n
        if slack > OPTIONAL_TOLERANCE_MONTHS:
            excluded[sid] = "starts " + s0.date().isoformat() + " after window start " + first.date().isoformat()
            continue
        if s1 < last:
            excluded[sid] = "ends " + s1.date().isoformat() + " before window end"
            continue
        inside = s.loc[first:last].dropna()
        gaps = (last.to_period("M") - first.to_period("M")).n + 1 - len(inside)
        if gaps > 0:
            excluded[sid] = str(gaps) + " missing months inside the window"
            continue
        assets.append(sid)
    frame = wide(assets + [u.inflation]).loc[first:last]
    n_before = len(frame)
    frame = frame.dropna()  # months with any gap are dropped, never filled
    nominal = frame[assets]
    infl = frame[u.inflation]
    real = (1.0 + nominal).div(1.0 + infl, axis=0) - 1.0
    return UniverseData(name=name, assets=tuple(assets), nominal=nominal, inflation=infl, real=real,
                        start=frame.index[0], end=frame.index[-1], excluded=excluded,
                        n_dropped_months=int(n_before - len(frame)), catalog_hash=catalog_hash())


def asset_label(series_id: str) -> str:
    s = SERIES.get(series_id)
    return s.label if s else series_id


def defensive(series_id: str) -> bool:
    s = SERIES.get(series_id)
    return bool(s.defensive) if s else False


def as_of() -> str:
    cat = catalog()
    inv = cat[cat["series_id"].isin(["us_eq", "ust_10y", "tbill", "cpi_nsa"])]
    if len(inv) == 0:
        return str(cat["last_obs"].max())
    return str(inv["last_obs"].min())
