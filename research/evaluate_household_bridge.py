"""Evaluate survey-calibrated budget templates on independent common market paths."""
import hashlib
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
from numba import set_num_threads
from scipy.stats import norm

from household_budget_engine import run_budget
from lifecycle.data import panel
from lifecycle.engine.scenarios import generate
from lifecycle.engine.scenarios.bootstrap import StationaryBootstrap
from lifecycle.studies import common as S

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"research/integrated_handoff_2026_11_20"
EQ_GRID=np.arange(0,1.001,.2)


def weights(equity,cash=0):
    return np.array([(1-cash)*equity,cash,(1-cash)*(1-equity)])


def wilson_lower(p,n,z):
    return (p+z*z/(2*n)-z*np.sqrt(p*(1-p)/n+z*z/(4*n*n)))/(1+z*z/n)


def evaluate(dataset):
    os.environ["LIFECYCLE_DATA_DIR"]=str(ROOT/"data"/("wrds_validation" if dataset=="wrds" else ""))
    panel.reload()
    templates=pd.read_csv(OUT/"household_templates.csv")
    u=panel.universe_data("core_long_history","1953-05-01","2024-12-31")
    assert u.assets==("us_eq","tbill","ust_10y")
    model=StationaryBootstrap(u.real_array(),u.inflation.to_numpy(),block_length=12)
    training=generate(model,u.assets,2000,120,920261120).real_returns
    testing=generate(model,u.assets,5000,120,820261120).real_returns
    score_rows=[];selection_rows=[];paired_rows=[]
    z=norm.ppf(1-.05/len(EQ_GRID))
    for _,profile in templates.iterrows():
        initial=profile.cash+profile.taxable_portfolio
        if not initial>0:
            raise ValueError("A mean template has no liquid resources")
        expense=profile.expense_primary
        for horizon in [1,5,10]:
            months=horizon*12
            for scenario in ["income_maintained","compound_stress"]:
                interruption=6 if scenario=="compound_stress" else 0
                losses=np.array([.4,0,.1]) if scenario=="compound_stress" else np.zeros(3)
                reserve_cash=min(3*expense/initial,1)
                base=dict(initial_assets=initial,monthly_outlays=expense,annual_earned=profile.earned_income,
                    annual_other=profile.nonlabor_income,interrupt_months=interruption,initial_losses=losses,
                    half_spread_bps=5,net_fraction=.85)
                candidates=[]
                for equity in EQ_GRID:
                    w=weights(equity,reserve_cash)
                    result=run_budget(training[:,:months],w,**base)
                    funded=result["unmet"]<1e-6
                    joint=funded&(result["terminal"]>=3*expense)
                    p=float(joint.mean())
                    candidates.append(dict(equity=float(equity),joint_success=p,
                        lower=wilson_lower(p,2000,z),mean_unmet=float(result["unmet"].mean()),
                        median_terminal=float(np.median(result["terminal"])),weights=w))
                feasible=[c for c in candidates if c["lower"]>=.9]
                pick=max(feasible,key=lambda x:x["median_terminal"]) if feasible else min(candidates,key=lambda x:(x["mean_unmet"],-x["joint_success"],-x["median_terminal"]))
                choices={"all_cash":weights(0,1),"sixty_forty":weights(.6),
                    "age_glide":weights(np.clip((110-profile.AGE)/100,.3,.9)),
                    "six_month_cash_6040":weights(.6,min(6*expense/initial,1)),
                    "budget_constrained":pick["weights"]}
                selection_rows.append(dict(dataset=dataset,profile_id=profile.profile_id,horizon=horizon,
                    scenario=scenario,feasible_training_grid=bool(feasible),selected_equity=pick["weights"][0],
                    selected_cash=pick["weights"][1],selected_bonds=pick["weights"][2],
                    training_joint_success=pick["joint_success"],training_joint_lower=pick["lower"],
                    selection="highest median terminal resources among jointly qualified candidates; otherwise minimum mean unmet outlays"))
                path_results={}
                for policy,w in choices.items():
                    result=run_budget(testing[:,:months],w,**base)
                    path_results[policy]=result
                    funded=result["unmet"]<1e-6
                    joint=funded&(result["terminal"]>=3*expense)
                    lo,hi=S.wilson(float(funded.mean()),len(funded))
                    joint_lo,joint_hi=S.wilson(float(joint.mean()),len(joint))
                    score_rows.append(dict(dataset=dataset,profile_id=profile.profile_id,age=profile.AGE,
                        horizon=horizon,scenario=scenario,policy=policy,annual_outlays=expense*12,
                        initial_liquid_resources=initial,net_income_annual=.85*profile.recurring_income,
                        equity_weight=w[0],cash_weight=w[1],bond_weight=w[2],
                        outlay_success=float(funded.mean()),success_low=lo,success_high=hi,
                        joint_success=float(joint.mean()),joint_low=joint_lo,joint_high=joint_hi,mean_unmet=float(result["unmet"].mean()),
                        unmet_cvar95=S.cvar(result["unmet"]),median_terminal=float(np.median(result["terminal"])),
                        funded_share=float(result["funded_outlays"].mean()/result["desired_outlays"]),
                        mean_cost=float(result["cost"].mean()),catalog_hash=panel.catalog_hash()))
                benchmark=path_results["age_glide"]
                for policy,result in path_results.items():
                    for metric,delta in [("outlay_success",(result["unmet"]<1e-6).astype(float)-(benchmark["unmet"]<1e-6)),
                                         ("mean_unmet",result["unmet"]-benchmark["unmet"])]:
                        point=float(delta.mean());se=float(delta.std(ddof=1)/np.sqrt(len(delta)))
                        paired_rows.append(dict(dataset=dataset,profile_id=profile.profile_id,horizon=horizon,scenario=scenario,
                            policy=policy,benchmark="age_glide",metric=metric,estimate=point,low=point-1.96*se,high=point+1.96*se,
                            uncertainty="Paired conditional Monte Carlo interval; excludes household and return-model estimation uncertainty"))
        pd.DataFrame(score_rows).to_csv(OUT/(dataset+"_household_policy_scores.csv"),index=False)
        pd.DataFrame(selection_rows).to_csv(OUT/(dataset+"_household_rule_selection.csv"),index=False)
        pd.DataFrame(paired_rows).to_csv(OUT/(dataset+"_household_paired_differences.csv"),index=False)
        print("Household templates evaluated",dataset,profile.profile_id,flush=True)
    (OUT/(dataset+"_market_metadata.json")).write_text(json.dumps(dict(catalog_hash=panel.catalog_hash(),
        universe=u.name,assets=u.assets,start=str(u.start.date()),end=str(u.end.date()),months=len(u.real),
        training_paths=2000,evaluation_paths=5000,training_seed=920261120,evaluation_seed=820261120,
        block_months=12,selection_confidence="one-sided 95% Bonferroni-Wilson across six training candidates",
        prospective_status="Conditional forward scenarios calibrated to 2025 household budgets and historical market data; not historical trading using future household observations",
        income_status="Frozen real earned/nonlabor income except the stated six-month interruption; not estimated retirement or career dynamics",
        script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()),indent=2),encoding="utf-8")


if __name__=="__main__":
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument("--dataset",choices=["public","wrds"],required=True)
    args=parser.parse_args()
    set_num_threads(4)
    evaluate(args.dataset)
