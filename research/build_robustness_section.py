"""Append the exploratory robustness evidence to the English employer notebook."""


def append_robustness(md, code):
    md("""## Further validation: selection uncertainty and complete historical periods

The initial WRDS signed-flow extension accidentally used the `core` universe, which includes three
additional Treasury maturities, whereas the public study uses `core_long_history` with three assets.
Although their portfolio weights were zero, unused assets changed the automatically selected joint
bootstrap block length. We corrected the WRDS surface to the explicit three-asset universe. The
earlier six-asset run remains in the audit files and is superseded by the corrected result above.

This is a retrospective exploratory extension. `robustness/design.json` was saved before these
calculations; it is not an independent preregistration. The new tests examine simulation noise,
return dependence, transaction costs, allocation-grid resolution and objective definitions.
All configurations and negative results are retained.

The sensitivity analysis uses 4,000 training paths and 10,000 separate evaluation paths. It retains the
original 19 flow values and two unique effective horizons, 10 and 20 years. Original age-cell weights
are 1/7 and 6/7 because six declared ages duplicate the 20-year experiment. An alternative gives the
two distinct horizons equal weight. Other checks use five random seeds; mean bootstrap blocks of
1, 6, 12 and 24 months plus the automatic choice; a Student-t generator on the same path count and
allocation grid; five-basis-point half-spreads; a five-percentage-point bond grid; risk aversion
2, 4, 6 and 8; resource floors of USD 100, 1,000 and 10,000; and a six-point flow grid.

We also test a proposed shrinkage rule. The first 2,000 training paths fit conditional and horizon-only
allocations. A separate set of 2,000 validation paths chooses alpha from 0, 0.25, 0.5, 0.75 and 1 for
`b = b_horizon + alpha * (b_conditional - b_horizon)`, rounded to the tested grid. Allocations are then
refitted on all 4,000 training paths with alpha frozen, before evaluating the untouched test paths.
Alpha zero recovers the restricted rule. We do not select the winning alpha on the evaluation sample.
This follows the separation-of-selection-and-evaluation principle in
[Varma and Simon (2006)](https://doi.org/10.1186/1471-2105-7-91); it does not replicate their classifier experiment.
""")
    code('''ROB = OUT/'robustness'
sens=pd.read_csv(ROB/'sensitivity_scores.csv')
main_mask=(sens.gamma.eq(4)&sens.resource_floor.eq(1000)&sens.weighting.eq('original_age_weights')&sens.flow_grid.eq('full'))
primary=sens[main_mask].copy()
primary['condition']=np.select([primary.bond_step.eq(.05),primary.cost_half_spread_bps.eq(5),primary.generator.eq('student_t'),primary.requested_block.isna()],
    ['5pp bond grid','5bp half-spread','Student-t','Automatic block'],default='Fixed block')
fixed=primary.condition.eq('Fixed block')
primary.loc[fixed,'condition']='Block '+primary.loc[fixed,'requested_block'].astype(int).astype(str)+' months'
summary=primary.groupby(['condition','policy']).agg(median_ce=('relative_resources_ce','median'),
    minimum_ce=('relative_resources_ce','min'),maximum_ce=('relative_resources_ce','max'),seeds=('seed','nunique'),
    median_success_difference_pp=('success_difference_pp','median')).reset_index()
summary.to_csv(ROB/'configuration_summary.csv',index=False)
display(summary[summary.policy.isin(['full','validated_shrinkage'])].round(5))
baseline=primary[primary.condition.eq('Automatic block')]
display(baseline[['seed','policy','relative_resources_ce','relative_terminal_ce','success_difference_pp','selected_alpha']].round(5))
full=baseline[baseline.policy.eq('full')]
display(Markdown(f"With the corrected three-asset setting and 10,000 evaluation paths, the five baseline seeds give conditional-versus-horizon-only resources CE changes from {full.relative_resources_ce.min():.2%} to {full.relative_resources_ce.max():.2%}, with a median of {full.relative_resources_ce.median():.2%}. Seeds reuse the same historical calibration and are not five independent economic samples."))
fig,ax=plt.subplots(figsize=(10,4.5))
conditions=list(summary.condition.unique())
for j,policy in enumerate(['full','validated_shrinkage']):
    g=summary[summary.policy.eq(policy)].set_index('condition').loc[conditions]
    y=np.arange(len(g))+(j-.5)*.16
    for i,(_,r) in enumerate(g.iterrows()):
        ax.plot([100*r.minimum_ce,100*r.maximum_ce],[y[i],y[i]],color=['tab:blue','tab:orange'][j])
    ax.plot(100*g.median_ce,y,'o',label=policy,color=['tab:blue','tab:orange'][j])
ax.axvline(0,color='black',lw=1)
ax.set_yticks(range(len(conditions)),conditions)
ax.set(xlabel='Resources CE vs horizon-only (%): median and seed range',title='Simulation and modeling sensitivity; ranges are not confidence intervals')
ax.legend(frameon=False)
export('robustness_configuration_sensitivity')
preference=sens[sens.generator.eq('bootstrap')&sens.requested_block.isna()&sens.cost_half_spread_bps.eq(0)&sens.bond_step.eq(.1)]
pref_summary=preference.groupby(['gamma','resource_floor','weighting','flow_grid','policy']).relative_resources_ce.agg(['median','min','max']).reset_index()
pref_summary.to_csv(ROB/'preference_summary.csv',index=False)
display(pref_summary[pref_summary.policy.isin(['full','validated_shrinkage'])].round(5))
''')
    md("""## Historical tests without overlapping holding periods

For each horizon, we now partition the realized history into complete periods starting in 1980:
nine five-year periods, four ten-year periods and two twenty-year periods. An expanding training
sample ends before each period begins. Both public and CRSP versions use the same periods, a
5-percentage-point bond grid, six declared flows, gamma 4, a USD 1,000 resource floor and 5bp
half-spreads. Shrinkage tuning uses only pre-period simulation paths. Training weights the three
unique horizons equally, avoiding duplicated age cells.

Training rows must also have recorded publication dates before the portfolio decision. With the
panel's 15-day CPI lag, a January decision can use the joint real-return history only through the
previous November. We corrected the earlier December cutoff and recomputed both the rolling-cohort
and nonoverlapping WRDS/public historical tests. This enforces the recorded lag on revised extracts;
archival real-time data vintages are unavailable, so it is not a complete real-time-vintage backtest.

Return months do not overlap within a given horizon. Different flows and policies still share each
period; horizons also share months. Adjacent periods need not be statistically independent. Therefore
we report period outcomes and certainty equivalents across the actual number of periods, without a
pooled significance test. Two twenty-year observations cannot establish population predictability.
""")
    code('''historical=pd.concat([pd.read_csv(ROB/(d+'_nonoverlap.csv')) for d in ['wrds','public']],ignore_index=True)
reference=historical[historical.policy.eq('horizon_only')][['dataset','horizon','start_year','q','resources','success','unmet']]
historical=historical.merge(reference,on=['dataset','horizon','start_year','q'],suffixes=('','_restricted'),validate='many_to_one')
assert (pd.to_datetime(historical.latest_training_publication)<pd.to_datetime(historical.decision_date)).all()
historical['relative_realized_resources']=historical.resources/historical.resources_restricted-1
period_summary=historical.groupby(['dataset','horizon','start_year','end_year','policy']).relative_realized_resources.mean().reset_index()
period_summary.to_csv(ROB/'nonoverlap_period_summary.csv',index=False)
ce_rows=[]
for (dataset,horizon,policy),g in historical.groupby(['dataset','horizon','policy']):
    ce_deltas=[]
    for q,cell in g.groupby('q'):
        a=np.maximum(cell.resources.to_numpy(),1000.)
        b=np.maximum(cell.resources_restricted.to_numpy(),1000.)
        ce_deltas.append((np.mean(a**-3)/np.mean(b**-3))**(-1/3)-1)
    draws=g[g.q>0]
    ce_rows.append({'dataset':dataset,'horizon':horizon,'policy':policy,'nonoverlapping_periods':g.start_year.nunique(),
        'mean_flow_relative_ce':np.mean(ce_deltas),'draw_success':draws.success.mean(),
        'draw_success_difference_pp':100*(draws.success.astype(float)-draws.success_restricted.astype(float)).mean(),
        'mean_draw_unmet':draws.unmet.mean()})
historical_ce=pd.DataFrame(ce_rows)
historical_ce.to_csv(ROB/'nonoverlap_ce_summary.csv',index=False)
display(historical_ce[historical_ce.policy.isin(['full','validated_shrinkage','flow_only'])].round(5))
fig,axes=plt.subplots(1,3,figsize=(13,3.8),layout='constrained')
for ax,h in zip(axes,[5,10,20]):
    for dataset,marker in [('wrds','o'),('public','x')]:
        g=period_summary[period_summary.dataset.eq(dataset)&period_summary.horizon.eq(h)&period_summary.policy.eq('full')]
        ax.plot(g.start_year,100*g.relative_realized_resources,marker=marker,label=dataset)
    ax.axhline(0,color='black',lw=1)
    ax.set(title=f'{h}-year periods',xlabel='First test year',ylabel='Mean realized resources difference (%)')
axes[0].legend(frameon=False)
export('robustness_nonoverlap_periods')
''')
    md("""## Resampling training history and refitting the rule

The earlier paired-path interval holds the fitted rule fixed. Here 100 stationary-bootstrap histories
resample the joint return/inflation vector, with a mean block length of 12 months. Each pseudo-history
refits a 12-month-block training generator and the portfolio rules on 2,000 paths, including a 1,000/1,000
fit/validation split for alpha. Common inner simulation innovations reduce variation from unrelated
random numbers. We evaluate every refitted rule against its refitted restricted comparator using the
same reference future grid of 10,000 paths from the original automatic-block generator.

This follows the refitting logic of the [stationary bootstrap, Politis and Romano (1994)](https://doi.org/10.1080/01621459.1994.10476870).
The 2.5th-97.5th percentile range measures refit sensitivity under this design. It combines training
history variation, the specified 12-month training dependence model and finite inner fitting noise.
It conditions on the fixed reference future model and does not provide a confidence interval covering
all future return uncertainty. One hundred refits provide only a coarse estimate of the tails.
""")
    code('''refits=pd.read_csv(ROB/'history_refit_scores.csv')
refit_summary=refits.groupby('policy').relative_resources_ce.agg(repetitions='size',median='median',
    q025=lambda x:x.quantile(.025),q975=lambda x:x.quantile(.975),positive_fraction=lambda x:(x>0).mean()).reset_index()
refit_summary.to_csv(ROB/'history_refit_summary.csv',index=False)
display(refit_summary.round(5))
full_refit=refit_summary[refit_summary.policy.eq('full')].iloc[0]
display(Markdown(f"Only {full_refit.positive_fraction:.0%} of history refits produce a positive conditional-rule CE difference. Its median is {full_refit['median']:.2%}, and its central refit range is [{full_refit.q025:.2%}, {full_refit.q975:.2%}]. The sign is not stable under this refitting design."))
fig,ax=plt.subplots(figsize=(9,4))
for policy in ['full','flow_only','validated_shrinkage']:
    values=100*refits.loc[refits.policy.eq(policy),'relative_resources_ce']
    ax.hist(values,bins=20,alpha=.4,label=policy)
ax.axvline(0,color='black',lw=1)
ax.set(xlabel='Resources CE vs refitted horizon-only rule (%)',ylabel='Number of history refits',
       title='Training-history refit sensitivity; fixed reference future model')
ax.legend(frameon=False)
export('robustness_history_refits')
display(pd.DataFrame([json.loads((ROB/'verification.json').read_text())]).T.rename(columns={0:'verification'}))
''')
