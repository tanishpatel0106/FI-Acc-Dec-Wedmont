# Governance, data rights and model-risk controls

Applies to LIFECYCLE v2 (engine semantic version 2.0). Research output only — not personalised advice.

## 1. Data boundaries and licensing

| Source class | Examples | Allowed in browser / exports | Control |
|---|---|---|---|
| `public_open` | Fed GSW curves, NY Fed ACM, US Treasury, SSA | derived statistics; public snapshot committed | `snapshots/public` with SHA-256 manifest |
| `public_with_terms` | FRED, Ken French library | derived statistics with attribution | ICE BofA OAS excluded (3-year public retention) |
| `wrds_restricted` | CRSP, WRDS Bond Returns, CRSP ETFs | **never raw rows**; aggregates only | server-side ingestion; `data/` gitignored; no inverse API (studies return quantiles/means only); `/v1/data/vintages` withholds restricted releases |
| `model_generated` | par bonds repriced from CMT yields | labelled everywhere | `provenance=model_generated`, UI tag "Model-generated" |
| test fixtures | `LIFECYCLE_SYNTHETIC=1` | never research output | every payload warns "SYNTHETIC DATA"; evidence grade `invalid` |

No commercial market-data APIs are used (none in `pyproject.toml` or `package.json`). Gold enters only as
an observed fund total return (WRDS CRSP GLD); historical LBMA prices are not ingested pending rights
review. The source-rights registry is in `backend/lifecycle/data/entitlements.py` and is served at
`/v1/data/entitlements`.

## 2. Credentials

WRDS credentials live in the repository `.env` (gitignored) or `~/.pgpass`. They are never logged, never
returned by the API, and never stored in `data/catalog/entitlements.json`, run specs or the audit trail.
WRDS refreshes cannot be triggered from the API (`POST /v1/data/refresh?group=wrds` → 403).

## 3. Reproducible change control

- Run ID = SHA-256(kind + canonical spec + data catalog hash). Runs are immutable; a data or spec change
  creates a new ID. Each run stores engine git SHA, `uv.lock` hash, seeds, warnings and timings.
- `make reproduce RUN=<id>` re-executes and asserts identical derived blocks.
- Semantic changes bump `ENGINE_SEMANTIC_VERSION` (`backend/lifecycle/__init__.py`).
- Append-only audit trail of submits, cache hits, cancels, completions, failures, traces, exports and
  refreshes: `audit` table in the run registry, `/v1/audit`, page L (RN-10).

## 4. Pre-registration and inference

Confirmatory family H1–H12 registered in `research/preregistration/hypotheses_v2.json` before the v2
studies ran. Holm and Benjamini-Hochberg adjustments; negative and not-computed results are reported
with the same prominence. Evidence grades: `not_computed`, `diagnostic`, `conditional`, `robust`,
`contradicted`, `invalid` (brief §13.2). A completed HTTP request is never treated as validation.

## 5. Model-risk controls (automated)

| Control | Where |
|---|---|
| No look-ahead: future-return mutation leaves earlier decisions unchanged | `tests/test_v2_engine.py`, RS-09 |
| Decision regime is the filtered/lagged signal; oracle only as a labelled bound | `pit_signals.py`, OP-06, RS-09 |
| Holdings ledger equals an independent spreadsheet loop (1e-10) | `test_ledger_matches_independent_loop` |
| Funded + unmet = desired; wealth never negative; no phantom consumption | `test_no_phantom_consumption_and_no_negative_wealth` |
| Browne rule trades only at the annual review; boundary equality does not trigger | `test_browne_*` |
| b_min handles monotone, non-monotone, disconnected and infeasible sets | `test_bmin_solver_cases` |
| Trade-ledger reconciliation (sources & uses residual) | RB-04 |
| Key-rate durations sum to effective duration | `test_v2_read_routes`, FI-04 |
| Universes never back-fill before inception; incompatible universes fail loudly | `panel.universe_data`, `IncompatibleUniverse` |
| Publication lags on every macro row; as-of replay respects them | `available_from`, `/v1/market-state/{as_of}` |

## 6. Access roles and deployment

- **Public demo:** committed public snapshot only; any visitor can run public studies.
- **Research host:** WRDS-entitled server; WRDS ingestion and entitlement scans via the CLI only.
- Put the API behind authentication and rate limiting before any public deployment; CORS is not an access
  control.

## 7. Sign-off checklist for a presentation

1. Every cited number has a run ID, data catalog hash and evidence grade.
2. Benchmarks share the tensor, spending rule, costs and horizon (or the comparison is labelled joint).
3. No macro predictor is used before its publication date; no oracle result is presented as tradable.
4. Model-generated returns, missing gold and other data limits are stated next to the result.
5. CIs and model disagreement are shown; non-significance is not presented as equivalence.
6. Negative findings (e.g. H1, H2, H6 on public data) are reported.
7. No raw WRDS observations in slides, exports or the repository.

## 8. Incident response

Stale or failed sources appear in MS-01/MS-12 and RN-08; failed runs keep their error and never render
figures. A data incident is handled by fixing the source, rebuilding the panel (new catalog hash) and
re-running the affected studies; old runs remain addressable for audit.
