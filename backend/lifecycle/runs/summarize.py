"""Turn kernel outputs into the persisted result payload (quantiles only by default)."""
from typing import Any

import numpy as np

from lifecycle.engine.lifecycle.kernel import SimOutput
from lifecycle.engine.lifecycle.simulator import Context
from lifecycle.engine.lifecycle.utility import ce_with_se, paired_delta_ce, path_ce
from lifecycle.engine.optimize.static import cvar

SCALE = 1000.0 * 12.0  # kernel utility units -> annual dollars


def ce_block(out: SimOutput, gamma: float) -> dict[str, float]:
    ce, se = ce_with_se(out.utility, gamma, out.sum_disc)
    return {"ce": ce * SCALE, "se": se * SCALE}


def delta_block(a: SimOutput, b: SimOutput, gamma: float) -> dict[str, float]:
    d, se = paired_delta_ce(a.utility, b.utility, gamma, a.sum_disc)
    z = d / se if se > 0 else (0.0 if d == 0 else float("inf"))
    return {"delta": d, "se": se, "z": z, "significant": bool(abs(d) > 2 * se)}


def quantiles(arr: np.ndarray, qs: tuple[float, ...]) -> dict[str, list[float]]:
    out = {}
    q = np.quantile(arr, qs, axis=0)
    for i in range(len(qs)):
        out["p%02d" % int(round(qs[i] * 100))] = np.atleast_1d(q[i]).tolist()
    out["mean"] = np.atleast_1d(arr.mean(axis=0)).tolist()
    return out


def shortfall_block(out: SimOutput, ctx: Context) -> dict[str, Any]:
    dep = out.deplete_month
    depleted = dep >= 0
    retire_m = ctx.investor.retire_month
    ages_dep = ctx.investor.start_age + dep[depleted] / 12.0
    n_years = out.cons_y.shape[1]
    by_age = []
    for y in range(n_years):
        by_age.append(float(np.mean(depleted & (dep < (y + 1) * 12))))
    res = {"p_depletion": float(depleted.mean()), "p_infeasible": float(out.infeasible.mean()),
           "mean_L": float(out.shortfall.mean()), "cvar95_L": cvar(out.shortfall, 0.95),
           "p_depleted_by_age": by_age, "retire_month": retire_m}
    if depleted.any():
        res["median_depletion_age"] = float(np.median(ages_dep))
        res["depletion_age_quantiles"] = np.quantile(ages_dep, [0.1, 0.25, 0.5, 0.75, 0.9]).tolist()
    else:
        res["median_depletion_age"] = None
    return res


def run_payload(ctx: Context, out: SimOutput, bench: SimOutput | None, qs: tuple[float, ...],
                n_sample: int) -> dict[str, Any]:
    gamma = ctx.prefs.gamma
    n_years = out.cons_y.shape[1]
    ages = (ctx.investor.start_age + np.arange(n_years + 1)).tolist()
    assets = list(ctx.tensor.assets)
    payload: dict[str, Any] = {
        "ages": ages,
        "assets": assets,
        "ce": {"policy": ce_block(out, gamma)},
        "fan": {"wealth": quantiles(out.wealth_y, qs), "consumption": quantiles(out.cons_y, qs)},
        "shortfall": shortfall_block(out, ctx),
        "terminal_wealth": quantiles(out.wealth_y[:, -1], qs),
        "weights_path": {"assets": assets, "mean": out.weights_y.mean(axis=0).tolist()},
        "risky_share": quantiles(out.risky_y, qs),
        "q_path": quantiles(out.q_y, qs),
        "turnover_annual": float(out.turnover.mean() / max(ctx.months / 12.0, 1.0)),
        "survival": ctx.survival[::12].tolist(),
        "n_paths": int(out.utility.shape[0]),
    }
    if bench is not None:
        payload["ce"]["benchmark"] = ce_block(bench, gamma)
        payload["ce"]["delta"] = delta_block(out, bench, gamma)
        payload["fan"]["benchmark_wealth"] = quantiles(bench.wealth_y, qs)
        payload["fan"]["benchmark_consumption"] = quantiles(bench.cons_y, qs)
        payload["benchmark_shortfall"] = shortfall_block(bench, ctx)
    if n_sample > 0:
        k = min(n_sample, out.utility.shape[0])
        pc = path_ce(out.utility[:k], gamma, out.sum_disc) * SCALE
        sample = {"path_ce_policy": pc.tolist(), "depleted_policy": (out.deplete_month[:k] >= 0).tolist()}
        if bench is not None:
            sample["path_ce_benchmark"] = (path_ce(bench.utility[:k], gamma, bench.sum_disc) * SCALE).tolist()
            sample["depleted_benchmark"] = (bench.deplete_month[:k] >= 0).tolist()
        payload["sample"] = sample
    return payload
