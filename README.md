# deck-smith-local

[![CI](https://github.com/santoshshinde2012/deck-smith-local/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/santoshshinde2012/deck-smith-local/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)

DeckSmith is an AI agent that builds PowerPoint decks from governed data. This repository runs it on a laptop, on a local stack that has the same shape as Databricks. The code uses ports and adapters (SOLID), so moving to Databricks changes configuration, not code. See [ARCHITECTURE.md](ARCHITECTURE.md).

> All data is synthetic: seed 42, about 8,000 subscriptions. No real customer data is used anywhere.

## What this is, and what it is not

| This is | This is not |
| --- | --- |
| A runnable reference: a LangGraph agent that plans a deck, waits for human approval, pulls numbers only through approved SQL, and renders a native `.pptx` | A hosted product or a managed service |
| An offline loop: the fake LLM means every test runs in CI with no keys and no network | A benchmark of model quality (the fake LLM is deterministic by design) |
| A local stand-in for Databricks pieces (Unity Catalog OSS, MLflow 3, Postgres in place of Lakebase, the Portkey gateway) | A security boundary: per-user views only emulate row filters |
| Clean seams for Databricks adapters (SQL Statement API, Unity Catalog, Apps on-behalf-of login) | Verified against a live Databricks workspace; that is a later phase |

## The design in brief

- **The LLM never writes SQL.** The planner picks from approved, parameterised SQL templates, which are written in Databricks SQL. Locally, sqlglot transpiles them for DuckDB.
- **The LLM never writes numbers.** Query results become *facts* with provenance. Slides refer to them as `{{fact:fN}}`, and the renderer formats them. A guardrail and a deterministic check reject any bare digit.
- **A human approves the outline** before any data is fetched. The run pauses and resumes from a checkpoint.
- **Data is fetched as the user.** A user who can see no data gets a clear refusal, not an empty deck.
- **Every step is traced**, and a golden set of prompts is scored on each change.

The design is documented in this repo: [ARCHITECTURE.md](ARCHITECTURE.md), the [decision records](docs/decisions.md) and the [test plan](docs/test-plan.md).

## Index

| Document | What it covers |
| --- | --- |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Layers, ports and adapters, the graph, SOLID principle by principle, fidelity of the local emulation |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Setup, workflow, quality gates, the dependency rule |
| [SECURITY.md](SECURITY.md) | How to report a vulnerability |
| [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) | Community standards |
| [docs/decisions.md](docs/decisions.md) | Architecture decision records |
| [docs/test-plan.md](docs/test-plan.md) | Fidelity tiers L0–L4, scenarios E1–E11, phases LD0–LD4 |
| [CHANGELOG.md](CHANGELOG.md) | Releases |
| [.env.example](.env.example) | Every setting, including adapter selection |
| [docker-compose.yml](docker-compose.yml) | `core` and `app` profiles |
| [configs/portkey/](configs/portkey) | Example gateway configs for each tier |
| [src/decksmith/sql/templates/](src/decksmith/sql/templates) | The approved SQL templates |
| [evals/golden/golden.jsonl](evals/golden/golden.jsonl) | Ten golden prompts with expectations |

## Quick start

Prerequisites: Python 3.11 or later, `make`, and git. Docker is needed only for `make up`.

```bash
git clone https://github.com/santoshshinde2012/deck-smith-local && cd deck-smith-local
git switch feat/core-local-stack   # until pull request #1 is merged into main
python3 -m venv .venv && make install
make up            # optional: Postgres, MLflow, UC OSS, Portkey, RustFS (needs about 3 GB free Docker disk)
make seed          # data/lakehouse.duckdb, with per-user views for alice, bob and carol
make test          # unit, architecture, integration and e2e tests (fake LLM)
make demo          # one deck each for bob (all regions), alice (EU-West) and carol (no access)
make api           # http://localhost:8000/docs
make ui            # http://localhost:8501 (in a second terminal)
```

`make demo` works with or without `make up`. By default it uses the fake LLM, DuckDB and in-memory state. See [Local stack](#local-stack-apple-silicon-16-gb-or-more) to switch to the services.

### Sample output

This is the deck `make demo` produces for bob ([download the .pptx](docs/examples/sample-deck.pptx)). The charts and text are native and editable, and the sources slide lists the query behind every number.

![Sample five-slide deck: title, KPIs, monthly churn trend, churn by segment, sources](docs/examples/sample-deck.png)

The test users have fixed tokens: `alice-token`, `bob-token` and `carol-token`. You can also drive the API directly:

```bash
curl -s -X POST localhost:8000/v1/decks -H 'Authorization: Bearer bob-token' \
  -H 'Content-Type: application/json' -d '{"request":"Build the Q3 2026 customer retention review for the exec team"}'
curl -s -X POST localhost:8000/v1/decks/<run_id>/decision -H 'Authorization: Bearer bob-token' \
  -H 'Content-Type: application/json' -d '{"action":"approve"}'
curl -s -o deck.pptx localhost:8000/v1/decks/<run_id>/file -H 'Authorization: Bearer bob-token'
```

## Local stack (Apple Silicon, 16 GB or more)

```bash
cp .env.example .env
make up            # Postgres :5433, MLflow :5001, UC OSS :8081, Portkey :8787, RustFS :9000/:9001
make publish       # Parquet to RustFS, plus tables registered in UC OSS as main.cs.*
ollama serve & ollama pull llama3.1:8b && ollama pull qwen2.5:14b   # optional, native
```

Next, edit `.env`: set `DECKSMITH_STATE_STORE=postgres`, `DECKSMITH_TRACER=mlflow` and `DECKSMITH_CATALOG=uc_oss`. Set `DECKSMITH_LLM=portkey` too if Ollama is running. Then run:

```bash
make api           # and `make ui` in a second terminal, or: make up-app
make stack-test    # E3 resume from Postgres, E6 gateway reachable
```

| Service | Port | Stands in for |
| --- | --- | --- |
| Postgres 16 | 5433 | Lakebase (LangGraph checkpoints) and the MLflow store |
| MLflow 3 | 5001 | Managed MLflow (tracing, `genai.evaluate`) |
| Unity Catalog OSS | 8081 | Unity Catalog names and registration (no row filters) |
| Portkey OSS gateway | 8787 | Portkey Enterprise hybrid (inline configs) |
| RustFS | 9000 / 9001 | S3 and UC volumes; replaces MinIO, whose images are no longer on Docker Hub |
| Agent API | 8000 | Databricks App backend |
| Streamlit UI | 8501 | Databricks App front end |
| Ollama (native) | 11434 | Bedrock models, offline |

## What is tested where

| Scenario | Here | How |
| --- | --- | --- |
| E1 renderer golden | Yes | Slide XML content hash is stable across runs; overflow is flagged |
| E2 numeric integrity | Yes | Every number on the produced deck resolves to a fact; charts plot series facts |
| E3 interrupt and resume | Yes / stack | Resume in a fresh container from a shared checkpointer (offline), or from Postgres (`make stack-test`) |
| E4 request to PPTX | Yes | Full graph; QA loop recovers from invalid JSON and unknown facts, and gives up after three writes |
| E5 permissions | Yes | alice sees EU-West only; carol gets a clean `no_data` refusal |
| E6 gateway | Partly | The 446 bare-number guardrail and the rewrite are offline. Retry and fallback need Portkey (`stack`) |
| E7 golden set | Yes | Ten prompts, deterministic scorers at 100%; also runs through `mlflow.genai.evaluate` |
| E8 cost and latency | Partly | Tokens recorded per node. Latency is meaningful only with real models |
| E9–E11 | No | Need a Databricks workspace or staging; skipped with reasons |

## Layout

```text
src/decksmith/
  domain/        DeckSpec, Fact, Outline, integrity rules, errors (pure)
  ports/         the eight Protocols
  application/   graph, nodes, SQL compiler, fact fetcher, guardrail, service
  adapters/      local/ and databricks/ implementations
  interfaces/    FastAPI, ResponsesAgent, Streamlit
  evaluation/    scorers and the golden-set harness
  seed/          synthetic data generator and UC OSS publisher
  sql/templates/ approved SQL in Databricks dialect
  bootstrap.py   composition root
tests/           unit, architecture, integration, e2e
```

## Status and next steps

This repo implements phases LD0–LD1 of the local plan. Next:

- LD2: run the online profile against Bedrock EU with synthetic data, and add LLM-judge scorers.
- `spark` and `airflow` compose profiles for SQL parity on Delta.
- LD3: hybrid runs against a Databricks workspace (E9–E10).

The model IDs in `configs/portkey` are **examples only**. Replace them with the models you have access to.
