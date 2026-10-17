# DeckSmith local. `make help` lists targets.
PY ?= .venv/bin/python
COMPOSE ?= docker compose

.DEFAULT_GOAL := help
.PHONY: help quickstart quickstart-docker quickstart-offline e2e-usecase stop stop-native venv install lock up up-app up-instabox down logs ps seed publish test unit contract e2e e2e-stack eval lint type audit check api ui demo stack-test smoke-api docker-lint sbom diagrams clean

help: ## Show targets
	@grep -E '^[a-z0-9-]+:.*?## ' $(MAKEFILE_LIST) | awk -F':.*?## ' '{printf "  %-12s %s\n", $$1, $$2}'

quickstart: ## Try it: install, seed, start API + UI, build decks (Docker if available, else offline)
	scripts/quickstart.sh auto

quickstart-docker: ## Quickstart on the lean Docker stack (Postgres, MLflow, Portkey, API and UI containers)
	scripts/quickstart.sh docker

quickstart-offline: ## Quickstart with no Docker: fake LLM, DuckDB, in-memory state; API and UI run natively
	scripts/quickstart.sh offline

e2e-usecase: ## Assert the whole use case against the running API and print a pass/fail table
	$(PY) scripts/e2e_usecase.py --api $(or $(API),http://localhost:8000)

stop: stop-native ## Stop the quickstart (native processes and containers)
	@if docker info >/dev/null 2>&1; then $(COMPOSE) --profile core --profile app --profile instabox down; fi

stop-native:
	@if [ -f out/.quickstart.pids ]; then kill $$(cat out/.quickstart.pids) 2>/dev/null || true; rm -f out/.quickstart.pids; fi

venv: ## Create .venv
	python3 -m venv .venv

install: ## Install the package (locked versions when uv is available) with dev, ui and publish extras
	@if command -v uv >/dev/null 2>&1; then \
	  UV_PROJECT_ENVIRONMENT=.venv uv sync --locked --all-extras; \
	else \
	  $(PY) -m pip install -U pip && $(PY) -m pip install -e ".[dev,ui,publish]"; \
	fi

lock: ## Refresh uv.lock after changing dependencies
	uv lock

up: ## Start the core profile (Postgres, MLflow, UC OSS, Portkey, RustFS)
	$(COMPOSE) --profile core up -d --build

up-app: ## Also run the agent API and UI in containers
	$(COMPOSE) --profile core --profile app up -d --build

up-instabox: ## Lean profile for a 4 vCPU / 8 GB VM (Postgres, MLflow, Portkey, agent)
	$(COMPOSE) --profile instabox up -d --build --wait

down: ## Stop everything
	$(COMPOSE) --profile core --profile app --profile instabox down

ps: ## Service status
	$(COMPOSE) --profile core --profile app --profile instabox ps

logs: ## Follow logs
	$(COMPOSE) --profile core --profile app --profile instabox logs -f --tail=100

seed: ## Build data/lakehouse.duckdb (synthetic, seed 42) with per-user views
	$(PY) -m decksmith.seed.generate

publish: seed ## Export Parquet to RustFS and register tables in UC OSS (needs `make up`)
	$(PY) -m decksmith.seed.publish

lint: ## Ruff lint and format check
	$(PY) -m ruff check src tests scripts && $(PY) -m ruff format --check src tests scripts

type: ## Mypy (strict)
	$(PY) -m mypy

unit: ## Unit and architecture tests
	$(PY) -m pytest tests/unit tests/architecture --no-cov

contract: ## Contract tests: every adapter of a port behaves the same
	$(PY) -m pytest tests/contract --no-cov

test: ## All offline tests (unit, architecture, integration, e2e with the fake LLM)
	$(PY) -m pytest

e2e: ## E1-E8 scenarios offline (E9-E11 skip with reasons)
	$(PY) -m pytest -m e2e -rs --no-cov

e2e-stack: ## E1-E8 plus the live-service tests, against a running stack (Postgres checkpoints, MLflow)
	DECKSMITH_STATE_STORE=postgres $(PY) -m pytest -m "e2e or stack" -rs --no-cov --junitxml=out/e2e-junit.xml

stack-test: ## Tests that need `make up` (Postgres resume, Portkey)
	DECKSMITH_STATE_STORE=postgres $(PY) -m pytest -m stack -rs --no-cov

smoke-api: ## Drive the containerised API end to end with curl (needs up-instabox or up-app)
	scripts/smoke_api.sh

audit: ## Known-vulnerability audit of the locked dependencies
	mkdir -p out && uv export --frozen --all-extras --no-emit-project --no-hashes -q -o out/requirements.lock.txt
	$(PY) -m pip_audit --strict --progress-spinner off --disable-pip --no-deps -r out/requirements.lock.txt

docker-lint: ## Hadolint the Dockerfiles
	docker run --rm -i hadolint/hadolint < docker/agent/Dockerfile && docker run --rm -i hadolint/hadolint < docker/mlflow/Dockerfile

sbom: ## CycloneDX SBOM of the Python environment into out/sbom.json
	mkdir -p out && uvx --from cyclonedx-bom cyclonedx-py environment $(PY) -o out/sbom.json

diagrams: ## Check the Mermaid palette and render every diagram in light and dark themes (needs mmdc or npx)
	MMDC="$${MMDC:-$$(command -v mmdc || echo npx -y @mermaid-js/mermaid-cli@11)}" python3 scripts/diagrams.py

eval: seed ## Golden set; add ARGS=--mlflow to log to MLflow
	$(PY) -m decksmith.evaluation.harness $(ARGS)

check: lint type test ## Everything CI runs (lint, types, all offline tests with the coverage gate)

api: ## Run the API natively on :8000
	$(PY) -m uvicorn --factory decksmith.interfaces.api:app --port 8000 --reload

ui: ## Run the Streamlit UI natively on :8501
	$(PY) -m streamlit run src/decksmith/interfaces/ui.py --server.port 8501

demo: seed ## Produce a deck end to end from the command line (fake LLM unless .env says otherwise)
	$(PY) scripts/demo.py

clean: ## Remove generated data and caches
	rm -rf data out mlruns .pytest_cache .mypy_cache .ruff_cache
