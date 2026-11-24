Fixed-income research follow-up
November 19, 2026 (America/New_York)

Open fixed_income_validation.html for the executed report. The accompanying notebook contains English
methods, dataset selection, source citations, five figures and the computed tables.

The starting point is Tanish's main branch at 4b0c23ec63f760feb8bcfbaecddd5746921f21d4.
The local continuation branch is codex/validation-and-employer-handoff.
source_changes.patch applies the code and setup changes to that starting point.

Changes completed

- Fixed the clean-checkout TypeScript error and updated Next.js to 16.4.6.
- Aligned consumption utility and withdrawal-success horizons.
- Preserved declared short horizons for young investors.
- Replaced cell-dispersion intervals with paired simulation-path bootstrap intervals.
- Corrected expected shortfall when most paths have zero spending loss.
- Included engine semantics in run identity and data-vintage stamps in dated-study specifications.
- Executed the public core studies, the January 2006 employer replay and the dated lifecycle simulator.
- Completed the multi-asset study, three age cohorts, four replay start dates, three estimation windows
  and six lifecycle ablations.
- Added observed IEF and GLD data in an isolated directory, with raw-response hashes and source URLs.
- Evaluated matched-window sources, estimation periods, trading costs, risk aversion and model sensitivity.
- Selected allocations on training paths and evaluated them on 10,000 independent test paths.
- Completed 11 chronological age/cash-flow holdouts, with 264 age/flow cells in the historical evaluation.
- Verified exact reproduction of the core frontier, signed-flow study and observed-IEF frontier.
- Verified 249 replay months per policy for nonnegative wealth, holdings reconciliation and information timing.

Verification

111 backend tests, 230 web unit tests and 26 browser workflow tests passed.
Type-check and production build passed. Lint has one existing React Hook Form warning.
The dependency audit still reports six advisories, recorded in npm_audit_after.json.

Main findings

At 5% withdrawals, the minimum feasible bond allocation depends on the estimation window and return source.
With September 2002–December 2013 calibration, reconstructed Treasury returns produce a best 30-year
withdrawal-success probability of 88.96%. Observed IEF returns produce 92.70% and a minimum 35% bond share
to reach the 90% target on the tested grid.

In the independent-path IEF evaluation at 5% withdrawals, the consumption-utility policy selected 35%
bonds and the success policy selected 5%. The former gained 12.20% consumption CE and lost 2.13 percentage
points of success probability on test paths.

The corrected default signed-flow model estimates a -0.38% resources CE change for age-plus-flow relative
to age-only, with a paired 95% interval of approximately -0.67% to -0.08%. Chronological results vary by
sample. The observed IEF tests tie at the 2008 and 2012 splits and show -1.89% at the 2015 split. Historical
cohorts overlap, so their results are descriptive.

Under the signed-flow model's resources objective and fixed horizons, ages 25–75 have the same selected
allocation surface. This is a consequence of the model specification. Empirical age relationships in
risk willingness and household capacity require the project's household-survey analysis.

The classic gold-based Permanent Portfolio now runs. Its CE difference versus 60/40 is +3.72%, with a
paired interval of about -4.86% to +11.81%, using the original modelled Treasury sleeve and observed GLD.

Reproduction

Install the locked backend environment following docs/SETUP.md, then run research/validate_followup.py
and research/validate_allocation_holdout.py as documented in the notebook. The original public snapshot
is committed in the upstream repository. Optional ETF validation uses data/validation_etfs. The delivered
observed_etf_monthly_returns.csv freezes the 550 IEF/GLD monthly returns. Restoring it reproduced the
exact observed-data catalog hash, as recorded in snapshot_reproduction.json.

For report execution and rendering, use an environment containing pandas, matplotlib, IPython, ipykernel,
nbformat, nbclient and nbconvert. Run research/build_followup_notebook.py followed by research/render_followup.py.
The observed report used pandas 3.0.1, matplotlib 3.11.2, nbformat 5.11.1, nbclient 0.11.0 and nbconvert 7.17.2.
The scientific backend used the upstream frozen uv.lock.

validation_manifest.json records the hashes of the numerical input files. Baseline outputs were exported
before the scientific corrections. Run records retain the actual source commit and catalog used when
they were computed. Dated-study cache identity now stamps the catalog for subsequent submissions.

Outstanding external dependencies

The employer has yet to reply with a GitHub username or confirm local installation. The connected account
has read access to Tanish's repository, so source changes are delivered as a local branch and patch.
WRDS authentication, Terms of Use acceptance and Cloud extraction are complete. The WRDS extension is
in ../wrds_validation_2026_11_19/wrds_validation.html and the accompanying English notebook. It adds
12 matched-window frontiers, two exact reproductions, 384 chronological age/flow cells, independent-path
allocation evaluation and the full 12-sleeve multi-asset universe. Raw WRDS data are excluded from this
package. The historical training comparisons begin in May 1953 and end in December 2024.
The updated extension explicitly matches the signed-flow universe to three assets. The earlier 0.61%
six-asset WRDS estimate is superseded by +0.10% with a paired 95% interval of -0.08% to +0.33%.
It adds 26 sensitivity configurations, 100 training-history refits and 15 complete nonoverlapping
periods per dataset (9 five-year, 4 ten-year and 2 twenty-year). Historical training respects the
recorded CPI publication lag. Four analytical robustness tests passed. These results do not establish
consistent superiority of the cash-flow-conditional rule over the horizon-only comparator.
The reviewed sources contain the Zoom invitation and follow-up email. A recording or transcript has yet
to be located.
