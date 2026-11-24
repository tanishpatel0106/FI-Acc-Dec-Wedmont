"""Connect observed SCF willingness with explicit household-budget stress constraints.

Run with the household-analysis Python environment. Export aggregate estimates and calibrated
templates only; no willingness-to-CRRA mapping and no causal interpretation of age contrasts.
"""
import hashlib
import json
import os
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROJECT = Path(os.environ.get("FIXED_INCOME_SURVEY_ROOT", ROOT.parent))
sys.path.insert(0, str(PROJECT / "scripts"))
from age_expense_analysis import load_expenses, fit_many
from capacity_validation import AGE, DEMO
from scf_analysis import Survey

OUT = ROOT / "research/integrated_handoff_2026_11_20"
CACHE = PROJECT / "data/household_bridge_2026_11_20"
OUT.mkdir(exist_ok=True)
CACHE.mkdir(exist_ok=True)
AGE_LABELS = ["20-39", "40-59", "60-74", "75-89"]


def stress_path(frame, expense, equity=.6, equity_loss=.4, bond_loss=.1,
                interrupt_months=6, net_fraction=.85, reserve_months=3, interrupt_nonlabor=False,
                include_market_assets=True):
    """One-year deterministic liquid-budget stress; no borrowing or assumed asset appreciation."""
    e = frame[expense].to_numpy(float)
    total = frame.cash.to_numpy(float)+(frame.taxable_portfolio.to_numpy(float)*(1-equity*equity_loss-(1-equity)*bond_loss) if include_market_assets else 0)
    unmet = np.zeros(len(frame))
    working = frame.earned_income.to_numpy(float)
    other = frame.nonlabor_income.to_numpy(float)
    for month in range(12):
        income = net_fraction*((0 if interrupt_nonlabor and month<interrupt_months else other)+(0 if month<interrupt_months else working))/12
        resources = np.maximum(total+income, 0)
        funded = np.minimum(resources, e)
        unmet += e-funded
        total = resources-funded
    valid = np.isfinite(e) & (e>0) & np.isfinite(total)
    return {"funded": np.where(valid, (unmet<1e-6).astype(float), np.nan),
            "funded_and_reserve": np.where(valid, ((unmet<1e-6)&(total>=reserve_months*e)).astype(float), np.nan),
            "unmet": np.where(valid, unmet, np.nan), "terminal": np.where(valid, total, np.nan)}


def prepare_wave(year):
    d, rw = load_expenses(year)
    d = d.copy()
    required = ["WAGEINC", "BUSSEFARMINC", "SSRETINC", "PENACCTWD", "TRANSFOTHINC", "LIQ", "STOCKS", "BOND", "NMMF"]
    assert all(c in d for c in required)
    d["cash"] = d.LIQ
    d["taxable_portfolio"] = d.STOCKS+d.BOND+d.NMMF
    d["earned_income"] = d.WAGEINC.clip(lower=0)+d.BUSSEFARMINC.clip(lower=0)
    d["pension_excluding_account_draws"] = (d.SSRETINC-d.PENACCTWD).clip(lower=0)
    d["nonlabor_income"] = d.pension_excluding_account_draws+d.TRANSFOTHINC.clip(lower=0)
    d["recurring_income"] = d.earned_income+d.nonlabor_income
    d["earned_share"] = (d.earned_income/d.recurring_income.where(d.recurring_income.gt(0))).fillna(0.)
    d["expense_primary"] = d.den_reported if year==2025 else d.den_expense
    d["age_cohort"] = pd.cut(d.AGE, [19,39,59,74,89], labels=AGE_LABELS)
    d["cash_ge3"] = (d.cash>=3*d.expense_primary).astype(float).where(d.expense_primary.notna())
    d["portfolio_participant"] = d.taxable_portfolio.gt(0).astype(float)
    d["liquid_resources"] = d.cash+d.taxable_portfolio
    d["budget_surplus_annual"] = .85*d.recurring_income-12*d.expense_primary
    configs = {
        "baseline_reserve": dict(equity_loss=0, bond_loss=0, interrupt_months=0),
        "income_interruption_reserve": dict(equity_loss=0, bond_loss=0),
        "combined_stress_reserve": {},
        "cash_only_stress_reserve": dict(include_market_assets=False),
        "combined_low_net_income": dict(net_fraction=.7),
        "combined_gross_income": dict(net_fraction=1),
        "combined_sixmonth_reserve": dict(reserve_months=6),
        "combined_published_expense": {},
        "combined_noage_expense": {},
        "combined_all_income_interruption": dict(interrupt_nonlabor=True),
    }
    for label, settings in configs.items():
        expense = "den_expense" if label=="combined_published_expense" else "den_noage" if label=="combined_noage_expense" else "expense_primary"
        result = stress_path(d, expense, **settings)
        d[label] = result["funded_and_reserve"]
        if label=="combined_stress_reserve":
            d["combined_fund_all_outlays"] = result["funded"]
            d["combined_unmet_annual"] = result["unmet"]
    return d, rw


def pooled_group_means(survey, columns, group, levels):
    def statistic(f, weights):
        results = []
        for level in levels:
            ok = f[group].eq(level).to_numpy() & np.isfinite(f[columns].to_numpy(float)).all(axis=1)
            w = weights[ok]
            results.append((w.T@f.loc[ok, columns].to_numpy(float))/w.sum(axis=0)[:,None])
        return np.concatenate(results, axis=1)
    result = survey.estimate(statistic)
    points = result["estimate"].reshape(len(levels),len(columns))
    ses = result["se"].reshape(points.shape)
    first = survey.data[survey.data.imp.eq(1)]
    rows = []
    for i, level in enumerate(levels):
        sample = first[first[group].eq(level)&np.isfinite(first[columns].to_numpy(float)).all(axis=1)]
        for j, col in enumerate(columns):
            rows.append(dict(group=level, variable=col, estimate=points[i,j], se=ses[i,j],
                low=points[i,j]-1.96*ses[i,j], high=points[i,j]+1.96*ses[i,j],
                n_households_implicate1=len(sample), population_share=sample.WGT.sum()/first.WGT.sum()))
    return pd.DataFrame(rows)


def main():
    age_rows, prevalence, audit, associations = [], [], [], []
    for year in [2016,2019,2022,2025]:
        print("Household budget bridge",year,flush=True)
        d, rw = prepare_wave(year)
        survey = Survey(d,rw)
        outcomes = ["any_risk", "cash_ge3", "baseline_reserve", "combined_stress_reserve", "combined_noage_expense", "combined_published_expense", "combined_all_income_interruption"]
        cols = AGE+DEMO
        for label, controls in [("Demographics",cols),("Income and wealth adjustment",cols+["income_log","wealth_asinh"]),("Income wealth and earned-share adjustment",cols+["income_log","wealth_asinh","earned_share"])]:
            result = fit_many(survey,controls,outcomes)
            k=len(controls)+1
            v=np.array([0]+[4.5 if c=="age10" else 3 if c=="age45plus" else 1 if c=="age65plus" else 0 for c in controls])
            for j,outcome in enumerate(outcomes):
                vector=np.zeros((k,len(outcomes)));vector[:,j]=v;vector=vector.ravel()
                point=float(vector@result["estimate"])
                se=float(np.sqrt(max(vector@result["cov"]@vector,0)))
                age_rows.append(dict(year=year,specification=label,outcome=outcome,estimate=point,
                    se=se,low=point-1.96*se,high=point+1.96*se,contrast="age75 minus age30",
                    expense_definition="reported nonhousing plus rent and debt payments" if year==2025 else "published-method expense reconstruction"))
        for measure in ["cash_ge3","combined_stress_reserve","combined_all_income_interruption"]:
            controls=AGE+DEMO+["income_log","wealth_asinh",measure]
            result=fit_many(survey,controls,["any_risk"])
            j=len(controls)
            b=float(result["estimate"][j]);se=float(result["se"][j])
            associations.append(dict(year=year,measure=measure,estimate=b,se=se,low=b-1.96*se,high=b+1.96*se,
                interpretation="Adjusted cross-sectional willingness difference associated with meeting the stated budget threshold; not a causal effect"))
        measures=["any_risk","cash_ge3","portfolio_participant","baseline_reserve","income_interruption_reserve",
            "combined_stress_reserve","cash_only_stress_reserve","combined_low_net_income","combined_gross_income",
            "combined_sixmonth_reserve","combined_published_expense","combined_noage_expense","combined_fund_all_outlays","combined_all_income_interruption"]
        table=pooled_group_means(survey,measures,"age_cohort",AGE_LABELS)
        table["year"]=year
        prevalence.append(table)
        first=d[d.imp.eq(1)]
        audit.append(dict(year=year,households=len(first),implicates=5,replicates=999,
            missing_primary_expense=int(first.expense_primary.isna().sum()),
            portfolio_zero_share=np.average(first.portfolio_participant.eq(0),weights=first.WGT),
            income_excludes="interest/dividends, capital gains and PENACCTWD",
            expense_definition="reported" if year==2025 else "approximate reconstruction"))
        if year==2025:
            d["profile"] = d.age_cohort.astype(str)+" | "+np.where(d.cash_ge3.eq(1),"cash >=3 months","cash <3 months")+" | "+np.where(d.any_risk.eq(1),"willing","no risk")
            levels=sorted(d.profile.unique())
            variables=["AGE","cash","taxable_portfolio","earned_income","nonlabor_income","recurring_income",
                "expense_primary","den_expense","den_noage","tolerance","any_risk","portfolio_participant"]
            profile=pooled_group_means(Survey(d,rw),variables,"profile",levels)
            profile.to_csv(OUT/"household_profile_estimates.csv",index=False)
            pooled_group_means(survey,["combined_stress_reserve","combined_all_income_interruption","baseline_reserve"],"profile",levels).to_csv(OUT/"actual_household_cell_stress.csv",index=False)
            templates=profile.pivot(index="group",columns="variable",values="estimate").reset_index().rename(columns={"group":"profile_id"})
            counts=profile.groupby("group")[["n_households_implicate1","population_share"]].first().reset_index().rename(columns={"group":"profile_id"})
            templates=templates.merge(counts,on="profile_id",validate="one_to_one")
            templates["template_type"]="MI-pooled survey-weighted cell mean; not an individual household or a population simulation"
            templates.to_csv(OUT/"household_templates.csv",index=False)
            joint=pooled_group_means(survey,["cash_ge3","baseline_reserve","combined_stress_reserve"],"any_risk",[0.,1.])
            joint.to_csv(OUT/"willingness_budget_joint.csv",index=False)
            d[["YY1","imp","WGT","AGE","any_risk","tolerance","cash","taxable_portfolio",
                "earned_income","nonlabor_income","recurring_income","expense_primary","den_expense",
                "den_noage","age_cohort","profile"]].to_csv(CACHE/"prepared_public_scf2025.csv.gz",index=False)
        load_expenses.cache_clear()
        pd.DataFrame(age_rows).to_csv(OUT/"budget_age_contrasts.csv",index=False)
        pd.DataFrame(associations).to_csv(OUT/"willingness_budget_adjusted.csv",index=False)
        pd.concat(prevalence).to_csv(OUT/"budget_age_profiles.csv",index=False)
        pd.DataFrame(audit).to_csv(OUT/"household_sample_audit.csv",index=False)
    sources=[]
    for year in [2016,2019,2022,2025]:
        folder=PROJECT/("data/raw" if year==2025 else "data/capacity_validation")
        for name in [f"scfp{year}excel.zip",f"scf{year}s.zip",f"scf{year}rw1s.zip"]:
            path=folder/name
            sources.append(dict(filename=name,url="https://www.federalreserve.gov/econres/files/"+name,
                sha256=hashlib.sha256(path.read_bytes()).hexdigest(),bytes=path.stat().st_size))
    (OUT/"household_input_manifest.json").write_text(json.dumps({"sources":sources,
        "script_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "methods":"Five imputations pooled; official 999 replicate weights on implicate 1 plus MI variance; observational age contrasts",
        "stress_definition":"Investigator-defined one-year liquid-budget stress; 40% equity loss, 10% bond loss, six months without earned income, 85% gross-to-net assumption, three months terminal expense reserve",
        "primary_2025_expense":"Direct reported nonhousing outlays plus rent and debt payments; earlier waves use the approximate published reconstruction",
        "templates":"Cell means preserve linear accounting, but nonlinear template outcomes are not population means",
        "willingness":"Observed ordinal response; not transformed into CRRA or a binding stock-allocation recommendation"},indent=2),encoding="utf-8")
    print("Household bridge preparation completed",flush=True)


if __name__=="__main__":
    main()
