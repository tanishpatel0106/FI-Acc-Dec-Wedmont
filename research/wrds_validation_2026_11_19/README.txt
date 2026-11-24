Fixed-income allocation: completed public and WRDS validation
November 19, 2026 (America/New_York)

Read research/wrds_validation_2026_11_19/wrds_validation.html for the new WRDS findings.
Read research/followup_2026_11_19/fixed_income_validation.html for the original audit and public-data baseline.
Both English notebooks are executed and include methods, citations, numerical tables and figures.

New findings

At 5% initial annual real withdrawals, the 2002-2013 calibration gives a highest 30-year spending-success
probability of 89.23% for the public reconstruction and 90.71% when only Treasury
returns are replaced by CRSP. The latter reaches the 90% target first at 40% bonds on the tested grid.
Using all CRSP core inputs over 2002-2024 gives 88.73% at the best tested allocation. The result depends
on the return source, sample and scenario generator; there is no supported universal bond minimum.

The corrected three-asset WRDS age-plus-flow rule changes resources CE by 0.10% versus age-only
(95% paired interval -0.08% to 0.33%, including zero). Five simulation seeds give a range
of -0.09% to 0.19%. The initial six-asset 0.61% estimate is superseded: unused Treasury
assets changed the automatically fitted block length and prevented a matched comparison.

Only 56% of 100 training-history refits produce a positive CE difference. The central refit range is
-1.73% to 1.82%; this is sensitivity conditional on a fixed future model, not a
general confidence interval. Completed nonoverlapping tests contain nine five-year, four ten-year
and two twenty-year periods per dataset. No consistent superiority of the conditional rule is established.
At 5% withdrawals, utility and spending-success optimization select 35% and 5% bonds respectively.
The utility policy gains 9.69% CE and changes success by -1.59 percentage points on independent test paths.

These return-based experiments do not estimate household age effects on risk tolerance or capacity.

Completed checks

12 matched-window frontier studies; 384 earlier chronological age/flow cells; four verified extraction hashes;
zero invalid restricted returns or duplicate month/series records; exact frontier and signed-flow
reproduction; 111 backend tests and four analytical robustness tests. The extension adds 26 sensitivity
configurations, 100 history refits and 900 policy/flow outcomes across 30 complete nonoverlapping periods
(15 per dataset; horizons share months). The earlier frontend checks remain 230 unit tests, 26 browser tests,
type-check and production build passed. The existing lint warning and six dependency advisories remain
documented in the public report. The full 12-sleeve multi-asset study and Permanent Portfolio now run.

Reproduction

The source patch at research/followup_2026_11_19/source_changes.patch applies to 4b0c23ec63f760feb8bcfbaecddd5746921f21d4.
Clone the original project, check out that commit, apply the patch, and copy the two research output
folders into its research directory. Aggregate notebook execution does not require WRDS. Recomputing
restricted return-based studies requires an entitled WRDS academic account and the documented Cloud
extraction process. The raw CRSP/TRACE files are excluded from this package and Git. Review the notebook
for source-specific date ranges, partial-inception-month exclusions and uncertainty definitions.

WRDS access is complete. Employer installation still awaits the employer reply and GitHub username.
No external messages have been sent. No meeting recording or transcript was located in the sources searched.
