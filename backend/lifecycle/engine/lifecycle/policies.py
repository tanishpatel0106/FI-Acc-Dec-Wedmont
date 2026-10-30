"""Weight-policy builders: constant mix, glidepaths, target-date, regime-dependent, parametric, bucket."""
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

GROWTH_CLASSES = ("us_eq", "intl_eq", "em_eq", "reit", "gold", "hy_credit")


def risky_mask(assets: tuple[str, ...]) -> NDArray[np.float64]:
    return np.array([1.0 if a in GROWTH_CLASSES else 0.0 for a in assets])


def vector(weights: dict[str, float], assets: tuple[str, ...]) -> NDArray[np.float64]:
    w = np.zeros(len(assets))
    for k, v in weights.items():
        if k not in assets:
            raise ValueError("weight given for asset outside the universe: " + k)
        w[assets.index(k)] = float(v)
    if np.any(w < -1e-12):
        raise ValueError("long-only: negative weight")
    s = w.sum()
    if s <= 0:
        raise ValueError("weights sum to zero")
    return w / s


def default_sleeves(assets: tuple[str, ...]) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Growth sleeve and defensive sleeve compositions used by glidepaths and parametric policies."""
    growth = {"us_eq": 0.6, "intl_eq": 0.3, "em_eq": 0.1}
    safe = {"ust_10y": 0.5, "tips": 0.3, "ig_credit": 0.2}
    g = {k: v for k, v in growth.items() if k in assets}
    s = {k: v for k, v in safe.items() if k in assets}
    if len(s) == 0:
        s = {"ust_10y": 1.0}
    return vector(g, assets), vector(s, assets)


def target_date_equity(age: NDArray[np.float64]) -> NDArray[np.float64]:
    """Industry-style glidepath: 90% to 40, 50% at 65, 30% from 75."""
    return np.interp(age, [0, 40, 65, 75, 200], [0.9, 0.9, 0.5, 0.3, 0.3])


@dataclass
class WeightPolicy:
    wmode: int
    sched: NDArray[np.float64]
    risky_w: NDArray[np.float64]
    safe_w: NDArray[np.float64]
    theta: NDArray[np.float64]
    bucket_years: float
    label: str


def constant_mix(w: NDArray[np.float64], months: int, label: str = "constant mix") -> WeightPolicy:
    sched = np.broadcast_to(w, (months, 1, len(w))).copy()
    return WeightPolicy(0, sched, w.copy(), w.copy(), np.zeros(4), 0.0, label)


def glidepath(share: NDArray[np.float64], risky_w: NDArray[np.float64], safe_w: NDArray[np.float64],
              label: str) -> WeightPolicy:
    sched = (share[:, None] * risky_w[None, :] + (1 - share[:, None]) * safe_w[None, :])[:, None, :]
    return WeightPolicy(0, sched, risky_w, safe_w, np.zeros(4), 0.0, label)


def linear_glidepath(start_age: float, months: int, theta0: float, theta1: float, risky_w: NDArray[np.float64],
                     safe_w: NDArray[np.float64], ref_age: float = 65.0) -> WeightPolicy:
    ages = start_age + np.arange(months) / 12.0
    share = np.clip(theta0 + theta1 * (ages - ref_age) / 10.0, 0, 1)
    return glidepath(share, risky_w, safe_w, "glidepath(%.2f, %.2f)" % (theta0, theta1))


def target_date(start_age: float, months: int, risky_w: NDArray[np.float64],
                safe_w: NDArray[np.float64]) -> WeightPolicy:
    ages = start_age + np.arange(months) / 12.0
    return glidepath(target_date_equity(ages), risky_w, safe_w, "target-date glidepath")


def regime_dependent(per_regime: NDArray[np.float64], months: int) -> WeightPolicy:
    K, A = per_regime.shape
    sched = np.broadcast_to(per_regime, (months, K, A)).copy()
    return WeightPolicy(0, sched, per_regime[0], per_regime[-1], np.zeros(4), 0.0, "regime-dependent")


def parametric(theta: NDArray[np.float64], risky_w: NDArray[np.float64], safe_w: NDArray[np.float64],
               months: int) -> WeightPolicy:
    sched = np.broadcast_to(0.5 * risky_w + 0.5 * safe_w, (months, 1, len(risky_w))).copy()
    return WeightPolicy(1, sched, risky_w, safe_w, np.asarray(theta, dtype=float), 0.0, "parametric")


def bucket(years: float, risky_w: NDArray[np.float64], safe_w: NDArray[np.float64], start_age: float,
           months: int) -> WeightPolicy:
    pre = target_date(start_age, months, risky_w, safe_w)
    return WeightPolicy(2, pre.sched, risky_w, safe_w, np.zeros(4), float(years),
                        "liability-matched bucket (%g y)" % years)
