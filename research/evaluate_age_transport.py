"""Chronological transport tests across independent SCF cross-sections.

Age prediction is evaluated out of wave, not inferred from in-sample significance.
Test survey uncertainty is conditional on the fitted training models. Training-sample
uncertainty, cohort effects and within-person aging are not identified here.
"""
import hashlib
import json
import os
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.stats import norm
from statsmodels.stats.multitest import multipletests

ROOT=Path(__file__).resolve().parents[1]
PROJECT=Path(os.environ.get("FIXED_INCOME_SURVEY_ROOT",ROOT.parent))
sys.path.insert(0,str(PROJECT/"scripts"))
from age_expense_analysis import load_expenses
from capacity_validation import AGE
from scf_analysis import Survey

OUT=ROOT/"research/integrated_handoff_2026_11_20"
MODELS={"Intercept":[],"Age":AGE,"Financial":["income_log","wealth_asinh"],
        "Financial + age":["income_log","wealth_asinh",*AGE]}
TARGETS=["any_risk","accessible_noage_ge3"]


def weighted_auc(y,p,w):
    """Weighted rank AUC with exact half credit for tied predictions."""
    order=np.argsort(p,kind="stable")
    y=y[order];p=p[order];w=w[order]
    starts=np.r_[0,1+np.flatnonzero(np.diff(p))]
    pos=np.add.reduceat(w*y[:,None],starts,axis=0)
    neg=np.add.reduceat(w*(1-y[:,None]),starts,axis=0)
    return (pos*(np.cumsum(neg,axis=0)-.5*neg)).sum(axis=0)/(pos.sum(axis=0)*neg.sum(axis=0))


def score_frame(f,w,target):
    y=f[target].to_numpy(float)
    rows=[]
    for label in MODELS:
        p=f["p_"+label].to_numpy(float)
        brier=(w.T@((p-y)**2))/w.sum(axis=0)
        loss=-(y*np.log(p)+(1-y)*np.log1p(-p))
        rows.extend([brier,w.T@loss/w.sum(axis=0),weighted_auc(y,p,w)])
    # Paired improvements isolate incremental age information.
    financial=f["p_Financial"].to_numpy(float)
    age=f["p_Financial + age"].to_numpy(float)
    rows.append(w.T@((financial-y)**2-(age-y)**2)/w.sum(axis=0))
    base=f["p_Intercept"].to_numpy(float)
    ageonly=f["p_Age"].to_numpy(float)
    rows.append(w.T@((base-y)**2-(ageonly-y)**2)/w.sum(axis=0))
    return np.column_stack(rows)


def main():
    waves={};weights={};rows=[];coefficients=[]
    for year in [2016,2019,2022,2025]:
        d,rw=load_expenses(year)
        columns=["YY1","imp","WGT","year",*AGE,"income_log","wealth_asinh",*TARGETS]
        waves[year]=d[columns].dropna().copy();weights[year]=rw
        load_expenses.cache_clear()
    for testyear in [2019,2022,2025]:
        training=[year for year in waves if year<testyear]
        print("Chronological SCF test",training,"to",testyear,flush=True)
        for target in TARGETS:
            test=waves[testyear].copy()
            for m in range(1,6):
                train=pd.concat([waves[y][waves[y].imp.eq(m)] for y in training])
                # Give each survey wave equal total training weight.
                tw=train.WGT/train.groupby("year").WGT.transform("sum")*len(train)/len(training)
                mask=test.imp.eq(m)
                for label,features in MODELS.items():
                    x=np.column_stack([np.ones(len(train)),train[features].to_numpy(float)])
                    fit=sm.GLM(train[target].to_numpy(float),x,family=sm.families.Binomial(),freq_weights=tw).fit(maxiter=100)
                    if not fit.converged:
                        raise RuntimeError("Training logit failed to converge")
                    xt=np.column_stack([np.ones(mask.sum()),test.loc[mask,features].to_numpy(float)])
                    test.loc[mask,"p_"+label]=np.clip(fit.predict(xt),1e-8,1-1e-8)
                    for term,b in zip(["Intercept",*features],fit.params):
                        coefficients.append(dict(test_year=testyear,target=target,implicate=m,model=label,term=term,coefficient=b))
            result=Survey(test,weights[testyear]).estimate(lambda f,w:score_frame(f,w,target))
            labels=[(model,metric) for model in MODELS for metric in ["Brier","Log loss","AUC"]]
            labels += [("Financial vs financial + age","Brier improvement"),("Intercept vs age","Brier improvement")]
            for i,(model,metric) in enumerate(labels):
                point=result["estimate"][i];se=result["se"][i]
                rows.append(dict(train_years="+".join(map(str,training)),test_year=testyear,target=target,
                    model=model,metric=metric,estimate=point,se=se,low=point-1.96*se,high=point+1.96*se,
                    n_test_households=int(test.imp.eq(1).sum()),
                    uncertainty="Test survey and MI uncertainty conditional on fitted training models; not training-sample uncertainty"))
            pd.DataFrame(rows).to_csv(OUT/"age_out_of_wave_scores.csv",index=False)
    pd.DataFrame(coefficients).to_csv(OUT/"age_out_of_wave_coefficients.csv",index=False)
    scores=pd.DataFrame(rows)
    primary=scores.model.eq("Financial vs financial + age")
    scores["p_holm_six_incremental_age_tests"]=np.nan
    scores.loc[primary,"p_holm_six_incremental_age_tests"]=multipletests(2*norm.sf(np.abs(scores.loc[primary,"estimate"]/scores.loc[primary,"se"])),method="holm")[1]
    scores.to_csv(OUT/"age_out_of_wave_scores.csv",index=False)
    (OUT/"age_transport_design.json").write_text(json.dumps(dict(
        script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        models=MODELS,targets=TARGETS,train_test="Expanding earlier waves to the next held-out wave; independent household cross-sections",
        weights="Equal total training weight per wave; five separately fitted MI models; official held-out survey weights and 999 replicates",
        feature_caveat="Financial predictors share ingredients with the liquidity outcome; predictive association is not independent construct validation",
        measurement="Common accessible-asset/no-age expense reconstruction across all waves; any_risk is directly reported",
        decision_rule="Positive paired Brier improvement means predictive age information in the held-out wave; no universal threshold or lifetime claim",
        uncertainty="Intervals condition on fitted models; they do not include full training-sample or model-selection uncertainty"),indent=2),encoding="utf-8")
    print("Out-of-wave transport evaluation completed",flush=True)


if __name__=="__main__":
    main()
