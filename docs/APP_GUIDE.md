# LIFECYCLE — application rundown

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

## 4. The pages (one unified application)

There is one page per route — no generation tabs. The sidebar is generated from
`web/lib/research/routes.ts` and groups the 13 pages; each page has a "How to use this page" panel, the
shared **research context ribbon**, domain-named sections (`?section=…`, deep-linkable with `#VIZ-ID`),
a related-pages footer, and an information button on every visualization.

| Group | Page | Route | Sections | Main question |
|---|---|---|---|---|
| Research Home | Overview | `/` | hero, findings, page guide, question navigator, workflow, health, journeys | Where to begin; what is established |
| Lifecycle & Portfolio Planning | Withdrawal Lab | `/withdrawal-lab` | overview · sustainability · bond-necessity · utility · outcomes · robustness · paths | When do bonds improve survival, at which withdrawal rates? |
| | Lifecycle & Cash Flows | `/lifecycle-flows` | overview · simulator · policies · funding · household | Does signed net cash flow guide allocation better than age? |
| | Permanent Portfolio | `/permanent-portfolio` | overview · conditional · composition · history | When does the four-sleeve design help, and which sleeve matters? |
| | Rebalancing & Execution | `/rebalance` | overview · costs · cash-flows · rules · ledger | Which trading rule is worth its cost? |
| | Portfolio Optimization | `/optimize` | overview · policy-family · dynamic · surfaces · attribution · robustness | Which allocation is optimal under which objective? |
| Markets & Risk Research | Fixed Income & Credit | `/fixed-income` | curves · risk · returns · liabilities · credit | How much duration, and which bonds? |
| | Market State | `/market-state` | snapshot · dependence · releases · conditional | What do dated public observations say now? |
| | Scenarios & Risk | `/scenarios` | historical-analytics · dependence · factors · regimes · generators · stress · diagnostics | Are the generators credible; how do portfolios fare under stress? |
| Research Validation | Strategy Comparison | `/compare` | policies · saved-runs · history · attribution · robustness | Which policy wins on identical paths, and robustly? |
| | Research & Evidence | `/research` | hypotheses · validation · uncertainty · oos · data-quality · conclusions | What does the evidence support? |
| | Runs & Reports | `/runs` | registry · reproduce · figures · health | Can every number be reproduced? |
| | Methodology & Data | `/methodology` | pipeline · mathematics · data · references · limitations · reproduce · visualizations | How is every number produced? |

**Where the original modules went** (details and acceptance tests: [`PRESERVATION_MATRIX.md`](PRESERVATION_MATRIX.md)):
CE utility sweeps → Withdrawal Lab › Utility & Welfare (WL-13…15); interactive simulator → Lifecycle ›
Simulator (EX-01…06); research lab → Scenarios › Historical analytics / Dependence / Regimes / Factors
(SC-13…25); policy family and grid DP → Optimization (OP-13…17); sweep attribution → Optimization ›
Attribution (OP-11/12); saved-run comparison → Strategy Comparison › Saved runs (CO-11…13); run
validation and H1–H4 → Research (RS-11…18); run history → Runs › Registry (RN-11); mathematical notes →
Methodology › Mathematics (MT-08); original fixed-income panel → Fixed Income (instance views of FI-02/03/05/07).

**Retired routes** redirect (query preserved): `/lab` → `/scenarios?section=historical-analytics`,
`/lab/fixed-income` → `/fixed-income`, `/simulate` → `/lifecycle-flows?section=simulator`.

**Shared research context** (`web/lib/store.ts`, `useResearchContext`): investor, scenario, preferences,
costs, withdrawal, horizon, as-of date and the comparison policy set. Every study header has
"Run with current assumptions", which maps the context to that study's strict spec
(`web/lib/research/context.ts`; validated against the strict backend models in
`test_unified_app.py`). Pages never launch computation on load: they look up the latest persisted run.

**Cross-page workflow:** Permanent Portfolio › Overview › "Compare with 60/40" carries the selected
policies into Strategy Comparison (URL + context). Gold-holding variants have no gold-free equivalent in
the comparison universe, so they are compared within the PP study (PP-02) and the page says so.

**Engine semantics.** Runs from the original target-weight kernel (experiments, sweeps, saved-run
comparisons, validations, attributions) and from the holdings ledger (research studies) coexist; every run
reports `semantics` (`GET /v1/runs`, `/v1/runs/{id}/inspect`), and `/v1/runs/compatibility` refuses to pair
runs from different engines.

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

## 7. Code map

```text
backend/lifecycle/
  engine/lifecycle/ledger.py        Numba holdings ledger, trading triggers, funding orders, trace
  engine/scenarios/pit_signals.py   point-in-time regime signals (filtered, lagged, oracle)
  studies/*.py, studies/registry.py the nine research studies (job kinds → spec, runner, page)
  api/routers/v2.py                 studies, market state, fixed income, runs (+ semantics), figures, methodology
backend/tests/test_unified_app.py   context specs vs strict models, unified run registry, semantics
web/lib/research/routes.ts          pages, groups, sections, research questions, workflow, journeys
web/lib/research/visualization-registry.ts  (+ viz/*.ts) explanation of every visualization
web/lib/research/context.ts         research context → study spec
web/components/visualizations/      VisualizationFrame, VisualizationInfo, ResearchTable, provenance, charts, Plot
web/components/research/kit.tsx     StudyGate (lookup, run default / with current assumptions), KPIs, layout helpers
web/components/research/page.tsx    ResearchPage layout, sections (Sec), context ribbon, how-to
web/components/research/<domain>/   modules carried over from the original pages
web/components/pages/*.tsx          the 13 pages
web/tests/unit/visualization-registry.test.ts, research-context.test.ts; web/tests/e2e/unified.spec.ts
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
