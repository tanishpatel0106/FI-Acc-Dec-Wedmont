# LIFECYCLE

Multi-asset portfolio optimisation and lifetime-utility research platform (Wedmont Private Capital × Columbia).

**Question.** How should an investor allocate across asset classes as contribution rate, withdrawal rate, horizon, wealth and
the economic regime change, and what is that worth in certainty-equivalent (CE) consumption?

**Headline exhibit.** A ΔCE heatmap (withdrawal rate 2–8% × years relative to retirement) of the optimised policy versus
60/40, target-date or the best constant mix. Click any cell to see the policy, its consumption fan, shortfall risk and the exact
spec, then regenerate it from its run ID.

Every number on screen comes from a versioned, reproducible backend run. The frontend never computes analytics.

---

## Quick start (local)

Requirements: Python 3.12 with [`uv`](https://docs.astral.sh/uv/), Node 22.

```bash
cp .env.example .env          # add WRDS_USERNAME / WRDS_PASSWORD (optional until you ingest WRDS)
make setup                    # backend/.venv (uv) + web/node_modules
make data                     # public data: French library, FRED, Fed GSW curves, NY Fed ACM, SSA life table
make seed                     # core exhibits: headline heatmaps, baselines, DP (about 20 min on a 4-core laptop)
make dev                      # API on :8000 + web on :3000
```

Open <http://localhost:3000>.

### Adding WRDS

```bash
make ingest-wrds              # one WRDS connection for all pulls -> approve the single Duo push on your phone
make seed                     # new catalog hash -> new run IDs; old runs stay addressable
```

`make ingest-wrds` pulls CRSP index (`crsp.msi`), Treasury & CPI (`crsp.mcti`), fixed-term and risk-free files
(`crsp.tfz_mth_ft`, `crsp.tfz_mth_rf`), Fama–French factors, the WRDS Bond Returns value-weighted IG/HY indexes (aggregated
server-side) and ETF proxies (EFA, EEM, LQD, TIP, VNQ, IEF, TLT, GLD; PERMNOs resolved by ticker *and* date range). Tables are
resolved at runtime (legacy SIZ and CIZ `_v2` names), and missing columns are reported rather than silently dropped.
WRDS series take priority over public ones automatically (`backend/lifecycle/data/normalize.py`), and every run records the
catalog hash it consumed. Raw WRDS observations never leave the server: the API returns derived statistics only.

Without WRDS the platform runs on public data, and the UI flags it ("Public data (WRDS pending)"). The following are
model-generated: Treasury, TIPS and IG returns repriced from FRED constant-maturity yields (a par bond bought at last month's
yield is repriced at this month's, so yields are never used as returns). They carry `provenance = model_generated`.

---

## What is implemented

| Layer | Contents |
| --- | --- |
| Data (`backend/lifecycle/data`) | WRDS + public ingestion scripts, canonical long-format panel (Parquet) with the §3.4 contract, series catalog with content hashes, two universes with per-series truncation recorded (assets never enter a window they do not cover) |
| M1 dependence | rolling 12/36/60m and inflation-regime correlation, joint-loss frequencies by decade/regime, Ledoit–Wolf, DCC-GARCH(1,1), Student-t copula tail dependence, PELT change points, out-of-sample QLIKE horse race |
| M2 fixed income | pricing, Macaulay/modified duration, DV01, convexity, shock tables (full repricing vs approximation), twists, PCA of yield changes with checked labels, carry/roll-down/Δy/convexity decomposition, TIPS-curve liability PV and duration gap |
| M3 scenarios | historical cohorts, stationary block bootstrap (Politis–White), multivariate Student-t (ML ν, shrunk scatter), Markov switching (EM, Hamilton filter + Kim smoother, BIC), yield-curve factor VAR; chunked `SeedSequence.spawn` generation |
| M4 lifecycle | Numba path kernel: CGM income, pension, fixed-real / fixed-% / guardrails / bucket / amortised spending, rebalancing costs, SSA mortality, bequest, C_min floor with explicit shortfall and infeasibility flags |
| M5 optimisation | mean–variance, risk parity, mean–CVaR (HiGHS LP), static CRRA (SLSQP on simulated paths), regime-dependent mixes, parametric dynamic policies (train/test seeds), grid DP on the reduced 3-asset × regime problem |
| M6 attribution | marginal asset-class utility with paired SE, exact Shapley values over sleeves, unconditional and by starting regime, sequence-risk permutation |
| Runs | frozen `ExperimentSpec` → SHA-256 run ID (cache hits return immediately), SQLite registry, SSE progress, sweeps whose cells are themselves addressable runs, compare, validation (MC convergence, parameter bootstrap, model disagreement, cohort replay, robustness verdict), H1–H4 tests, PDF/CSV/BibTeX/JSON reports |
| API (`/v1`) | every endpoint in brief §7.4, RFC 9457 errors, Arrow IPC for path arrays, run metadata on every response |
| Web (`web/`) | Next.js 16 App Router, Tailwind v4, shadcn/ui (Base UI), Aceternity UI, Plotly; Overview, Research Lab, Fixed Income, Simulator, Optimizer, Withdrawal Lab, Compare & Validate, Runs & Reports, Methodology |

### Tests

```bash
make test-backend   # 27 tests: §9.1 accounting identities, Merton recovery, property tests, estimator recovery, API
make test-web       # tsc, eslint, vitest
cd web && npx playwright test   # e2e + visual snapshots of all screens (needs `make api`)
```

The R1 exit criterion (historical 60/40 cohorts against an independent spreadsheet-style loop, to 1e-8) is
`tests/test_accounting.py::test_historical_60_40_cohorts_match_independent_loop`.

### Reproducibility

Each run stores its canonical spec and hash, the catalog hash, the engine version (git SHA), the `uv.lock` hash, seeds and
timings. `make reproduce RUN=<id>` re-executes a run and asserts identical summary statistics. `make paper` builds the paper
figures from `research/experiments/run_ids.json` only.

---

## Layout

```text
backend/lifecycle/{data,engine,runs,api,workers,reports,research}   Python engine + FastAPI
backend/tests/                                                     pytest (synthetic fixtures only)
web/app, web/components/{ui,charts,experiment,pages,shell}         Next.js research terminal
research/experiments/*.json                                        versioned specs for every exhibit
paper/                                                             LaTeX draft + figure builder
data/                                                              gitignored: raw/, processed/, runs/
```

## Operations

- `REDIS_URL` set → jobs go to arq workers (`docker compose up` starts api, worker, redis, web); unset → in-process executor.
- `LIFECYCLE_WORKERS` (default 1): concurrent jobs in-process. The Numba kernel already uses every core.
- Credentials (`WRDS_USERNAME`, `WRDS_PASSWORD`, `.pgpass`, `FRED_API_KEY`) live in `.env` and are never committed.

Research output only, not investment advice. Results are model-dependent, and every exhibit cites its run ID and data vintage.
