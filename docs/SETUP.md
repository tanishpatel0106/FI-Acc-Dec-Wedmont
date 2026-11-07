# LIFECYCLE v2 — setup guide

This gets you from a clean clone to the full research terminal (13 pages, 137 visualizations) running on
public data, then optionally adds WRDS. Every step was run end to end on Linux (Python 3.12, Node 22).

## 0. Requirements

| Tool | Version | Notes |
|---|---|---|
| Python | 3.12 (exactly; `requires-python = ">=3.12,<3.13"`) | |
| [`uv`](https://docs.astral.sh/uv/) | any recent | creates `backend/.venv` |
| Node.js | 22 | `web/` is Next.js 16 / React 19 |
| make, git | | |
| Optional: Redis | 7+ | only for multi-process job workers (`REDIS_URL`) |
| Optional: `latexmk` | | only to compile the paper PDF |
| Optional: WRDS account | institutional | CRSP / Bond Returns / ETF data; Duo approval required |

Disk: ~1.5 GB for the two environments; data + runs are small (tens of MB).

## 1. Install

```bash
git clone https://github.com/tanishpatel0106/FI-Acc-Dec-Wedmont.git
cd FI-Acc-Dec-Wedmont
cp .env.example .env        # leave WRDS_* empty for public-only mode
make setup                  # backend/.venv (uv, locked deps incl. wrds + arq) and web/node_modules
```

## 2. Build the data panel (public, offline)

```bash
make data-offline           # installs the committed public snapshot (snapshots/public) and builds the panel
```

This needs no network. It prints the catalog hash (for the committed 2026-10-30 snapshot:
`f0ce88a6493ff732`). To download fresh public data instead (French, FRED, Fed GSW, NY Fed ACM, SSA):

```bash
make data
```

## 3. Run the research studies (F1–F6)

```bash
make seed-v2                # all nine v2 studies, ~70 s on 4 cores
```

Each study is a hashed, persisted run (`data/runs/<run_id>/results.json`); the IDs are written to
`research/results/v2_run_ids.json`. Without WRDS the Permanent Portfolio study on `pp_modern_etf` fails
honestly (no observed gold series) and the command automatically runs the gold-free variants on
`core_duration`. Options:

```bash
backend/.venv/bin/python -m lifecycle.cli seed-v2 --only frontier signed_flow
backend/.venv/bin/python -m lifecycle.cli seed-v2 --force                       # re-execute cached runs
backend/.venv/bin/python -m lifecycle.cli seed-v2 --only permanent --pp-universe core_duration
```

The legacy v1 exhibits (ΔCE heatmaps, DP, guardrails) are still available and take ~20 min:

```bash
make seed
```

Pages never start computation on their own: a study that has not been run shows
**"Results not computed"** with a *Run this study* button and the CLI command.

## 4. Start the app

```bash
make dev                    # API on :8000 and web on :3000 (Ctrl-C stops both)
```

or in two terminals:

```bash
make api
```

```bash
make web
```

Open <http://localhost:3000>. API docs (OpenAPI) are at <http://localhost:8000/docs>; health at
<http://localhost:8000/health>. If the web app runs on another host, set `NEXT_PUBLIC_API_BASE` for the web
build and `API_CORS_ORIGINS` for the API.

## 5. Tests

```bash
make test-backend           # 45 pytest tests on synthetic fixtures (accounting, ledger, look-ahead, studies, API)
backend/.venv/bin/python -m lifecycle.cli selftest   # same suite; records the result for the Overview timeline
make test-web               # tsc, eslint, vitest
cd web && npx playwright test --trace off            # e2e + screenshots of all 15 routes (needs the API up)
make reproduce RUN=<run_id> # re-execute any run and assert every derived block is identical
```

The e2e suite writes baseline screenshots the first time (`--update-snapshots`). If Playwright cannot find
its browser, install the version pinned in `web/package.json` (`npx playwright install chromium`).

## 6. Adding WRDS (authorised research host only)

```bash
# .env: WRDS_USERNAME=... WRDS_PASSWORD=...   (never committed)
backend/.venv/bin/python -m lifecycle.cli entitlements   # read-only scan; one Duo push
make ingest-wrds OFFLINE=1                               # CRSP index/Treasury, Bond Returns, ETFs (GLD/TLT/TIP/...)
backend/.venv/bin/python -m lifecycle.cli seed-v2 --force
```

The entitlement scan writes `data/catalog/entitlements.json` (server-local; no usernames, hosts or rows)
and its labels appear on the Runs and Market State pages. With GLD ingested, `pp_modern_etf` materialises
and the classic Permanent Portfolio (with gold) runs. WRDS series automatically outrank public ones; the
new catalog hash produces new run IDs, and old runs stay addressable. Raw WRDS rows never leave the
server — the API and all exports return derived statistics only.

## 7. Live public market data

```bash
backend/.venv/bin/python -m lifecycle.cli market-refresh   # US Treasury daily par nominal + real curves
```

or the **Update (backend job)** button on `/market-state`. This needs outbound access to
`home.treasury.gov`; failures are recorded in the Refresh audit panel (MS-12) and the page falls back to the
monthly GSW curves with a "not ingested" badge.

## 8. Docker / workers

```bash
make docker-up              # api + arq worker + redis + web
```

`REDIS_URL` set → jobs go to arq workers; unset → an in-process thread pool (`LIFECYCLE_WORKERS`, default 1).

## 9. Make targets (new in v2 marked ★)

| Target | What it does |
|---|---|
| `make setup` | install backend + web |
| `make data-offline` / `make data` | build the panel from the snapshot / live public sources |
| `make ingest-wrds` | WRDS + public ingestion |
| ★ `make seed-v2` | run the nine v2 studies |
| `make seed` / `make seed-full` | v1 exhibits |
| `make dev` / `make api` / `make web` | run the app |
| `make test` | backend + web tests |
| ★ `make selftest` | pytest with the result recorded for the Overview |
| ★ `make market-refresh` | Treasury daily curves |
| ★ `make entitlements` | WRDS entitlement scan |
| `make reproduce RUN=<id>` | deterministic re-execution check |
| `make openapi` | regenerate the typed web client |
| `make paper` | paper figures (+ PDF if `latexmk`) |

## 10. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Pages say "API unreachable" | start `make api`; check `NEXT_PUBLIC_API_BASE` and CORS origins |
| `panel not built` (503) | run `make data-offline` |
| Permanent Portfolio "IncompatibleUniverse … gold" | expected without WRDS; gold-free run is on `core_duration` |
| A study stays "queued" | another job is running (`LIFECYCLE_WORKERS=1`); see `/runs` → RN-03 |
| Numba compile pause on the first run | one-off; kernels are cached in `__pycache__` |
| Treasury refresh fails | the host has no access to home.treasury.gov; monthly GSW curves remain |
