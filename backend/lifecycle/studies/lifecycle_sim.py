"""Multi-asset lifecycle simulation from a dated start (Interactive Lifecycle Simulator, multi-asset engine).

An investor starts at a chosen date and age (e.g. 20 years old in January 2007) and is simulated to the final
age with state-dependent, multi-asset policies executed by the holdings ledger, every path recomputing its
targets every month. Two scenario sources:

  * ``simulated_from_start``: no hindsight. Market estimates, the regime model and the bootstrap sample use only
    information available at the start date; every path starts from the initial wealth.
  * ``history_then_simulated``: the investor lives through actual history from the start date to the last
    observation (the point-in-time replay engine), then continues on bootstrap paths from the exact realised
    holdings.

Unlike the equity/bond simulator kernel, allocations span every eligible asset class (equity regions, nominal
and real Treasuries, credit, currencies, gold and commodities when ingested, cash) and change with the
investor's state and market signals. Research output, not advice.
"""
from typing import Any

import numpy as np
import pandas as pd
from pydantic import Field

from lifecycle.studies import common as S
from lifecycle.studies import historical_replay as H


class LifecycleSimSpec(S.Frozen):
    start: str = "2007-01"
    scenario_source: str = Field("simulated_from_start", pattern="^(simulated_from_start|history_then_simulated)$")
    investor: H.ReplayInvestor = Field(default_factory=H.ReplayInvestor)
    preferences: S.StudyPrefs = Field(default_factory=S.StudyPrefs)
    costs: S.StudyCosts = Field(default_factory=lambda: S.StudyCosts(commission_bps=1, half_spread_bps=2))
    rebalance: H.ReplayRebalance = Field(default_factory=H.ReplayRebalance)
    policies: tuple[str, ...] = ("pp_lifecycle", "lifecycle_adaptive", "target_date", "sixty_forty")
    universe_mode: str = Field("fixed", pattern="^(fixed|expanding)$")
    candidates: tuple[str, ...] = H.CANDIDATES
    n_paths: int = Field(1000, ge=50, le=5000)
    block_months: int = Field(12, ge=1, le=60)
    min_history_months: int = Field(36, ge=12, le=240)
    estimation_window_months: int | None = Field(120, ge=24, le=600)
    seed: int = 20261108
    label: str | None = None


def _replay_spec(spec: LifecycleSimSpec, end: str | None) -> H.HistoricalReplaySpec:
    return H.HistoricalReplaySpec(start=spec.start, end=end, universe_mode=spec.universe_mode, candidates=spec.candidates,
                                  investor=spec.investor, preferences=spec.preferences, costs=spec.costs,
                                  rebalance=spec.rebalance, policies=spec.policies, min_history_months=spec.min_history_months,
                                  estimation_window_months=spec.estimation_window_months, forward_paths=spec.n_paths,
                                  forward_block_months=spec.block_months, seed=spec.seed, experiments=False)


def run_lifecycle_sim(spec: LifecycleSimSpec, progress: S.Progress) -> dict[str, Any]:
    unknown = [p for p in spec.policies if p not in H.POLICIES]
    if unknown:
        raise ValueError("unknown policies: " + ", ".join(unknown))
    progress("loading_history", 0.02)
    inv = spec.investor
    out: dict[str, Any] = {"scenario_source": spec.scenario_source, "start": spec.start, "investor": inv.model_dump(),
                           "policies": {}, "labels": {p: H.POLICIES[p][1] for p in spec.policies}}
    if spec.scenario_source == "simulated_from_start":
        rs = _replay_spec(spec, spec.start)
        start = pd.Timestamp(spec.start + "-01") + pd.offsets.MonthEnd(0)
        # information set: everything published before the start date; the start month itself is the first decision
        h = H.load_history(rs.model_copy(update={"start": (start - pd.offsets.MonthEnd(1)).strftime("%Y-%m"),
                                                   "end": spec.start}))
        snaps = H.market_snapshots(rs, h)
        snap = snaps[-1]
        keep = [c for c in snap["eligible"] if c == "tbill" or snap["history_months"].get(c, 0) >= rs.forward_min_sample_months]
        short = [c for c in snap["eligible"] if c not in keep]
        snap = H.restrict(snap, keep)
        cand = list(h.R.columns)
        as_of = h.dates[-1] - pd.offsets.MonthEnd(1)
        lia = H.liabilities(inv, inv.start_age, inv.salary, snap["real_rate"])
        st = {"age": inv.start_age, "wealth": inv.initial_wealth, "salary": inv.salary,
              "years_to_retirement": max(inv.retirement_age - inv.start_age, 0.0), "human_capital": lia["human_capital"],
              "pv_liabilities": lia["pv_liabilities"], "liability_duration": lia["liability_duration"],
              "funding_ratio": (inv.initial_wealth + lia["human_capital"]) / max(lia["pv_liabilities"], 1.0)}
        out.update({"information_until": str(as_of.date()), "eligible": snap["eligible"], "excluded_short_history": short, "candidates": cand,
                    "not_ingested": h.not_ingested, "history": None})
        for k, pol in enumerate(spec.policies):
            tg = H.target(pol, snap, st, rs)
            if tg is None:
                out["policies"][pol] = {"available": False, "reason": H.unavailable_reason(pol, h, rs)}
                continue
            hold = H._full(tg["final"], snap["eligible"], cand) * inv.initial_wealth
            f = H.forward(rs, h, cand, pol, spec.seed, snap, hold, inv.salary, age0=inv.start_age, as_of=as_of)
            out["policies"][pol] = {"available": True, "initial_target": dict(zip(cand, np.round(hold / max(inv.initial_wealth, 1e-9), 4).tolist())),
                                    "forward": f, "notes": H._jsonable(tg["notes"])}
            progress("simulated %s" % pol, 0.1 + 0.85 * (k + 1) / len(spec.policies))
    else:
        rs = _replay_spec(spec, None)
        h = H.load_history(rs)
        base = H.replay(rs, h, list(spec.policies), progress)
        cand = base["candidates"]
        last = base["snaps"][-1] if base["fixed_set"] is None else H.restrict(base["snaps"][-1], base["fixed_set"])
        out.update({"information_until": str(h.dates[-1].date()), "eligible": last["eligible"], "candidates": cand,
                    "not_ingested": h.not_ingested, "history": {"dates": [str(d.date()) for d in h.dates]}})
        for k, pol in enumerate(spec.policies):
            rp = base["policies"][pol]
            if not rp.get("available"):
                out["policies"][pol] = {"available": False, "reason": rp.get("reason")}
                continue
            stt = rp.pop("_state")
            f = H.forward(rs, h, cand, pol, spec.seed, last, stt["holdings"], stt["salary"])
            ser = rp["series"]
            out["policies"][pol] = {"available": True, "forward": f,
                                    "history": {"wealth_real": ser["wealth_real"], "w_post": ser["w_post"],
                                                "ages": [round(inv.start_age + (t + 1) / 12, 3) for t in range(len(ser["wealth"]))],
                                                "final_wealth": rp["final_wealth"], "max_drawdown": rp["max_drawdown"],
                                                "n_rebalances": rp["n_rebalances"], "total_costs": rp["total_costs"]}}
            progress("continued %s" % pol, 0.7 + 0.25 * (k + 1) / len(spec.policies))
    out["block_of"] = {c: H.BLOCK_OF.get(H.SERIES[c].asset_class if c in H.SERIES else "other", "real") for c in out["candidates"]}
    out["warnings"] = ["Treasury, TIPS and investment-grade returns are repriced from public yields (model-generated); IG credit has no default losses"]
    if out["not_ingested"]:
        out["warnings"].append("not ingested (WRDS-only, never proxied): " + ", ".join(out["not_ingested"]))
    out["definitions"] = {"dollars": "real dollars of the information date",
                          "paths": "block bootstrap of joint real returns and CPI from the information set; policies recompute targets every month on every path"}
    return out
