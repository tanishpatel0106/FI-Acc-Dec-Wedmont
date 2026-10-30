"""Model-generated total returns from public yields (used only when WRDS returns are absent).

A yield is never used as a return: each month the constant-maturity par bond bought at
last month's yield is repriced at this month's yield one month closer to maturity.
Rows carry provenance=model_generated so the catalog and UI flag them.
"""
import numpy as np
import pandas as pd

from lifecycle.data.schema import finalize_rows


def par_bond_month_return(y0: float, y1: float, maturity_years: float, freq: int = 2) -> float:
    """One-month total return of a par bond (coupon y0, maturity M) repriced at y1 with M - 1/12 left.

    Returned as dirty price - 1, so accrued coupon income is included.
    """
    n = maturity_years * freq - freq / 12.0
    whole = int(np.floor(n + 1e-12))
    frac = n - whole
    if frac > 1e-9:
        times = frac + np.arange(whole + 1, dtype=float)
    else:
        times = np.arange(1, whole + 1, dtype=float)
    disc = (1.0 + y1 / freq) ** (-times)
    dirty = float(np.sum((y0 / freq) * disc) + disc[-1])
    return dirty - 1.0


def par_bond_returns(yields: pd.Series, maturity_years: float) -> pd.Series:
    out = {}
    idx = yields.index
    for i in range(1, len(idx)):
        if (idx[i].to_period("M") - idx[i - 1].to_period("M")).n != 1:
            continue
        y0 = float(yields.iloc[i - 1])
        y1 = float(yields.iloc[i])
        if not (np.isfinite(y0) and np.isfinite(y1)):
            continue
        out[idx[i]] = par_bond_month_return(y0, y1, maturity_years)
    return pd.Series(out, dtype=float)


MODELS = [
    # (yield series, maturity, target series, real?)
    ("y_dgs2", 2.0, "ust_2y", False),
    ("y_dgs5", 5.0, "ust_5y", False),
    ("y_dgs10", 10.0, "ust_10y", False),
    ("y_dgs20", 20.0, "ust_20y", False),
    ("y_dgs30", 30.0, "ust_30y", False),
    ("y_aaa", 10.0, "ig_credit", False),
    ("y_dfii10", 10.0, "tips", True),
]


def build_public_models(panel: pd.DataFrame) -> pd.DataFrame:
    rows = []
    cpi = panel[panel["series_id"] == "cpi_nsa"].set_index("month_end")["value"].sort_index()
    cpi = cpi[~cpi.index.duplicated()]
    for ysid, maturity, target, real in MODELS:
        y = panel[panel["series_id"] == ysid].set_index("month_end")["value"].sort_index()
        y = y[~y.index.duplicated()]
        if len(y) < 13:
            continue
        rets = par_bond_returns(y, maturity)
        for ts, v in rets.items():
            value = float(v)
            if real:
                if ts not in cpi.index:
                    continue
                value = (1.0 + value) * (1.0 + float(cpi.loc[ts])) - 1.0
            rows.append({"month_end": ts, "series_id": target, "value": value, "quantity": "total_return",
                         "provenance": "model_generated",
                         "source": "model:par_bond(" + ysid + "," + str(maturity) + "y" +
                                   (",real+cpi" if real else "") + ")"})
    return finalize_rows(rows)
