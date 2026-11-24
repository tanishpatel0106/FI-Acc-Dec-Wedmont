"""Create the English WRDS extension from aggregate study artifacts only."""
from pathlib import Path
import nbformat as nbf

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "research/wrds_validation_2026_11_19"
cells = []


def md(s):
    cells.append(nbf.v4.new_markdown_cell(s))


def code(s):
    cells.append(nbf.v4.new_code_cell(s))


md("""# WRDS validation of retirement portfolio allocation

**November 19, 2026 | Extension of the Tanish/Wedmont implementation audit**

We investigate whether the withdrawal-success frontier and the value of conditioning allocation on
planned cash flows survive a change in return measurement. This extension replaces reconstructed
Treasury returns with CRSP target-maturity Treasury returns, then replaces the remaining core inputs.
The analysis is retrospective and follows the public-data results; it is not a new preregistered test.

The object of study is a portfolio rule under specified withdrawals and preferences. These market-return
data contain no household age, reported risk tolerance, or household balance sheets. Accordingly, this
analysis cannot estimate the population relationship between age and risk tolerance or financial capacity.
The earlier household-survey work addresses a different empirical question.
""")
code('''from pathlib import Path
import json
import hashlib
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from IPython.display import display, Markdown
ROOT = next(p for p in [Path.cwd(), *Path.cwd().parents] if (p/'backend/lifecycle').exists())
OUT = ROOT/'research/wrds_validation_2026_11_19'
FIG = OUT/'figures'
FIG.mkdir(exist_ok=True)
def read(name):
    return json.loads((OUT/name).read_text(encoding='utf-8'))
def result(record):
    return read(record['run_id']+'.json')
def export(name):
    plt.savefig(FIG/(name+'.png'),dpi=180,bbox_inches='tight')
    plt.show()
plt.rcParams.update({'figure.dpi':120,'axes.spines.top':False,'axes.spines.right':False,'font.size':10})
labels = {'public':'Public reconstructed Treasury','treasury_only':'CRSP Treasury only','wrds':'All CRSP core inputs'}
runs = {d:read(d+'_frontier_runs.json') for d in labels}
extended = read('wrds_extended_runs.json')
''')
md("""## Data sources and selection

CRSP Treasury and Inflation Indexes (`crsp.mcti`) provide Treasury target-maturity returns, a one-month
bill return and CPI inflation. `crsp.msix.vwretd` supplies the US value-weighted equity return including
distributions. These extracts end in December 2024. Treasury return histories start in 1941; the common
long calibration begins in May 1953, the first month available for the public Treasury reconstruction.

The CRSP methodology selects a representative issue near each target maturity. It is an observed
security-return series assembled under an index methodology, rather than the project's yield-based
par-bond reconstruction. It also differs from IEF, which holds a portfolio of securities with maturities
of seven to ten years. This choice tests the sensitivity to Treasury measurement without treating the
two definitions as identical. See the [CRSP data descriptions, section 3.4](https://wrds-www.wharton.upenn.edu/documents/399/Data_Descriptions_Guide.pdf).

The ETF extract uses `crsp.msf_v2.mthret`, with distributions included, and ends in December 2025.
Each requested ticker resolves to one PERMNO during the extracted period. Ten funds cover international
and emerging equities, intermediate and long Treasuries, investment-grade and high-yield credit,
TIPS, real estate, gold and commodities. Published inception dates restrict the extraction to the intended
funds. First fund months may be partial; none enters the matched core frontier experiment. Portfolio
comparisons start in December 2004 for the Permanent Portfolio and May 2007 for the full universe,
after the youngest required fund's first partial month.

WRDS Bond Returns supplies a supplementary credit aggregation, August 2002 to May 2026. We use
immediately previous-month ratings and amount outstanding, exclude gaps in consecutive months, and
retain bonds with a nonmissing current return and positive lagged weight. IG uses rating numbers 1-10;
HY uses 11-21. These are lagged par-amount-weighted research portfolios, not market-value-weighted
investable indexes. Missing returns and the data provider's bond coverage can affect them.
The canonical panel selects TRACE-derived IG and the observed HYG fund for HY under its source-priority
rule; the supplementary TRACE HY aggregate is not used by the reported full-universe allocation study.

Raw licensed observations remain local and excluded from Git and the report package. This notebook reads
only aggregate results and coverage metadata. Sources: [WRDS CRSP product documentation](https://wrds-www.wharton.upenn.edu/pages/about/data-vendors/center-for-research-in-security-prices-crsp/),
[WRDS Bond Returns product description](https://wrds-www.wharton.upenn.edu/pages/analytics/).
""")
code('''audit = pd.read_csv(OUT/'source_audit.csv')
selected = ['us_eq','ust_2y','ust_5y','ust_10y','ust_30y','tbill','cpi_nsa','ust_7_10_etf','gold','ig_credit','hy_credit']
display(audit[audit.series_id.isin(selected)].reset_index(drop=True))
assert audit['nonfinite'].sum()==0 and audit['duplicates'].sum()==0
summary = read('extraction_summary.json')
checks = pd.DataFrame(summary['sources']['mcti']['unit_checks_against_index_growth']).T
display(checks)
assert (checks.decimal_rmse < checks.percent_rmse).all()
display(Markdown('Return/index reconciliation supports decimal return units. CPI index levels have lower precision, so their reconciliation residual is larger. Core series have no internal missing months.'))
display(pd.read_csv(OUT/'source_difference_summary.csv').round(6))
''')
md("""## Matched source experiment

We run three panels over exactly the same calendar windows: the public baseline, a panel replacing only
Treasury returns with CRSP, and a panel replacing Treasury, equity, cash and inflation with CRSP.
The Treasury-only comparison isolates that source change; the all-CRSP comparison changes four inputs
jointly. No observations are spliced across providers, and missing values are never filled.

Each frontier uses 10,000 bootstrap evaluation paths, 5,000 training paths, seed 20261119, annual
rebalancing, a 0%-100% bond grid in 5-percentage-point steps, and annual real withdrawals of 3%-6% of
initial wealth. The horizon is 30 years for both success and utility calculations. Trading costs are zero
in this matched experiment. A Student-t generator provides an additional scenario comparison.

Success means fully funding all planned withdrawals over the horizon. The minimum bond share is the
lowest tested allocation reaching 90% success. An empty value means that no allocation on the grid
reaches that target. The frontier is not assumed monotone: a zero minimum does not imply every larger
bond allocation is feasible. Bootstrap threshold intervals use 300 resamples of simulation paths and
condition on the fitted return generator. They do not include uncertainty about the historical sample,
regimes, costs or future market structure. Maximizing reported success across the evaluation grid is
descriptive; the separately trained objective comparison below provides independent policy evaluation.
""")
code('''rows=[]
for dataset, records in runs.items():
    for window, record in records.items():
        z=result(record)
        for rate in [.04,.045,.05,.055]:
            i=int(np.argmin(abs(np.array(z['r'])-rate)))
            probs=np.array(z['p_success']['30'])[:,i]
            threshold=z['thresholds']['30|0.90'][i]
            boot=z['threshold_bootstrap']['30|0.90'][i]
            rows.append({'dataset':dataset,'window':window,'withdrawal_rate':rate,
                         'best_success':probs.max(),'all_equity_success':probs[0],
                         'minimum_bond_share':threshold['b_min'],'status':threshold['status'],
                         'conditional_bond_q05':boot['q05'],'conditional_bond_q95':boot['q95'],
                         'bootstrap_infeasible_fraction':boot['share_unidentified'],
                         'run_id':record['run_id'],'catalog_hash':record['catalog_hash']})
table=pd.DataFrame(rows)
table.to_csv(OUT/'matched_frontier_summary.csv',index=False)
display(table[np.isclose(table.withdrawal_rate,.05)].round(4))
fig,axes=plt.subplots(1,2,figsize=(12,4.4),layout='constrained')
windows=['long','modern','early','recent']
positions=np.arange(len(windows)); width=.25
for j,d in enumerate(labels):
    part=table[np.isclose(table.withdrawal_rate,.05)&table.dataset.eq(d)].set_index('window').loc[windows]
    axes[0].bar(positions+(j-1)*width,100*part.best_success,width,label=labels[d])
    axes[1].plot(positions,100*part.minimum_bond_share,marker='o',label=labels[d])
axes[0].axhline(90,color='black',ls='--',lw=1)
axes[0].set(ylabel='Highest grid success probability (%)',ylim=(75,100),title='5% withdrawal: spending success')
axes[1].set(ylabel='Minimum feasible bond share (%)',ylim=(-5,105),title='90% target; gaps indicate infeasibility')
for ax in axes:
    ax.set_xticks(positions,['1953-2024','2002-2024','2002-2013','2014-2024'],rotation=20)
axes[0].legend(frameon=False,fontsize=8)
export('matched_source_comparison')
fig,axes=plt.subplots(1,3,figsize=(13,3.8),layout='constrained')
for ax,d in zip(axes,labels):
    z=result(runs[d]['modern'])
    im=ax.pcolormesh(100*np.array(z['r']),100*np.array(z['b']),z['p_success']['30'],
                     shading='nearest',vmin=.5,vmax=1,cmap='viridis')
    ax.set(title=labels[d],xlabel='Initial annual real withdrawal (%)',ylabel='Bond share (%)')
fig.colorbar(im,ax=axes,label='30-year spending success')
export('matched_success_heatmaps')
early=table[np.isclose(table.withdrawal_rate,.05)&table.window.eq('early')].set_index('dataset')
modern=table[np.isclose(table.withdrawal_rate,.05)&table.window.eq('modern')].set_index('dataset')
display(Markdown(f"At 5% withdrawals in the 2002-2013 calibration, replacing only Treasury returns increases the highest grid success rate from {early.loc['public','best_success']:.2%} to {early.loc['treasury_only','best_success']:.2%}; the first feasible bond allocation is {early.loc['treasury_only','minimum_bond_share']:.0%}. Over 2002-2024, the all-CRSP panel reaches only {modern.loc['wrds','best_success']:.2%}, below the 90% target. The 40% allocation is therefore conditional on the earlier calibration window, not a general minimum."))
alternatives=[]
for d,records in runs.items():
    for window,record in records.items():
        z=result(record)
        i=int(np.argmin(abs(np.array(z['r'])-.05)))
        for generator,alt in z['alt_generators'].items():
            threshold=alt['thresholds'][i]
            alternatives.append({'dataset':d,'window':window,'generator':generator,'paths':alt['n_paths'],
                'highest_success_at_5pct':np.array(alt['p_success'])[:,i].max(),
                'minimum_bonds':threshold['b_min'],'status':threshold['status']})
alternative_table=pd.DataFrame(alternatives)
alternative_table.to_csv(OUT/'generator_sensitivity.csv',index=False)
display(alternative_table.round(4))
display(Markdown('The Student-t comparison uses 1,000 paths and a coarser 10-percentage-point bond grid. It can change threshold feasibility and has more Monte Carlo noise than the main experiment; near-90% estimates do not establish a dependable spending guarantee.'))
''')
md("""## Age, cash flows and independent evaluation

The signed-flow surface fixes an exogenous annual net draw as a fraction of initial reference wealth;
negative values denote contributions. We fit allocations by age and flow using 4,000 paths and evaluate
on 5,000 separate paths, calibrated on January 1953-December 2024 CRSP returns. CRRA risk aversion is 4.
The objective is certainty-equivalent terminal real
wealth plus cumulative funded withdrawals, with a USD 1,000 floor, rather than a direct measure of
household capacity or consumption utility. The age-only rule averages normalized training objectives
equally over the declared flow grid. Joint path resampling preserves dependence across age/flow cells.

The 20-year surface gives ages 25-75 the same effective horizon. With zero labor income in the surface
experiment, age has no independent cash-flow channel there. Age 85 has a 10-year horizon because the
terminal-age cap is 95. Identical fitted allocations for ages 25-75 follow from this model specification.

For historical evaluation, training uses only pre-split returns. Frozen allocations are scored on all
completed later 10- and 20-year cohorts through December 2024. The 1990, 2000, 2005, 2010 and 2015
splits are retained only when the full horizon is available. Public and CRSP versions use the same end
date. Cohorts and splits overlap; their results are reported separately without an IID standard error
or a pooled significance claim. Policies are fixed through each cohort, so this test evaluates static
conditional allocations, not annual adaptive retraining.
Both historical comparisons begin training in May 1953. The separate objective-selection experiment
uses the January 1953-December 2024 CRSP sample, 5,000 training paths and 10,000 evaluation paths.
Historical training also respects the recorded 15-day CPI publication lag: January allocations use
joint return history through the previous November. Revised extracts remain a limitation.
""")
code('''signed=result(extended['signed_flow'])
comparison=signed['policies']['oos_full_vs_age']
display(pd.DataFrame([comparison]))
display(Markdown(f"The independent simulation estimate for age-plus-flow versus age-only resources CE is {comparison['delta']:.2%}, with a paired-path 95% interval [{comparison['lo']:.2%}, {comparison['hi']:.2%}]. This interval is conditional on the return model and trained policies."))
if comparison['lo']<=0<=comparison['hi']:
    display(Markdown('The corrected matched-universe interval includes zero. This experiment does not establish that conditioning allocation on cash flows improves performance over the horizon-only rule. The further validation section reports seed, specification and historical refitting checks.'))
fig,ax=plt.subplots(figsize=(9,4))
im=ax.pcolormesh(100*np.array(signed['q']),signed['ages'],100*np.array(signed['b_ce']),shading='nearest',cmap='viridis',vmin=0,vmax=100)
ax.set(xlabel='Annual planned net draw / initial wealth (%)',ylabel='Starting age',title='CRSP: training-optimal bond allocation (resources CE)')
fig.colorbar(im,ax=ax,label='Bond share (%)')
export('age_cash_flow_surface')
history=pd.concat([pd.read_csv(OUT/(d+'_chronological_holdout.csv')) for d in ['wrds','public_matched']],ignore_index=True)
groups=history.groupby(['dataset','split_year','max_horizon']).agg(mean_relative_ce=('full_vs_age_delta','mean'),
    minimum_cell_ce=('full_vs_age_delta','min'),maximum_cell_ce=('full_vs_age_delta','max'),
    cells=('age','size'),minimum_cohorts=('n_overlapping_cohorts','min'),maximum_cohorts=('n_overlapping_cohorts','max')).reset_index()
groups.to_csv(OUT/'chronological_summary.csv',index=False)
display(groups.round(4))
wrds_groups=groups[groups.dataset.eq('wrds')]
display(Markdown(f"The WRDS chronological mean CE difference is positive in {(wrds_groups.mean_relative_ce>0).sum()} of {len(wrds_groups)} folds and negative in {(wrds_groups.mean_relative_ce<0).sum()}. The range is {wrds_groups.mean_relative_ce.min():.2%} to {wrds_groups.mean_relative_ce.max():.2%}. These overlapping folds are not independent replications; the latest ten-year fold has only one completed cohort."))
fig,ax=plt.subplots(figsize=(10,4))
for (d,h),g in groups.groupby(['dataset','max_horizon']):
    ax.plot(g.split_year,100*g.mean_relative_ce,marker='o',label=f'{d}: maximum horizon {h} years')
ax.axhline(0,color='black',lw=1)
ax.set(xlabel='First test year',ylabel='Age-plus-flow vs age-only resources CE (%)',title='Completed historical cohorts; overlapping windows')
ax.legend(frameon=False,fontsize=8)
export('chronological_comparison')
allocation=read('wrds_allocation_holdout.json')
allocation_rows=[]
for r in allocation['results']:
    delta=r['test_ce_delta_ce_vs_survival']
    allocation_rows.append({'withdrawal_rate':r['withdrawal_rate'],'ce_selected_bonds':r['trained_ce_bond_share'],
      'success_selected_bonds':r['trained_survival_bond_share'],'ce_policy_success':r['test_ce_opt_success'],
      'success_policy_success':r['test_survival_opt_success'],'ce_gain':delta['delta'],'ce_ci_lo':delta['lo'],'ce_ci_hi':delta['hi']})
allocation_table=pd.DataFrame(allocation_rows)
allocation_table.to_csv(OUT/'allocation_objective_summary.csv',index=False)
display(allocation_table.round(4))
r5=allocation_table[np.isclose(allocation_table.withdrawal_rate,.05)].iloc[0]
display(Markdown(f"At 5% withdrawals, the trained utility policy selects {r5.ce_selected_bonds:.0%} bonds and the spending-success policy selects {r5.success_selected_bonds:.0%}. On independent paths, the utility policy gains {r5.ce_gain:.2%} CE (95% interval [{r5.ce_ci_lo:.2%}, {r5.ce_ci_hi:.2%}]) and changes success by {(r5.ce_policy_success-r5.success_policy_success)*100:.2f} percentage points. These objectives recommend different allocations even with the same return data."))
''')
md("""## Expanded portfolios and reproducibility

Observed gold, TIPS, high-yield and commodity funds now permit the full multi-asset study and the classic
Permanent Portfolio to execute. The Permanent Portfolio uses the existing annual 15/35 band review and
the same scenario paths as its 60/40 benchmark. The full multi-asset analysis uses 12 sleeves over their
joint available history, with no backfill before fund inception. Results include the source definitions,
costs, common windows, generator and run IDs. Different universes and calibration periods prevent a
causal attribution of changes to diversification alone.
""")
code('''pp=result(extended['permanent'])
multi=result(extended['multi_asset'])
pp_rows=[]
for r in pp['scorecard']:
    d=r.get('delta_ce_vs_benchmark',{})
    pp_rows.append({'policy':r['policy'],'ce':r['ce']['ce'],'success_30y':r['success']['30']['p'],
        'ce_vs_benchmark':d.get('delta',0),'lo':d.get('lo'),'hi':d.get('hi')})
display(pd.DataFrame(pp_rows).round(4))
multi_rows=[]
for r in multi['scorecard']:
    delta=r.get('delta_ce',{})
    multi_rows.append({'policy':r['policy'],'family':r['family'],'ce':r['ce'],
                      'success':r['success'],'annual_cost_bps':r['cost_bps_yr'],'median_drawdown':r['mdd_median'],
                      'relative_ce':delta.get('delta',0),'lo':delta.get('lo',0),'hi':delta.get('hi',0)})
multi_table=pd.DataFrame(multi_rows)
display(multi_table.round(4))
display(Markdown(f"In this calibration, {(multi_table.hi<0).sum()} of {len(multi_table)-1} alternatives have lower consumption CE than 60/40 with an unadjusted paired interval entirely below zero. The intervals condition on the fitted model and are not corrected for multiple policy comparisons. Adding asset classes does not establish superior retirement performance."))
multi_table.to_csv(OUT/'multi_asset_summary.csv',index=False)
fig,ax=plt.subplots(figsize=(9,5))
for i,r in multi_table.iterrows():
    ax.plot([100*r['lo'],100*r['hi']],[i,i],color='tab:blue')
    ax.plot(100*r.relative_ce,i,'o',color='tab:blue')
ax.axvline(0,color='black',lw=1)
ax.set_yticks(range(len(multi_table)),multi_table.policy)
ax.set(xlabel='CE difference vs 60/40 (%) with paired 95% interval',title='Full universe: estimated performance depends on the policy')
export('multi_asset_comparison')
display(pd.DataFrame([{'study':name,'run_id':record['run_id'],'catalog_hash':record['catalog_hash'],
    'engine_version':record['engine_version']} for name,record in extended.items()]))
display(pd.DataFrame([{'study':name,'assets':', '.join(z['universe']['assets']),
                      'start':z['universe']['window'][0],'end':z['universe']['window'][1],
                     'months':z['universe']['n_months']}
                     for name,z in [('permanent',pp),('multi_asset',multi)]]))
display(pd.DataFrame([read('verification.json')]).T.rename(columns={0:'result'}))
''')
from build_robustness_section import append_robustness
append_robustness(md, code)

md("""## Interpretation and remaining limits

Return measurement changes the estimated spending-success frontier enough to change whether a 90%
target is feasible. The result also changes across historical windows. A universal bond allocation or
withdrawal guarantee is unsupported by these experiments. The age-plus-flow comparison must be judged
from its independent-path and chronological results above; separating the concepts of willingness and
capacity is a modeling premise, not an empirical finding from these market data.

All simulations condition on historical calibration, the withdrawal convention, CRRA objective,
rebalancing rule and terminal-age cap. Bootstrap and Student-t experiments do not eliminate structural
model risk. Historical tests use revised data extracts, overlapping cohorts and selected windows.
Monte Carlo intervals measure simulation uncertainty. Country effects, cohort effects, human-capital
risk and changes in household preferences remain outside this return-based extension.

The corrected matched-universe signed-flow result supersedes the initial six-asset WRDS extension.
The robustness section separates fixed-policy simulation intervals, sensitivity across specifications,
training-history refit dispersion and realized nonoverlapping periods. These quantities answer different
questions and are not interchangeable confidence statements.

The notebook is executable from the supplied aggregate JSON and CSV artifacts without a WRDS account.
Recomputing the restricted-data studies requires an entitled WRDS academic account. Run
`research/extract_wrds_cloud.py` in WRDS Cloud, retain the exported files locally under
`data/wrds_validation/inputs`, then run these commands from the repository root:

```powershell
backend/.venv/Scripts/python.exe research/import_wrds_cloud.py
backend/.venv/Scripts/python.exe research/validate_wrds_followup.py --dataset public
backend/.venv/Scripts/python.exe research/validate_wrds_followup.py --dataset treasury_only
backend/.venv/Scripts/python.exe research/validate_wrds_followup.py --dataset wrds
backend/.venv/Scripts/python.exe research/robustness_followup.py --stage sensitivity
backend/.venv/Scripts/python.exe research/robustness_followup.py --stage nonoverlap --dataset wrds
backend/.venv/Scripts/python.exe research/robustness_followup.py --stage nonoverlap --dataset public
backend/.venv/Scripts/python.exe research/robustness_followup.py --stage refit
backend/.venv/Scripts/python.exe research/verify_robustness.py
```

`public_matched_chronological_holdout.csv` is generated by calling
`validate_followup.holdout('public_matched', end_date='2024-12-31', start_date='1953-05-01', respect_publication_lags=True)`
with the public data directory.
Hashes identify the exact restricted extracts and resolved panels; vendor revisions can change a fresh
extraction. The delivered package contains no restricted return observations. WRDS access has been
completed. Employer installation still awaits the employer's reply and GitHub username; no message has
been sent on the user's behalf.
""")
notebook = nbf.v4.new_notebook(cells=cells, metadata={"kernelspec": {
    "display_name": "Python 3", "language": "python", "name": "python3"}})
nbf.write(notebook, OUT / "wrds_validation.ipynb")
(ROOT / "data/wrds_validation/report_prose.txt").write_text("\n\n".join(c.source for c in cells if c.cell_type == "markdown"), encoding="utf-8")
print("Created WRDS validation notebook")
