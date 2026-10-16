# deck-smith-local

DeckSmith is the PowerPoint agent designed in [pptx-agent-databricks-research](https://github.com/santoshshinde2012/pptx-agent-databricks-research). This repository runs it on a laptop, using a stack shaped like Databricks.

You can work in two modes:

- **Offline.** The whole agent runs with a fake LLM and needs no keys and no Docker. CI uses this mode.
- **Local stack.** Docker Compose runs Unity Catalog OSS, MLflow 3, Postgres, the Portkey OSS gateway and an S3-compatible store. Ollama runs natively on Apple Silicon.

The code follows ports and adapters (SOLID). Moving to Databricks means changing configuration, not code. See [ARCHITECTURE.md](ARCHITECTURE.md).

> All data is synthetic: seed 42, about 8,000 subscriptions, modelled on retention-radar. No real customer data is used anywhere.

## Index

| Document | What it covers |
| --- | --- |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Layers, ports and adapters, the graph, SOLID principle by principle, fidelity of the local emulation |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Setup, workflow, quality gates, the dependency rule |
| [CHANGELOG.md](CHANGELOG.md) | Releases |
| [.env.example](.env.example) | Every setting; adapter selection |
| [docker-compose.yml](docker-compose.yml) | `core` and `app` profiles |
| [configs/portkey/](configs/portkey) | Gateway configs for each tier (Ollama first, then Bedrock EU) |
| [src/decksmith/sql/templates/](src/decksmith/sql/templates) | The approved SQL templates (Databricks SQL) |
| [evals/golden/golden.jsonl](evals/golden/golden.jsonl) | Ten golden prompts with expectations |
| [Local development environment](https://github.com/santoshshinde2012/pptx-agent-databricks-research/blob/main/docs/08-delivery-roadmap/06-local-development-environment.md) | The design this repo implements (tiers L0–L4, scenarios E1–E11, phases LD0–LD4) |

## Quick start (offline, about two minutes)

```bash
python3 -m venv .venv && make install
make seed          # data/lakehouse.duckdb, with per-user views for alice, bob and carol
make test          # unit, architecture, integration and e2e tests (fake LLM)
make demo          # one deck each for bob (all regions), alice (EU-West) and carol (no access)
make api           # http://localhost:8000/docs
make ui            # http://localhost:8501 (in a second terminal)
```

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

Items marked [unv] need checking by the named owner. The Bedrock model IDs in `configs/portkey` are placeholders [unv: owner platform team].
