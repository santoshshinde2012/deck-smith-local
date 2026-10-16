# DeckSmith local. `make help` lists targets.
PY ?= .venv/bin/python
COMPOSE ?= docker compose

.DEFAULT_GOAL := help
.PHONY: help venv install up up-app down logs ps seed publish test unit e2e eval lint type check api ui demo stack-test clean

help: ## Show targets
	@grep -E '^[a-z-]+:.*?## ' $(MAKEFILE_LIST) | awk -F':.*?## ' '{printf "  %-12s %s\n", $$1, $$2}'

venv: ## Create .venv
	python3 -m venv .venv

install: ## Install the package with dev and ui extras
	$(PY) -m pip install -U pip && $(PY) -m pip install -e ".[dev,ui,publish]"

up: ## Start the core profile (Postgres, MLflow, UC OSS, Portkey, RustFS)
	$(COMPOSE) --profile core up -d --build

up-app: ## Also run the agent API and UI in containers
	$(COMPOSE) --profile core --profile app up -d --build

down: ## Stop everything
	$(COMPOSE) --profile core --profile app down

ps: ## Service status
	$(COMPOSE) --profile core --profile app ps

logs: ## Follow logs
	$(COMPOSE) --profile core --profile app logs -f --tail=100

seed: ## Build data/lakehouse.duckdb (synthetic, seed 42) with per-user views
	$(PY) -m decksmith.seed.generate

publish: seed ## Export Parquet to RustFS and register tables in UC OSS (needs `make up`)
	$(PY) -m decksmith.seed.publish

lint: ## Ruff lint and format check
	$(PY) -m ruff check src tests scripts && $(PY) -m ruff format --check src tests scripts

type: ## Mypy (strict)
	$(PY) -m mypy

unit: ## Unit and architecture tests
	$(PY) -m pytest tests/unit tests/architecture

test: ## All offline tests (unit, architecture, integration, e2e with the fake LLM)
	$(PY) -m pytest

e2e: ## E1-E8 scenarios offline (E9-E11 skip with reasons)
	$(PY) -m pytest -m e2e -rs

stack-test: ## Tests that need `make up` (Postgres resume, Portkey)
	DECKSMITH_STATE_STORE=postgres $(PY) -m pytest -m stack -rs

eval: ## Golden set; add ARGS=--mlflow to log to MLflow
	$(PY) -m decksmith.evaluation.harness $(ARGS)

check: lint type test ## Everything CI runs

api: ## Run the API natively on :8000
	$(PY) -m uvicorn --factory decksmith.interfaces.api:app --port 8000 --reload

ui: ## Run the Streamlit UI natively on :8501
	$(PY) -m streamlit run src/decksmith/interfaces/ui.py --server.port 8501

demo: seed ## Produce a deck end to end from the command line (fake LLM unless .env says otherwise)
	$(PY) scripts/demo.py

clean: ## Remove generated data and caches
	rm -rf data out mlruns .pytest_cache .mypy_cache .ruff_cache
