"""Series catalog: coverage, units, provenance, licence class and content hashes."""
import hashlib
import json

import pandas as pd

from lifecycle.data.series import SERIES


def content_hash(values: pd.Series, index: pd.Series) -> str:
    h = hashlib.sha256()
    h.update(pd.to_datetime(index).astype("int64").to_numpy().tobytes())
    h.update(values.astype("float64").round(12).to_numpy().tobytes())
    return h.hexdigest()[:16]


def build_catalog(resolved: pd.DataFrame) -> pd.DataFrame:
    """One row per resolved (series_id, source)."""
    rows = []
    for (sid, source), grp in resolved.groupby(["series_id", "source"], sort=True):
        grp = grp.sort_values("month_end")
        first = grp["month_end"].iloc[0]
        last = grp["month_end"].iloc[-1]
        expected = (last.to_period("M") - first.to_period("M")).n + 1
        sdef = SERIES.get(sid)
        rows.append({
            "series_id": sid,
            "label": sdef.label if sdef else sid,
            "asset_class": sdef.asset_class if sdef else "other",
            "units": sdef.units if sdef else "",
            "frequency": "monthly",
            "quantity": str(grp["quantity"].iloc[0]),
            "provenance": str(grp["provenance"].iloc[0]),
            "source": source,
            "licence_class": "wrds_restricted" if str(source).startswith("wrds:") else "public",
            "first_obs": first.date().isoformat(),
            "last_obs": last.date().isoformat(),
            "n_obs": int(len(grp)),
            "n_missing": int(expected - len(grp)),
            "vintage": pd.to_datetime(grp["vintage"]).max().date().isoformat(),
            "content_hash": content_hash(grp["value"], grp["month_end"]),
        })
    return pd.DataFrame(rows)


def catalog_hash(catalog: pd.DataFrame) -> str:
    payload = []
    for i in range(len(catalog)):
        payload.append([catalog["series_id"].iloc[i], catalog["source"].iloc[i], catalog["content_hash"].iloc[i]])
    return hashlib.sha256(json.dumps(sorted(payload)).encode()).hexdigest()[:16]
