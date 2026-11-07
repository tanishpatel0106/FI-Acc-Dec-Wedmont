# Feature-preservation matrix (consolidation audit)

Audit of every user-facing capability in the two page trees that existed at commit `720f1ff`
(`web/components/pages/*` and `web/components/pages/v2/*`), where it lives in the unified application,
and how it was verified. "Reuse" = same component moved/re-wrapped; "Combine" = merged into an existing
visualization with a toggle; "Refactor" = same calculation and API, new layout.

Verification legend: **E2E** = Playwright workflow/route test (`web/tests/e2e`), **REG** = covered by the
visualization-registry coverage test (`web/tests/unit/visualization-registry.test.ts`), **API** = backend
test, **MAN** = manually checked in a headless browser run against the seeded public panel.

## Original pages (pre-v2)

| # | Original route / component | Capability | Visualizations / tables | API | Destination (route · section) | Method | Viz IDs | Verified |
|---|---|---|---|---|---|---|---|---|
| 1 | `/` `Overview` | headline v1 sweep results, universe windows, run counts, module tiles | KPI tiles; bento module tiles | `/v1/overview`, `/v1/catalog/series` | `/` · Research status & key findings | Refactor (KPIs → OV-09; tiles → page guide) | OV-09 | REG, E2E |
| 2 | `/lab` `ResearchLab` · Returns | return moments, drawdowns, rolling vol, correlation | moments table, drawdowns, rolling 36m vol, correlation heatmap | `/v1/market/returns/summary` | `/scenarios?section=historical-analytics` | Reuse | SC-13, SC-14, SC-15, SC-16 | REG, E2E |
| 3 | `/lab` · Dependence | asset-pair rolling corr + DCC + PELT, joint loss by decade, inflation conditioning, t-copula, covariance forecast horse race | 5 panels | `/v1/market/dependence` | `/scenarios?section=dependence` | Reuse | SC-17 … SC-21 | REG, E2E |
| 4 | `/lab` · Regimes | filtered/smoothed probabilities, K=2/3, NBER overlay, regime means, transition + BIC | 3 panels | `/v1/market/regimes` | `/scenarios?section=regimes` | Reuse | SC-22, SC-23, SC-24 | REG, E2E |
| 5 | `/lab` · Factors | Fama–French factor regressions | table | `/v1/market/factors` | `/scenarios?section=factors` | Reuse | SC-25 | REG, E2E |
| 6 | `/lab/fixed-income` `FixedIncome` · curves | zero curves (+1y ago, TIPS), yield history | 2 charts | `/v1/market/yield-curve` | `/fixed-income?section=curves` | Combine (FI-01 already plots identical series; history lines added to FI-02 as a view) | FI-01, FI-02 | REG, MAN |
| 7 | `/lab/fixed-income` · PCA | PCA loadings with checked labels | 1 chart | same | `/fixed-income?section=curves` | Superseded by identical FI-08 (same endpoint fields) | FI-08 | REG |
| 8 | `/lab/fixed-income` · risk | par-bond risk table (Macaulay, modified, convexity, DV01), parallel-shock bars full vs approx, twist summary | table + chart + text | same | `/fixed-income?section=risk` | Combine (Macaulay table and full-vs-approx bars added to FI-03/FI-05; twists in FI-06) | FI-03, FI-05, FI-06 | REG, MAN |
| 9 | `/lab/fixed-income` · decomposition | monthly 10Y return decomposition (stacked bars + total) | 1 chart | same | `/fixed-income?section=returns` | Combine (time-series view added to FI-07) | FI-07 | REG |
| 10 | `/lab/fixed-income` · KPIs | curve date, 10Y par, liability PV/duration | KPI tiles | same | `/fixed-income` header | Reuse | – | MAN |
| 11 | `/simulate` `Simulator` | investor builder (`InvestorForm`), URL-persisted spec, run + SSE progress, cache hits | form; result summary | `/v1/experiments*`, SSE | `/lifecycle-flows?section=simulator` | Reuse (same form/store; store renamed research context) | EX-01 … EX-06 | REG, E2E |
| 12 | `ResultSummary` (shared) | headline stats, wealth fan, consumption fan, weights by age, depletion by age, DP surface, Arrow sample paths, provenance | 6 charts | `/v1/experiments/{id}/results`, `/paths` | simulator, withdrawal path explorer, optimizer cards, run inspector | Reuse | EX-01 … EX-06 | REG |
| 13 | `/optimize` `Optimizer` · family | 10-policy family run, ΔCE bars with paired SE, growth share by age, policy cards | 2 charts + cards | `/v1/experiments` | `/optimize?section=policy-family` | Reuse | OP-13, OP-14 | REG, E2E |
| 14 | `/optimize` · DP | grid DP solve, equity weight (age × cash-on-hand), equity vs q, weight path, H1 slope | 3 charts + KPIs | `/v1/experiments` (`policy.type=dp`) | `/optimize?section=dynamic` | Reuse | OP-15, OP-16, OP-17 | REG |
| 15 | `/withdrawal-lab` `WithdrawalLab` | v1 ΔCE sweeps (decumulation/accumulation), benchmark switch, SE hatching, depletion heatmap, generator disagreement, cell detail → compare | 3 charts + cell drill-down | `/v1/sweeps*`, `/v1/compare` | `/withdrawal-lab?section=utility` (+ disagreement in robustness) | Reuse | WL-13, WL-14, WL-15 | REG, E2E |
| 16 | `/compare` `Compare` · comparison | saved-run picker (2–4 runs), common-path table, paired path scatter, divergent paths | table + 2 charts | `/v1/compare*` | `/compare?section=saved-runs` | Reuse | CO-11, CO-12, CO-13 | REG, E2E |
| 17 | `/compare` · validation | MC convergence, parameter bootstrap, model uncertainty, sequence risk, calibration windows, tail coverage, cohort replay, robust verdict | 7 charts/tables + KPIs | `/v1/validation/{id}` | `/research?section=validation` | Reuse | RS-12 … RS-18 | REG |
| 18 | `/compare` · attribution | Shapley MU by regime, marginal MU table | chart + table | `/v1/attribution/{sweep}` | `/optimize?section=attribution` | Reuse | OP-11, OP-12 | REG |
| 19 | `/compare` · hypotheses | H1–H4 tests (v1) | cards | `/v1/research/hypotheses` | `/research?section=hypotheses` | Reuse | RS-11 | REG |
| 20 | `/runs` `Runs` | day-grouped run timeline, run detail (spec, timings, warnings, PDF/CSV/BibTeX/JSON, reproduce, ResultSummary) | timeline | `/v1/experiments*`, `/v1/reports/{id}` | `/runs?section=registry` | Combine (timeline view of RN-01; detail merged into RN-02) | RN-01, RN-02, RN-11 | REG, E2E |
| 21 | `/methodology` `Methodology` | formulas: wealth, income, utility/CE/SE, shortfall, DP/parametric, generators table, FI, data table, limitations, references | article | `/v1/catalog/series` | `/methodology?section=mathematics` | Reuse | MT-08 | REG |

## v2 pages

| v2 page | Destination | Change | Viz IDs |
|---|---|---|---|
| `OverviewV2` | `/` | expanded into the application guide; OV-01…08 retained | OV-01 … OV-08 |
| `WithdrawalLabV2` | `/withdrawal-lab` | split into domain sections | WL-01 … WL-12, FI-12 |
| `LifecycleFlows` | `/lifecycle-flows` | sections; simulator integrated | LC-01 … LC-08, LC-01b |
| `PermanentPortfolio` | `/permanent-portfolio` | sections; "Compare with 60/40" workflow | PP-01 … PP-12, PP-robust |
| `Rebalance` | `/rebalance` | sections | RB-01 … RB-12 |
| `FixedIncomeV2` | `/fixed-income` | sections; legacy panel combined | FI-01 … FI-14 |
| `MarketState` | `/market-state` | sections | MS-01 … MS-12 |
| `Scenarios` | `/scenarios` | sections; Research Lab absorbed | SC-01 … SC-12 |
| `OptimizeV2` | `/optimize` | sections; v1 optimizer + DP + attribution integrated | OP-01 … OP-10 |
| `CompareV2` | `/compare` | sections; saved-run comparison first-class; comparison builder | CO-01 … CO-10 |
| `Research` | `/research` | sections; H1–H4 and run validation integrated | RS-01 … RS-10 |
| `RunsV2` | `/runs` | sections; one registry for all run kinds | RN-01 … RN-10 |
| `MethodologyV2` | `/methodology` | sections; mathematical notes + visualization reference | MT-01 … MT-07 |

## Retired navigation and routes

| Old | Now | Behaviour |
|---|---|---|
| sidebar "Research Lab (v1)" `/lab` | Scenarios & Risk | permanent redirect → `/scenarios?section=historical-analytics` (query preserved) |
| `/lab/fixed-income` | Fixed Income & Credit | redirect → `/fixed-income` |
| sidebar "Lifecycle Simulator (v1)" `/simulate` | Lifecycle & Cash Flows | redirect → `/lifecycle-flows?section=simulator` (spec query params preserved) |
| v2/legacy page tabs on 7 pages | domain-named sections | removed |
| `/compare?id=<compare run>` | Strategy Comparison → Saved-run comparison | deep link opens the saved-run section |
| `/runs?id=<run>` | Runs & Reports → Registry | deep link selects the run |

## Backend

No scientific code was removed. v1 job kinds (`experiment`, `sweep`, `compare`, `validation`, `attribution`,
`hypotheses`) and v2 study kinds share one registry. Each run now reports its accounting semantics
(`legacy_target_weight_kernel` or `holdings_ledger_v2`) via `GET /v1/runs`, and comparisons across the two
families are flagged by `/v1/runs/compatibility`.
