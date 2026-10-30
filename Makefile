# LIFECYCLE — common tasks. Run `make help`.
SHELL := /bin/bash
PY := backend/.venv/bin/python
UV ?= uv

.PHONY: help setup setup-backend setup-web data data-offline snapshot ingest-wrds build-panel seed seed-full api web dev test test-backend test-web lint typecheck openapi reproduce paper docker-up clean-runs

help:
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

setup: setup-backend setup-web ## Install backend (uv) and web (npm) dependencies

setup-backend: ## Create backend/.venv with locked deps (incl. WRDS client and arq)
	cd backend && $(UV) venv --python 3.12 .venv && $(UV) pip install -e ".[dev,wrds,workers]"

setup-web: ## npm install for the Next.js app
	cd web && npm install

data: ## Ingest public sources (French, FRED, Fed GSW, NY Fed ACM, SSA) and build the panel
	$(PY) -m lifecycle.cli ingest

data-offline: ## Build the panel from the committed public snapshot (snapshots/public) - no network
	$(PY) -m lifecycle.cli ingest --offline

snapshot: ## Refresh snapshots/public from the live public sources
	$(PY) -m lifecycle.cli snapshot

ingest-wrds: ## Ingest WRDS + public (WRDS_USERNAME / WRDS_PASSWORD from .env; approve the Duo push). OFFLINE=1 uses the snapshot for public data
	$(PY) -m lifecycle.cli ingest --wrds $(if $(OFFLINE),--offline,)

build-panel: ## Rebuild the canonical panel + catalog from the raw vintages on disk
	$(PY) -m lifecycle.cli build-panel

seed: ## Run the core exhibit specs in research/experiments (headline heatmaps, baselines, DP)
	$(PY) -m lifecycle.cli seed

seed-full: ## Run every exhibit spec, plus attribution and the H1-H4 tests
	$(PY) -m lifecycle.cli seed --full

api: ## FastAPI on :8000
	cd backend && .venv/bin/uvicorn lifecycle.api.main:app --host 0.0.0.0 --port 8000 --reload

web: ## Next.js dev server on :3000
	cd web && npm run dev

dev: ## API + web together (Ctrl-C stops both)
	@trap 'kill 0' INT TERM; $(MAKE) api & $(MAKE) web & wait

test: test-backend test-web ## All tests

test-backend: ## pytest (accounting, property, estimator recovery, API) on synthetic fixtures
	cd backend && .venv/bin/python -m pytest -q

test-web: ## Type-check, lint and vitest
	cd web && npx tsc --noEmit && npx eslint . && npx vitest run

lint: ## ruff + eslint
	cd backend && .venv/bin/ruff check lifecycle tests
	cd web && npx eslint .

typecheck: ## mypy on the engine
	cd backend && .venv/bin/mypy lifecycle/engine

openapi: ## Export the OpenAPI schema and regenerate the typed web client
	$(PY) -m lifecycle.cli openapi web/lib/api/openapi.json
	cd web && npx openapi-typescript lib/api/openapi.json -o lib/api/schema.d.ts

reproduce: ## Re-execute a run and assert identical summary statistics: make reproduce RUN=<id>
	@test -n "$(RUN)" || (echo "usage: make reproduce RUN=<run_id>"; exit 2)
	$(PY) -m lifecycle.cli reproduce $(RUN)

paper: ## Build paper figures from the stored run IDs (research/experiments/run_ids.json), then LaTeX if available
	$(PY) paper/build_figures.py
	@if command -v latexmk >/dev/null; then cd paper && latexmk -pdf -outdir=build main.tex; else echo "latexmk not found: figures written to paper/figures"; fi

docker-up: ## api + worker + redis + web via docker compose
	docker compose up --build

clean-runs: ## Delete the run registry and cached results (data/runs)
	rm -rf data/runs
