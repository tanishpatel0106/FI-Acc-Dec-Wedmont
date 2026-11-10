"""Synthetic fixtures for CI and tests. Never used for research output (flagged model_generated)."""
import numpy as np
import pandas as pd

from lifecycle.data.catalog import build_catalog, catalog_hash
from lifecycle.data.schema import PANEL_COLUMNS

ASSETS = {
    # id: (annual mean, annual vol)
    "us_eq": (0.095, 0.17), "intl_eq": (0.08, 0.18), "em_eq": (0.09, 0.23), "reit": (0.085, 0.20),
    "tbill": (0.035, 0.008), "ust_2y": (0.04, 0.02), "ust_5y": (0.045, 0.045), "ust_10y": (0.05, 0.075),
    "ust_20y": (0.055, 0.10), "ust_30y": (0.056, 0.12), "tips": (0.045, 0.055), "ig_credit": (0.055, 0.065),
    "gold": (0.05, 0.16), "hy_credit": (0.07, 0.10),
}


def synthetic_panel(seed: int = 7, start: str = "1926-01-31", months: int = 1200):
    rng = np.random.default_rng(seed)
    idx = pd.date_range(start, periods=months, freq="ME")
    regime = np.zeros(months, dtype=int)
    for t in range(1, months):
        stay = 0.97 if regime[t - 1] == 0 else 0.92
        regime[t] = regime[t - 1] if rng.random() < stay else 1 - regime[t - 1]
    infl = np.where(regime == 0, 0.0022, 0.0055) + rng.normal(0, 0.003, months)
    common = rng.normal(0, 1, months)
    rows = []
    names = list(ASSETS.keys())
    for k in range(len(names)):
        mu, vol = ASSETS[names[k]]
        load = 0.8 if names[k].endswith("eq") or names[k] == "reit" else (-0.2 if "ust" in names[k] else 0.1)
        if names[k] == "gold":
            load = 0.0
        z = load * common + np.sqrt(1 - load ** 2) * rng.normal(0, 1, months)
        r = mu / 12 + vol / np.sqrt(12) * z - np.where(regime == 1, 0.002, 0.0)
        first = 0 if names[k] in ("us_eq", "tbill", "ust_10y", "ust_2y", "ust_5y", "ust_20y", "ust_30y") else 936
        for t in range(first, months):
            rows.append((idx[t], names[k], float(r[t]), "total_return", "model_generated", "synthetic:" + names[k]))
    for t in range(months):
        rows.append((idx[t], "cpi_nsa", float(infl[t]), "rate", "model_generated", "synthetic:cpi"))
        rows.append((idx[t], "cpi_sa", float(infl[t]), "rate", "model_generated", "synthetic:cpi_sa"))
    level = 0.04 + np.cumsum(rng.normal(0, 0.002, months)).clip(-0.035, 0.08)
    for t in range(420, months):
        for m in range(1, 31):
            y = level[t] + 0.01 * (1 - np.exp(-m / 5.0)) + 0.002 * np.sin(t / 50.0) * np.exp(-m / 3.0)
            rows.append((idx[t], "gsw_nom_%02d" % m, float(y), "yield", "model_generated", "synthetic:gsw"))
        for m in range(2, 21):
            y = level[t] - 0.02 + 0.006 * (1 - np.exp(-m / 5.0))
            rows.append((idx[t], "gsw_real_%02d" % m, float(y), "yield", "model_generated", "synthetic:gsw_real"))
    # extra sleeves drawn from a separate stream so the original fixture series stay bit-identical
    rng2 = np.random.default_rng(seed + 101)
    for sid, (mu, vol, load) in {"fx_basket": (0.03, 0.07, 0.4), "commodities": (0.04, 0.18, 0.3)}.items():
        z = load * common + np.sqrt(1 - load ** 2) * rng2.normal(0, 1, months)
        r = mu / 12 + vol / np.sqrt(12) * z
        for t in range(936, months):
            rows.append((idx[t], sid, float(r[t]), "total_return", "model_generated", "synthetic:" + sid))
    frame = pd.DataFrame(rows, columns=["month_end", "series_id", "value", "quantity", "provenance", "source"])
    frame["vintage"] = pd.Timestamp("2026-01-01")
    frame["available_from"] = frame["month_end"]
    frame = frame[PANEL_COLUMNS]
    cat = build_catalog(frame)
    meta = {"catalog_hash": catalog_hash(cat), "built_at": "synthetic", "choices": {}, "synthetic": True}
    return frame, cat, meta
