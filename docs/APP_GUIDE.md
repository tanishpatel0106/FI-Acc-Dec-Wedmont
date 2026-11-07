# LIFECYCLE v2 — application rundown

LIFECYCLE is a research terminal for one question: **when, why and in which form does defensive asset
allocation improve lifetime portfolio sustainability as an investor crosses from net contributions to net
withdrawals?** It is a Python research engine (NumPy/Numba/SciPy) behind a FastAPI service, with a
Next.js front end that only *displays* persisted, hashed backend runs — the browser never computes an
investment outcome.

Setup: [`docs/SETUP.md`](SETUP.md). Every chart, by ID: [`docs/VISUALIZATIONS.md`](VISUALIZATIONS.md).
Controls and data rights: [`GOVERNANCE.md`](../GOVERNANCE.md). Pre-analysis plan:
[`research/preregistration/`](../research/preregistration/).

---

## 1. How it fits together

```
public sources (FRED, Treasury, Fed GSW, NY Fed ACM, French, SSA)   WRDS (server-side only)
                 │                                                       │
                 └──────────────► raw vintages (data/raw/<group>/<date>) ◄┘
                                          │  normalize: one source per series, provenance,
                                          ▼  publication lags, content hashes
                          canonical monthly panel + series catalog  (catalog hash)
                                          │
                universes (core_long_history, core_duration, pp_modern_etf, liability_match, …)
                                          │
        scenario generators: historical cohorts · stationary bootstrap · Student-t · Markov switching ·
        yield-curve factor VAR   →  ScenarioTensor (paths × months × assets, real returns, inflation,
                                     regime + point-in-time decision signal)
                                          │
        v2 holdings ledger (Numba): desired / funded / unmet spending · signed planned q ·
        allocation targets × trading policy × funding order · executed-notional costs
                                          │
        studies (9 job kinds) → derived payload → run registry (SQLite) + data/runs/<id>/results.json
                                          │
        FastAPI /v1 (63 routes; RFC 9457 errors; SSE progress) → Next.js pages A–M (137 visualizations)
```

### Run identity and reproducibility

A run ID is the SHA-256 of `kind + canonical spec JSON`, where the spec is stamped with the current data
catalog hash. Identical specs return the cached result instantly; changing any semantic input (data, seed,
policy, costs, horizon, …) yields a new ID. Each run stores its spec, catalog hash, engine version (git
SHA), `uv.lock` hash, warnings and timings. `make reproduce RUN=<id>` re-executes the stored spec and
asserts every derived block is byte-identical. The engine semantic version is now **2.0** (`lifecycle/__init__.py`).

### Timing contract (every simulation)

Known state → planned flows (contribution or desired draw) → fund the flow by the funding order →
trading decision on post-flow weights → trades and costs → earn next month's returns → update wealth.
A test mutates future returns and checks that no earlier decision changes.

---

## 2. What changed from v1 (engine audit, brief §1.2)

| Audit item | v2 resolution |
|---|---|
| Latent regime look-ahead | Decisions use a **point-in-time signal**: for Markov-switching paths the Hamilton-filter prediction ξ<sub>t\|t−1</sub> computed on the simulated path; for bootstrap/cohorts the filtered label of the previous month. Applied to the legacy kernel too. The contemporaneous state is available only as a labelled **oracle** bound (OP-06). |
| Signed flow vs withdrawal | New exogenous `planned signed q` mode (`spend="signed"`), distinct from the initial withdrawal rate `r`. |
| Survival definitions | Fixed-horizon financial success, survival-while-alive (1 − E[S(τ)]) and severity (unmet $, CVaR) reported separately. |
| Shortfall accounting | Desired, funded and unmet spending are separate; utility uses funded consumption with a documented utility floor that is never counted as funded. |
| Trading/costs | Holdings ledger; costs on executed notional (commission + half spread + quadratic slippage); trade ledger and sources/uses reconciliation (RB-04). |
| Asset roles | `risky_mask` no longer drives v2 decisions; defensive/cash sleeves are explicit per study. |
| Benchmarks | All comparisons share one tensor, spending rule, costs and horizon; joint spending+allocation comparisons are labelled (CO-07). |
| Statistical evidence | Wilson CIs, path-pair bootstrap ΔCE CIs, joint bootstrap of b_min, Holm + BH adjustments, MC convergence, walk-forward OOS, permutation tests. |
| Data rights | Public/WRDS source classes, entitlement scanner, licence-aware exports; no gold proxy is spliced in. |

---

## 3. The nine studies

| Kind | Experiments | Default universe / scale | Produces |
|---|---|---|---|
| `frontier` | E01–E03 | `core_long_history`, 2,000 bootstrap paths, r 0–10% step 0.25pp × bond 0–100% step 5pp, horizons 10/20/30/40y, 200 joint bootstraps, Student-t + Markov alternatives, two calibration windows, γ 2/4/6/8 | survival surfaces, b_min feasible sets with bootstrap bands, breakpoints, max sustainable r, CE vs survival optima, first-shortfall and severity, bond-instrument spectrum, robustness forest, model agreement |
| `signed_flow` | E04–E05 | ages 25–85 × 19 planned q values (−15%…+10%) × 11 bond shares, train/test seed sets | q×age optimal bond surfaces, age-only / q-only / full OOS comparison, bootstrapped slopes ∂b*/∂q, funded-ratio map, synthetic lifecycle persona, accumulation contribution frontier |
| `permanent` | E13–E18 | `pp_modern_etf` (needs observed gold); falls back to `core_duration` without WRDS | 14 policies (classic 15/35, calendars, bands, duration/TIPS/cash-buffer variants, ablations, regime-adaptive, minimax-regret robust), scorecard, conditional advantage, macro quadrants, gold hedge stats, duration replacement, cash buffer, defensive simplex, cohorts, Shapley |
| `rebalance` | E19–E22 | `core_duration`, 55/35/10 target, 16 trading strategies, costs 0–20 bps, reserves 0–3y | efficiency frontier, calendar/band × cost heatmaps, cash-flow turnover savings, no-trade rule audit, liquidity runway, event stats, cost decomposition, funding race, risk-budget drift |
| `scenario_lab` | E23–E26 | all five generators on `core_duration` | generator diagnostics/verdicts, distribution & Q–Q, joint-downside (observed / modelled / OOS), regimes, copula tails, inflation scatter, stress library, shock timing, historical cohort map, PIT mismatch |
| `asof` | E29 | Markov switching on `core_long_history` | conditional vs unconditional fans and the change in the bond-necessity surface from the observed starting state |
| `optimize` | E07, E30, E33–E34 | static simplex of equity / 2Y / 10Y / 30Y / bills | Pareto set, regime surfaces, Shapley & marginal sleeve value, uncertainty band (path bootstrap, generators, parameter refits), funding-ratio surface, holdout policy classes incl. oracle, objective switch, risk budget, tornado, SLSQP trace |
| `compare_v2` | E24, E26, E36 | six policies vs 60/40 | paired forest, path scatter, twin fans, divergent paths, cohort winner matrix, trade-off table, order-free attribution, robustness forest, source substitution |
| `evidence` | E28, H1–H12 | reads the latest completed studies | hypothesis registry with Holm/BH, evidence matrix, MC convergence, walk-forward, permutation test, threshold ridge, leakage checklist, coverage audit, conclusion builder |

All defaults are visible and editable on each page (**Edit spec**), via `GET /v1/studies/{kind}/defaults`,
or on the Methodology page (MT-07).

---

## 4. The pages

Navigation (left sidebar) follows the brief's pages A–M. Every page has a context ribbon (universe,
window, generator, paths, benchmark, run, evidence), warnings (e.g. *model_generated returns*), and the
study header with run ID, catalog hash and finish time.

### A · `/` Research overview & command center (OV-01…08)
Headline verdict tiles with CIs, benchmark, universe, date and run ID — or "Not established" /
"No feasible allocation"; the signed-q continuum strip; a mini bond-necessity contour; the CE-optimal vs
survival-optimal KPI pair; the H1–H12 evidence matrix; a pipeline timeline with real timestamps (panel
build, tests, each study); the data coverage grid with staleness; and a "reproduce this figure" launcher.
The v1 overview is in the second tab.

### B · `/withdrawal-lab` Bond necessity & sustainable spending (WL-01…12, F1)
The central exhibit. A withdrawal × bond-share survival heatmap with the target contour (click any cell for
CI, CE, survival-while-alive, severity and a single-path funding-gap drilldown, WL-11); the b_min frontier
for 80/85/90/95% targets with bootstrap bands and shaded "no feasible allocation" regions; survival curves
by bond mix; maximum sustainable withdrawal (with the historical 4% rule as a reference only); CE- vs
survival-optimal shares; a threshold sensitivity forest (target, horizon, generator, window, γ);
first-shortfall timing (financial and alive-weighted); severity violins; model-disagreement overlay;
model-conditional allocation ranges by horizon; and FI-12 (bond instruments across withdrawal rates). The
v1 ΔCE heatmap is in the second tab.

### C · `/lifecycle-flows` Signed contributions → retirement → withdrawals (LC-01…08, F2)
The q × age optimal bond surface (CE or survival objective), age-only vs q-only vs full policies scored
out of sample, bootstrapped marginal slopes with a zero reference, the funded-ratio map on the TIPS real
curve with mortality, and a synthetic, labelled persona: wealth/consumption fans across age, policy
transition map with planned net flows, a narrated single path with rebalancing ticks and the governing
equations, and the accumulation contribution frontier (savings × start age).

### D · `/permanent-portfolio` Permanent Portfolio laboratory (PP-01…12, F3)
Sleeve matrix with exact canonical sources and measured exposures; paired scorecard vs 60/40; conditional
advantage by withdrawal × starting regime; growth × inflation quadrants (lagged, point-in-time
classification); regime-adaptive weight river; gold incremental utility and hedge statistics; duration
replacement with DV01; cash-buffer trade-off; defensive simplex (equity fixed at 25%); Browne band event
timeline (annual review; breaches between reviews do not trade); historical cohort race; Shapley ablation;
robust (minimax-regret) mix. **Without WRDS the gold sleeve is reported as unavailable** — the page shows
the failed gold run and the gold-free variants, never a proxy.

### E · `/rebalance` Rebalancing & cash-flow execution (RB-01…12, F4)
Net ΔCE vs turnover frontier by strategy family with CIs; calendar/band × cost heatmaps; cash-flow
turnover savings for contributors, zero-flow and withdrawers; the utility-net-of-cost rule's
accepted/rejected decisions and holdout ΔCE; liquidity runway fans; event statistics; commission / spread /
slippage decomposition and CE drag; withdrawal funding race; risk-budget drift with a lagged-estimate
validation; and a per-path trade audit (weights, trades, costs, triggers) with a sources-and-uses
waterfall whose residual checks the ledger.

### F · `/fixed-income` Rates, liability matching & credit (FI-01…14)
Nominal/real GSW curves (any month-end), 2/5/10/30Y history heatmap, duration/DV01/convexity, key-rate
durations whose sum is checked against effective duration, full repricing vs Taylor error, bear-steepener
/ bull-flattener grids for nominal and TIPS, monthly return decomposition with disclosed residual, PCA with
shape-checked labels, Baa−Aaa / Baa−10Y spreads, real liability PV with sensitivities, a TIPS-strip-style
cash-flow matching ladder against a budget, the bond-value spectrum, stock–bond co-loss regimes and their
shortfall consequence, and the credit-quality surface (unavailable without bond-level WRDS data; index
statistics shown instead). The v1 panel is in the second tab.

### G · `/market-state` Public-data as-of terminal (MS-01…12)
A per-source ribbon (latest observation, retrieval vintage, staleness, licence) with a backend
**Update** job; curves, 10Y nominal/real/breakeven with the ACM decomposition, a valuation dashboard,
rolling correlations with Fisher-z bands and DCC, filtered regime probabilities with model vintage, a
release timeline with a historical point-in-time selector, credit spreads, the WRDS ETF panel (or why it
is unavailable), and the refresh audit. The as-of selector replays any month using publication lags. The
`asof` study adds the conditional scenario fan (MS-07) and the scenario delta board (MS-10).

### H · `/scenarios` Scenario, dependence & stress (SC-01…12, F5)
Generator comparison with automatic pass/caution/fail checks; simulated vs historical distributions (Q–Q,
histograms); path fans and sample paths per generator; joint-downside frequencies (observed, modelled,
out-of-sample); rolling/DCC correlation with change points; Markov transition matrix, dwell times and
state uncertainty; t-copula vs empirical tail counts; inflation–rate–bond scatter; the synthetic stress
matrix (rate shock, inflation shock, −35% equity, 2022-like, stagflation, recession rally); shock timing
(year 0/5/10/20); actual cohort maps; PIT mismatch diagnostics with red flags.

### I · `/optimize` Multi-objective allocation (OP-01…10)
Pareto set in (failure, CE) space with the constraint region; regime and q×age weight surfaces; Shapley
and marginal sleeve values with CIs; an uncertainty band instead of a point optimum; funding-ratio policy
surface; static vs fitted glidepath vs regime-conditional vs **oracle** on holdout paths; the objective
switch (CE, success, CVaR, minimax regret, constrained CE); risk budget and duration; a parameter tornado;
the optimiser's actual trace with its convergence message. The v1 optimizer is in the second tab.

### J · `/compare` Policy & cohort comparison (CO-01…10, F6)
Paired ΔCE forest, per-path scatter with failures, twin fans, the most divergent paths with their
early-sequence explanation, a cohort winner matrix, a sortable trade-off table, order-free (Shapley)
attribution of allocation / spending / rebalancing / costs, robustness across generators and windows with
sign-reversal flags, public-vs-WRDS source substitution, and a first-failure timeline for the worst actual
cohort. `/compare?id=<run>` opens the legacy run-vs-run comparison tab.

### K · `/research` Hypotheses, validation & statistics (RS-01…10, F6)
The pre-registered H1–H12 table (estimate, CI, Holm/BH p, window, verdict, grade, run link), the evidence
heatmap, Monte Carlo convergence with an automatic stop rule, the b_min replication ridge, the
chronological walk-forward scoreboard, generator/parameter disagreement, a return-order permutation test,
coverage audit, an automated leakage checklist and a conclusion builder that writes only verified claims.

### L · `/runs` Reproduction, diagnostics & reports (RN-01…10)
Run registry (with cache hits from the audit log), inspector (spec, seeds, lock hash, git SHA,
provenance), live SSE progress with cancel/retry, the F1–F6 figure gallery, run compatibility checks,
the export centre (study JSON/CSV, experiment PDF/CSV/BibTeX, manifest), the reproduce command with
data/engine-change warnings, data health, paper build preview and the audit trail.

### M · `/methodology` Methodology (MT-01…07)
Pipeline diagram, an equation explorer (ledger, utility, bond necessity, CIs, duration, rebalancing,
filter), data dictionary, assumption registry, bibliography with live links, limitations and prohibited
interpretations, and CLI/API recipes with every study's default spec.

The v1 **Research Lab** (`/lab`) and **Lifecycle Simulator** (`/simulate`) remain as they were.

---

## 5. What the current public-data runs show (catalog `f0ce88a6493ff732`, 2026-11-07)

These come from the default studies on the committed public snapshot (US data 1953–2026; Treasury
returns are **model-generated** from CMT yields because WRDS is not ingested). They are model-conditional
research outputs at pilot-to-conditional evidence grades, not advice. Run IDs are in
`research/results/v2_run_ids.json`.

- **Bond necessity (F1, 30y, 90% target, bootstrap):** up to a 4.5% initial real withdrawal an
  all-equity portfolio already meets the target (b_min = 0). At 5% no equity/10Y mix meets 90% at the
  point estimate, and 97.5% of joint bootstrap replicates find no feasible mix (the few that do need 3–19%
  bonds). A withdrawal breakpoint (all-equity fails, a bond mix passes) is identified only for the 95% target
  (4.25%). Model sensitivity: Student-t, Markov switching and the 1953–1989 window also show no feasible mix
  at 5%; the 1990–2026 window identifies b_min = 10%. The CE-optimal bond share at 5% is 30% for every γ in
  2–8 on this grid.
- **CE vs survival (H9):** the CE-optimal bond share exceeds the survival-optimal share by 15pp at 4–5%
  withdrawal (e.g. 30% vs 15% at 5%); choosing survival costs ~3% of CE for ~1pp of success.
- **Signed flow (F2, H1/H2):** the bootstrapped slopes of the optimal bond share in q do not exclude zero
  at any key age, and the age-only policy is *not* beaten out of sample by the full (age + q) policy
  (+0.35% for age-only, CI 0.11%–0.58%) — both recorded as **contradicted**. A target-date glidepath loses
  ~5.8% CE relative to the cell-optimal policy on these surfaces.
- **Rebalancing (F4, H6):** against an annual calendar, band-edge rebalancing (+2.0% ΔCE, CI 1.0–3.1%)
  and a 20% relative band (+1.1%) help; monthly calendar (−4.3%), buy-and-hold (−5.3%) and a 2-year cash
  floor (−5.7%) hurt; cash-flow targeting is −0.9% (CI −1.3% to −0.6%) → H6 **contradicted** here.
- **Permanent Portfolio (F3, H5):** **not computed** — no observed gold series without WRDS. Gold-free
  variants on `core_duration` (50% cash) trail 60/40 by ~20% CE.
- **Evidence (H1–H12):** supported (conditional grade) H4, H8, H9, H12; contradicted H1, H2, H6; fragile
  H3, H7, H10, H11; not computed H5. Every claim carries its run ID; the automated leakage checklist
  passes, with one warning (ALFRED vintages not ingested).

---

## 6. API quick reference

| Area | Routes |
|---|---|
| Studies | `GET /v1/studies`, `GET/POST /v1/studies/{kind}` (`?submit=false` = lookup only, `?force=true`), `GET /v1/studies/{kind}/latest`, `GET /v1/studies/{kind}/defaults`, `GET /v1/studies/run/{id}`, `…/trace?path=&r=&b=&strategy=&policy=`, `…/export?format=json\|csv&block=` |
| Brief aliases | `POST /v1/research/{frontier\|signed-flow\|permanent-portfolio\|rebalance\|stress\|walk-forward\|asof\|optimize\|compare}`, `GET /v1/research-v2/hypotheses`, `GET /v1/research-v2/evidence/{id}` |
| Market state | `GET /v1/market-state/latest`, `/{as_of}`, `/curve`, `/ribbon`, `/audit`, `/pit?series_id=&as_of=` |
| Fixed income | `GET /v1/fixed-income/{key-rates,twist,taylor,liability-gap,ladder,coloss,credit}` |
| Data | `GET /v1/data/{entitlements,coverage,vintages,health}`, `POST /v1/data/refresh?group=treasury_daily\|public_snapshot` (WRDS refresh is CLI-only → 403) |
| Runs & reports | `GET /v1/runs/{id}/inspect`, `GET /v1/runs/compatibility?a=&b=`, `GET /v1/audit`, `GET /v1/results/{figures,manifest}`, `POST /v1/reports/build`, `GET /v1/paper/preview` |
| Methodology | `GET /v1/methodology/{assumptions,bibliography,bibtex}`, `GET /v1/overview/v2` |
| v1 (unchanged) | `/v1/experiments…`, `/v1/sweeps…`, `/v1/compare…`, `/v1/validation/{id}`, `/v1/attribution/{id}`, `/v1/reports/{id}`, `/v1/market/…`, `/v1/catalog/series`, `/v1/overview` |

---

## 7. Code map (new in v2)

```text
backend/lifecycle/
  engine/lifecycle/ledger.py        Numba holdings ledger, trading triggers, funding orders, trace
  engine/scenarios/pit_signals.py   point-in-time regime signals (filtered, lagged, oracle)
  studies/common.py                 shared specs, ledger runner, statistics (Wilson, paired ΔCE, severity)
  studies/{frontier,signed_flow,permanent,rebalance,scenario_lab,asof,optimize_v2,compare_v2,evidence}.py
  studies/registry.py               job kinds → spec model, runner, page
  market_state.py, fixed_income_v2.py  derived market and rates views
  data/ingest_treasury_daily.py     official Treasury daily par curves (separate daily store)
  data/entitlements.py              WRDS entitlement scan + source-rights registry
  api/routers/v2.py                 all v2 routes
backend/tests/test_v2_engine.py, test_v2_studies.py
research/preregistration/         hypotheses_v2.json (machine-readable), analysis_plan.md
research/results/v2_run_ids.json  run IDs of the default studies
web/lib/api/v2.ts                 study hooks (lookup / submit / trace / export)
web/components/v2/{kit,charts}.tsx Viz frame, StudyGate, tables, tabs; Plotly chart kit
web/components/pages/v2/*.tsx      pages A–M
web/app/{lifecycle-flows,permanent-portfolio,rebalance,fixed-income,market-state,scenarios,research}/
```

---

## 8. Known limitations

- Public mode uses **model-generated Treasury/TIPS/IG returns** repriced from yields; ingest WRDS CRSP to
  replace them with observed returns. Duration-specific findings are conditional until then.
- **No observed gold** without WRDS, so classic Permanent Portfolio results (H5) are not computed.
- **ALFRED real-time vintages** are not ingested; revised macro series are descriptive only.
- The Treasury daily feed needs outbound network access; this sandbox could not reach it, so that adapter
  is implemented but was not exercised against the live endpoint.
- The Browne 15/35 rule is defined for equal sleeves; on unequal targets (e.g. 55/35/10) it trades at every
  review, which the rebalancing page states.
- Monte Carlo CIs are conditional on the fitted model; parameter and model uncertainty are shown
  separately. Cohort results overlap and carry no iid CIs. No taxes or tax lots are modelled.
- The signed-flow surface has no human-capital channel (age enters via horizon and survival); the persona
  adds labour income explicitly.
