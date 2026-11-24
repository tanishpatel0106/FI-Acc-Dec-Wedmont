"""Exploratory robustness extension; licensed observations never enter exported artifacts."""
import argparse
import hashlib
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
from numba import set_num_threads

from lifecycle.data import panel
from lifecycle.engine.scenarios import ScenarioTensor, generate
from lifecycle.engine.scenarios.bootstrap import StationaryBootstrap
from lifecycle.engine.scenarios.student_t import MultivariateT
from lifecycle.runs import context as C
from lifecycle.studies import common as S
from lifecycle.studies.signed_flow import DEFAULT_Q

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "research/wrds_validation_2026_11_19/robustness"
OUT.mkdir(exist_ok=True)
COMPACT_Q = np.array([-.05, -.02, 0, .02, .04, .06])
FULL_Q = np.array(DEFAULT_Q)
ALPHAS = np.array([0, .25, .5, .75, 1.])
SEEDS = [20261119, 20261120, 20261121, 20261122, 20261123]


def save(name, obj):
    (OUT / name).write_text(json.dumps(obj, indent=2, default=str), encoding="utf-8")


def setup(dataset):
    os.environ["LIFECYCLE_DATA_DIR"] = str(ROOT / "data" / ("wrds_validation" if dataset == "wrds" else ""))
    panel.reload()
    C._MODELS.clear()
    C._TENSORS.clear()


def context(tensor, start, end, seed, horizon):
    es = S.experiment_spec(S.StudyData(universe="core_long_history", calibration_start=start, calibration_end=end),
        S.StudyScenario(n_paths=max(100, tensor.n_paths), n_train_paths=100, seed=seed, k_regimes=1),
        S.StudyInvestor(age=65, horizon_years=horizon))
    return S.get_context(es, tensor, seed)


def tensor_from_history(u, n, months, seed, generator="bootstrap", block=None):
    model = (StationaryBootstrap(u.real_array(), u.inflation.to_numpy(), block_length=block)
             if generator == "bootstrap" else MultivariateT(u.real_array(), u.inflation.to_numpy()))
    return generate(model, u.assets, n, months, seed), model


def grid(tensor, start, end, seed, horizons, qs, bs, cost=0, resources_only=False):
    result = {"resources": np.empty((len(horizons), len(qs), len(bs), tensor.n_paths))}
    if not resources_only:
        result.update(terminal=np.empty_like(result["resources"]), unmet=np.empty_like(result["resources"]),
                      success=np.empty(result["resources"].shape, dtype=bool))
    trading = S.strategy("calendar_12m", S.StudyCosts(half_spread_bps=cost))
    for hi, horizon in enumerate(horizons):
        ctx = context(tensor.head(horizon*12), start, end, seed, horizon)
        for qi, q in enumerate(qs):
            for bi, b in enumerate(bs):
                weights = S.weights_vector({"us_eq": 1-b, "ust_10y": b}, tensor.assets)
                out = S.run(ctx, weights, trading, spend="signed", q=float(q), zero_income=True)
                result["resources"][hi, qi, bi] = out.terminal+out.funded
                if not resources_only:
                    result["terminal"][hi, qi, bi] = out.terminal
                    result["unmet"][hi, qi, bi] = out.unmet
                    result["success"][hi, qi, bi] = out.first_shortfall < 0
    return result


def ce(values, gamma=4, floor=1000):
    x = np.maximum(values, floor)/1e6
    return (np.exp(np.log(x).mean(axis=-1)) if gamma == 1 else
            (x**(1-gamma)).mean(axis=-1)**(1/(1-gamma)))*1e6


def chosen(array, indices):
    return array[np.arange(indices.shape[0])[:, None], np.arange(indices.shape[1])[None, :], indices]


def fit_policies(train, bs, hweights, gamma=4, floor=1000):
    """Tune shrinkage on A2, refit allocations on A1+A2; evaluation paths never enter."""
    nh, nq = train.shape[:2]

    def fit(values):
        scores = ce(values, gamma, floor)
        relative = scores/scores.max(axis=2, keepdims=True)
        full = scores.argmax(axis=2)
        restricted = np.repeat(relative.mean(axis=1).argmax(axis=1)[:, None], nq, axis=1)
        qonly = np.repeat(np.sum(relative*hweights[:, None, None], axis=0).argmax(axis=1)[None, :], nh, axis=0)
        return full, restricted, qonly

    split = train.shape[-1]//2
    first_full, first_restricted, _ = fit(train[..., :split])
    validation = ce(train[..., split:], gamma, floor)
    normalizer = validation.max(axis=2)
    candidates = []
    for alpha in ALPHAS:
        bond = bs[first_restricted]+alpha*(bs[first_full]-bs[first_restricted])
        indices = np.abs(bond[..., None]-bs).argmin(axis=-1)
        candidates.append(float(np.sum((chosen(validation, indices)/normalizer).mean(axis=1)*hweights)))
    alpha = float(ALPHAS[np.argmax(candidates)])
    full, restricted, qonly = fit(train)
    bond = bs[restricted]+alpha*(bs[full]-bs[restricted])
    shrink = np.abs(bond[..., None]-bs).argmin(axis=-1)
    return {"full": full, "horizon_only": restricted, "flow_only": qonly, "validated_shrinkage": shrink,
            "sixty_forty": np.full((nh, nq), np.abs(bs-.4).argmin(), dtype=int)}, alpha


def evaluate(test, policies, hweights, qs, gamma=4, floor=1000):
    scores = ce(test["resources"], gamma, floor)
    terminal = ce(test["terminal"], gamma, floor)
    reference = chosen(scores, policies["horizon_only"])
    terminal_ref = chosen(terminal, policies["horizon_only"])
    draw = np.asarray(qs)>0
    base_success = chosen(test["success"], policies["horizon_only"]).mean(axis=-1)
    rows = []
    for name, indices in policies.items():
        resources = chosen(scores, indices)
        success = chosen(test["success"], indices).mean(axis=-1)
        unmet = chosen(test["unmet"], indices)
        tails = np.apply_along_axis(S.cvar, -1, unmet)
        rows.append({"policy": name,
            "relative_resources_ce": float(np.sum((resources/reference-1).mean(axis=1)*hweights)),
            "relative_terminal_ce": float(np.sum((chosen(terminal, indices)/terminal_ref-1).mean(axis=1)*hweights)),
            "withdrawal_success": float(np.sum(success[:, draw].mean(axis=1)*hweights)),
            "success_difference_pp": float(np.sum((success[:, draw]-base_success[:, draw]).mean(axis=1)*hweights)*100),
            "withdrawal_unmet_mean": float(np.sum(unmet[:, draw].mean(axis=(-1, -2))*hweights)),
            "mean_cell_unmet_cvar95": float(np.sum(tails[:, draw].mean(axis=1)*hweights))})
    return rows


def sensitivity():
    setup("wrds")
    u = panel.universe_data("core_long_history", "1953-01-01", "2024-12-31")
    configs = [(s, "bootstrap", None, 0, .1) for s in SEEDS]
    configs += [(s, "bootstrap", b, 0, .1) for b in [1, 6, 12, 24] for s in SEEDS[:3]]
    configs += [(s, "bootstrap", None, 5, .1) for s in SEEDS[:3]]
    configs += [(s, "student_t", None, 0, .1) for s in SEEDS[:3]]
    configs += [(s, "bootstrap", None, 0, .05) for s in SEEDS[:3]]
    rows, allocations = [], []
    for seed, generator, block, cost, step in configs:
        bs = np.round(np.arange(0, 1+step/2, step), 4)
        data = S.StudyData(universe="core_long_history", calibration_start="1953-01-01", calibration_end="2024-12-31")
        es = S.experiment_spec(data, S.StudyScenario(n_paths=10000, n_train_paths=4000, seed=seed, k_regimes=1),
                               S.StudyInvestor(age=65, horizon_years=20))
        trainseed = C.train_seed(es)
        train_tensor, model = tensor_from_history(u, 4000, 240, trainseed, generator, block)
        test_tensor, _ = tensor_from_history(u, 10000, 240, seed, generator, block)
        train = grid(train_tensor, "1953-01-01", "2024-12-31", trainseed, [10, 20], FULL_Q, bs, cost, True)["resources"]
        test = grid(test_tensor, "1953-01-01", "2024-12-31", seed, [10, 20], FULL_Q, bs, cost)
        settings = [(4, 1000, "original_age_weights", "full")]
        if generator == "bootstrap" and block is None and cost == 0 and step == .1:
            settings += [(g, 1000, "original_age_weights", "full") for g in [2, 6, 8]]
            settings += [(4, f, "original_age_weights", "full") for f in [100, 10000]]
            settings += [(4, 1000, "equal_effective_horizons", "full"), (4, 1000, "original_age_weights", "compact")]
        for gamma, floor, weighting, flowset in settings:
            qidx = np.arange(len(FULL_Q)) if flowset == "full" else np.array([np.flatnonzero(np.isclose(FULL_Q, q))[0] for q in COMPACT_Q])
            tr = train[:, qidx]
            te = {k: v[:, qidx] for k, v in test.items()}
            qs = FULL_Q[qidx]
            hw = np.array([1/7, 6/7]) if weighting == "original_age_weights" else np.array([.5, .5])
            policies, alpha = fit_policies(tr, bs, hw, gamma, floor)
            common = dict(seed=seed, generator=generator, requested_block=block,
                fitted_block=model.block_length if generator == "bootstrap" else None,
                cost_half_spread_bps=cost, bond_step=step, gamma=gamma, resource_floor=floor,
                weighting=weighting, flow_grid=flowset, selected_alpha=alpha, catalog_hash=panel.catalog_hash())
            for row in evaluate(te, policies, hw, qs, gamma, floor):
                rows.append({**common, **row})
            if gamma == 4 and floor == 1000 and weighting == "original_age_weights" and flowset == "full":
                for policy, indices in policies.items():
                    for hi, horizon in enumerate([10, 20]):
                        for qi, q in enumerate(qs):
                            allocations.append({**common, "policy": policy, "horizon": horizon,
                                "q": q, "bond_share": bs[indices[hi, qi]]})
            if seed == SEEDS[0] and generator == "bootstrap" and block is None and cost == 0 and step == .1 and flowset == "full" and gamma == 4 and floor == 1000:
                cache = ROOT / "data/wrds_validation/robustness_cache"
                cache.mkdir(exist_ok=True)
                np.savez_compressed(cache / "reference_grid.npz", train=train,
                    test_ce=ce(test["resources"]), bs=bs, catalog_hash=panel.catalog_hash())
        pd.DataFrame(rows).to_csv(OUT / "sensitivity_scores.csv", index=False)
        pd.DataFrame(allocations).to_csv(OUT / "allocation_stability.csv", index=False)
        print("sensitivity completed", seed, generator, block, cost, step, flush=True)
    save("sensitivity_metadata.json", {"configurations": len(configs), "training_paths": 4000,
        "validation_split": "first 2000 A1, last 2000 A2; refit on 4000, score on disjoint 10000 B",
        "test_paths": 10000, "horizons": [10, 20], "q_grid": FULL_Q.tolist(),
        "original_age_weights": [1/7, 6/7], "equal_effective_horizon_weights": [.5, .5],
        "alpha_grid": ALPHAS.tolist(), "inference": "descriptive configuration sensitivity; seeds share historical data"})


def nonoverlap(dataset):
    setup(dataset)
    bs = np.round(np.arange(0, 1.001, .05), 4)
    horizons = [5, 10, 20]
    rows = []
    periods = {h: [(y, y+h-1) for y in range(1980, 2025-h+1, h)] for h in horizons}
    for h, spans in periods.items():
        assert all(a[1]<b[0] for a, b in zip(spans, spans[1:]))
    for year in range(1980, 2021, 5):
        active = [h for h in horizons if any(start==year for start, end in periods[h])]
        if not active:
            continue
        end = f"{year-1}-12-31"
        u = panel.universe_data("core_long_history", "1953-05-01", end)
        training, _ = tensor_from_history(u, 4000, 240, 810000+year, block=None)
        train = grid(training, "1953-05-01", end, 810000+year, horizons, COMPACT_Q, bs, 5, True)["resources"]
        policies, alpha = fit_policies(train, bs, np.ones(3)/3)
        for horizon in active:
            hi = horizons.index(horizon)
            hist = panel.universe_data("core_long_history", f"{year}-01-01", f"{year+horizon-1}-12-31")
            assert len(hist.real) == horizon*12
            ten = ScenarioTensor(hist.assets, hist.real_array()[None, :, :], hist.inflation.to_numpy()[None, :],
                                  np.zeros((1, horizon*12), dtype=np.int64), 1)
            ctx = context(ten, f"{year}-01-01", f"{year+horizon-1}-12-31", 0, horizon)
            for qi, q in enumerate(COMPACT_Q):
                for policy, indices in policies.items():
                    b = bs[indices[hi, qi]]
                    out = S.run(ctx, S.weights_vector({"us_eq": 1-b, "ust_10y": b}, hist.assets),
                        S.strategy("calendar_12m", S.StudyCosts(half_spread_bps=5)),
                        spend="signed", q=float(q), zero_income=True)
                    rows.append(dict(dataset=dataset, horizon=horizon, start_year=year, end_year=year+horizon-1,
                        train_start="1953-05-01", train_end=end, q=q, policy=policy, bond_share=b,
                        alpha=alpha, terminal=float(out.terminal[0]), resources=float(out.terminal[0]+out.funded[0]),
                        success=bool(out.first_shortfall[0]<0), unmet=float(out.unmet[0]),
                        catalog_hash=panel.catalog_hash()))
        pd.DataFrame(rows).to_csv(OUT / (dataset+"_nonoverlap.csv"), index=False)
        print("nonoverlap completed", dataset, year, active, flush=True)
    save(dataset+"_nonoverlap_metadata.json", {"periods": periods, "training_paths": 4000,
        "alpha_grid": ALPHAS.tolist(), "half_spread_bps": 5, "gamma": 4, "floor": 1000,
        "training_horizon_weighting": "equal over 5/10/20 years, unique horizon cells",
        "catalog_hash": panel.catalog_hash(), "inference": "no overlapping return months within each horizon; serial dependence can remain; no pooled IID inference"})


def refit(n_boot=100):
    setup("wrds")
    cache = np.load(ROOT / "data/wrds_validation/robustness_cache/reference_grid.npz")
    assert str(cache["catalog_hash"]) == panel.catalog_hash()
    test_ce, bs = cache["test_ce"], cache["bs"]
    u = panel.universe_data("core_long_history", "1953-01-01", "2024-12-31")
    outer = StationaryBootstrap(u.real_array(), u.inflation.to_numpy(), block_length=12)
    rows, allocations = [], []
    hw = np.array([1/7, 6/7])
    for iteration in range(n_boot):
        rr, ii, _ = outer.simulate(1, len(u.real), np.random.default_rng(920000+iteration), None)
        fitted = StationaryBootstrap(rr[0], ii[0], block_length=12)
        training = generate(fitted, u.assets, 2000, 240, 813773)
        values = grid(training, "1953-01-01", "2024-12-31", 813773, [10, 20], FULL_Q, bs, 0, True)["resources"]
        policies, alpha = fit_policies(values, bs, hw)
        reference = chosen(test_ce, policies["horizon_only"])
        for name in ["full", "flow_only", "validated_shrinkage"]:
            score = float(np.sum((chosen(test_ce, policies[name])/reference-1).mean(axis=1)*hw))
            rows.append(dict(iteration=iteration, policy=name, relative_resources_ce=score, alpha=alpha))
            for hi, horizon in enumerate([10, 20]):
                for qi, q in enumerate(FULL_Q):
                    allocations.append(dict(iteration=iteration, policy=name, horizon=horizon, q=q,
                                            bond_share=bs[policies[name][hi, qi]]))
        pd.DataFrame(rows).to_csv(OUT / "history_refit_scores.csv", index=False)
        if (iteration+1)%10 == 0:
            print("history refits completed", iteration+1, flush=True)
    pd.DataFrame(allocations).to_csv(OUT / "history_refit_allocations.csv", index=False)
    save("history_refit_metadata.json", {"repetitions": n_boot, "outer_block_months": 12,
        "inner_block_months": 12, "training_paths_per_refit": 2000, "reference_future_paths": 10000,
        "common_inner_seed": 813773, "catalog_hash": panel.catalog_hash(),
        "interpretation": "refit dispersion conditional on one fixed reference future model and finite inner simulation; not a general confidence interval or independent external validation"})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=["sensitivity", "nonoverlap", "refit"], required=True)
    parser.add_argument("--dataset", choices=["wrds", "public"], default="wrds")
    parser.add_argument("--refits", type=int, default=100)
    args = parser.parse_args()
    set_num_threads(4)
    if args.stage == "sensitivity":
        sensitivity()
    elif args.stage == "nonoverlap":
        nonoverlap(args.dataset)
    else:
        refit(args.refits)
    save(args.stage+"_"+args.dataset+"_identity.json", {
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "design_sha256": hashlib.sha256((OUT / "design.json").read_bytes()).hexdigest(),
        "catalog_hash": panel.catalog_hash(), "engine_version": __import__("lifecycle.config", fromlist=["engine_version"]).engine_version()})


if __name__ == "__main__":
    main()
