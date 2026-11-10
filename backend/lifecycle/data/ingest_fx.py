"""Public currency sleeve: carry-inclusive returns of foreign overnight deposits for a US-dollar investor.

Sources (FRED, public): daily H.10 spot rates (DEX*) sampled at the last business day of each complete month,
and OECD immediate call-money rates (IRSTCI01*M156N, monthly averages). One rate definition is used for every
currency so no incompatible rate series are combined; a currency whose rate series is stale (CHF stops in
2024) is excluded rather than spliced.

    r_t = (S_t / S_{t-1}) * (1 + i_{t-1} / 12) - 1        S = USD per unit of foreign currency

i_{t-1} is the previous month's average call-money rate (known when the deposit is placed). `fx_basket` is the
equal-weight monthly-rebalanced basket over months where every component has both spot and rate; the
individual currency returns are stored too. Returns are `index_derived` (computed from observed inputs).
"""
import pandas as pd

from lifecycle.data.http import complete_months
from lifecycle.data.ingest_fred import _download_all
from lifecycle.data.schema import finalize_rows

# currency -> (spot FRED id, quoted as foreign-per-USD?, call-money FRED id)
CURRENCIES = {
    "gbp": ("DEXUSUK", False, "IRSTCI01GBM156N"),
    "jpy": ("DEXJPUS", True, "IRSTCI01JPM156N"),
    "cad": ("DEXCAUS", True, "IRSTCI01CAM156N"),
    "aud": ("DEXUSAL", False, "IRSTCI01AUM156N"),
}
BASKET = tuple(CURRENCIES)


def fx_returns(spot_usd_per_fx: pd.Series, rate_annual: pd.Series) -> pd.Series:
    """Monthly total return of a foreign overnight deposit in USD (month-end spot, lagged monthly-average rate)."""
    s = spot_usd_per_fx.sort_index()
    i = rate_annual.sort_index().reindex(s.index)
    r = s / s.shift(1) * (1.0 + i.shift(1) / 12.0) - 1.0
    months = s.index.to_period("M")
    consecutive = pd.Series((months[1:] - months[:-1]).map(lambda d: d.n) == 1, index=s.index[1:])
    r = r.iloc[1:][consecutive.values]
    return r.dropna()


def pull_fx() -> pd.DataFrame:
    ids = [v[0] for v in CURRENCIES.values()] + [v[2] for v in CURRENCIES.values()]
    raw = _download_all(ids)
    rows = []
    rets: dict[str, pd.Series] = {}
    for ccy, (spot_id, invert, rate_id) in CURRENCIES.items():
        spot, rate = raw[spot_id], raw[rate_id]
        if isinstance(spot, Exception) or isinstance(rate, Exception):
            print("warning: FX", ccy, "failed:", spot if isinstance(spot, Exception) else rate)
            continue
        cutoff = complete_months(spot.index)
        m = spot.resample("ME").last().dropna()
        m = m[m.index <= cutoff]
        usd_per = 1.0 / m if invert else m
        rate_m = (rate / 100.0).copy()
        rate_m.index = rate_m.index + pd.offsets.MonthEnd(0)
        for ts, v in usd_per.items():
            rows.append({"month_end": ts, "series_id": "fxs_" + ccy, "value": float(v), "quantity": "index_level",
                         "provenance": "observed", "source": "fred:" + spot_id + (":inverted" if invert else ""),
                         "available_from": ts + pd.Timedelta(days=1)})
        for ts, v in rate_m.items():
            rows.append({"month_end": ts, "series_id": "y_cm_" + ccy, "value": float(v), "quantity": "yield",
                         "provenance": "observed", "source": "fred:" + rate_id,
                         "available_from": ts + pd.Timedelta(days=45)})
        r = fx_returns(usd_per, rate_m)
        rets[ccy] = r
        for ts, v in r.items():
            rows.append({"month_end": ts, "series_id": "fx_" + ccy, "value": float(v), "quantity": "total_return",
                         "provenance": "index_derived", "source": "derived:fx_deposit(" + spot_id + "," + rate_id + ")",
                         "available_from": ts})   # a realised deposit return: known to the holder at month end
    if all(c in rets for c in BASKET):
        frame = pd.concat([rets[c] for c in BASKET], axis=1, join="inner")
        basket = frame.mean(axis=1)
        for ts, v in basket.items():
            rows.append({"month_end": ts, "series_id": "fx_basket", "value": float(v), "quantity": "total_return",
                         "provenance": "index_derived",
                         "source": "derived:fx_basket(equal-weight " + ",".join(c.upper() for c in BASKET) +
                                   "; H.10 month-end spot; OECD call money)",
                         "available_from": ts})
    else:
        print("warning: fx_basket not built (missing components:", [c for c in BASKET if c not in rets], ")")
    return finalize_rows(rows)
