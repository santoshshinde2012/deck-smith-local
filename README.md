# deck-smith-local

[![CI](https://github.com/santoshshinde2012/deck-smith-local/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/santoshshinde2012/deck-smith-local/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)

DeckSmith is an AI agent that builds PowerPoint decks from governed data. This repository runs it on a laptop, on a local stack that has the same shape as Databricks. The code uses ports and adapters (SOLID), so moving to Databricks changes configuration, not code. See [ARCHITECTURE.md](ARCHITECTURE.md).

> All data is synthetic: seed 42, about 8,000 subscriptions. No real customer data is used anywhere.

## Try it in 5 minutes

You need Python 3.11+, `make` and git. [uv](https://docs.astral.sh/uv/) is recommended, because `make install` then installs the exact locked versions; without it, pip is used. Docker is optional.

```bash
git clone https://github.com/santoshshinde2012/deck-smith-local && cd deck-smith-local
make quickstart        # install → seed → start API and UI → build decks; opens http://localhost:8501
make e2e-usecase       # asserts the whole use case below and prints a pass/fail table
make stop              # stop everything
```

`make quickstart` chooses the path for you; you can also pick one explicitly:

| Path | Command | What runs | Needs |
| --- | --- | --- | --- |
| **Offline** | `make quickstart-offline` | Fake LLM, DuckDB and in-memory state. The API and UI run natively | Python only; no Docker, keys or network after install |
| **Docker** | `make quickstart-docker` | Lean stack: Postgres checkpoints, MLflow traces (http://localhost:5001), the Portkey gateway, and the API and UI containers | Docker, about 4.5 GB of RAM |
| **Real LLM** (optional) | Export the three variables below, then run either command | The same flow, with a hosted model routed through the Portkey OSS gateway | Your own provider key |

```bash
export DECKSMITH_LLM=portkey DECKSMITH_PORTKEY_CONFIG_DIR=configs/portkey-openai
export DECKSMITH_LLM_API_KEY=sk-...   # yours; it stays in your environment and is never written to disk
# Docker path: the gateway is already running on :8787. Offline path: run `npx @portkey-ai/gateway` first.
```

The key travels only as the bearer token from the agent to your local gateway, and from there to the provider ([configs/portkey-openai](configs/portkey-openai/README.md)). Real models are not deterministic, so a run can fail QA and be retried. The fake LLM never fails.

### The use case, step by step

An analyst needs the quarterly churn review for the exec team, built from governed data and safe to present.

1. **Ask.** Acting as **bob** in the UI (http://localhost:8501), the analyst asks: *"Build the Q3 2026 customer retention review for the exec team."*
2. **Review the plan.** The agent proposes a five-slide outline: title, headline KPIs, monthly churn trend, churn by segment, and sources. The run pauses; no data has been touched yet. The analyst can **Edit** ("drop the segment slide"), **Reject** or **Approve**.
3. **Approve.** Only now does the agent run approved SQL templates as bob. The LLM writes no SQL and no numbers.
4. **Download.** The result is an editable `.pptx` with native charts. Every number on a slide is a *fact* with an ID (`f1`–`f5`). The renderer fills it in from the query result, and the **Sources** slide maps each fact ID to its query, tables and timestamp. The API returns the same facts, and the UI lists them under the download button.
5. **Same request, different user.** Three test users show how permissions change the outcome:

| User | Can see | Result |
| --- | --- | --- |
| **bob** | All regions | A full deck, with 6,172 active subscriptions |
| **alice** | EU-West only | A full deck with her own numbers (2,184 active subscriptions) |
| **carol** | Nothing | A clear refusal (`no_data`) and no deck |

Users can't see each other's runs (404), and anonymous calls are rejected (401).

`make e2e-usecase` checks each of these steps against the running API, with the same request and the same three users. It asserts that every number in the downloaded PPTX is a formatted fact, and writes `out/e2e-usecase.md`.

<details><summary>Example output (offline path)</summary>

```text
1. API is up                                  PASS    API up at http://localhost:8000
2. bob asks for a churn review deck           PASS    run 57e6c445: outline s01, s02, s03, s04, s05, paused for approval
3. bob edits the outline (human in the loop)  PASS    edit applied (s01, s02, s03, s05); still waiting for approval
4. bob approves; data is fetched as bob       PASS    status done: 5 slides, 5 facts
5. bob downloads an editable PPTX             PASS    out/usecase-bob.pptx (54,215 bytes, 5 slides, 2 native charts)
6. every number traces to a fact ID           PASS    4 numbers on slides, all from facts; sources slide cites 5 fact IDs
7. alice (EU-West only) gets her own deck     PASS    run 39a25608: status done: 5 slides, 5 facts
8. alice's deck is consistent too             PASS    4 numbers on slides, all from facts; sources slide cites 5 fact IDs
9. permissions change the numbers             PASS    active subscriptions: bob 6,172 (all regions) vs alice 2,184 (EU-West only)
10. carol (no access) is refused              PASS    no_data: None of the requested data is visible to you, so no deck was produced.
11. runs are private; auth is required        PASS    alice cannot see bob's run or file (404); anonymous request rejected (401)

11/11 steps passed
```
</details>

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

## Architecture

```mermaid
flowchart LR
  user([User / Streamlit UI]) -->|JWT| api[FastAPI interface]
  api --> svc[DeckService<br/>application]
  svc --> graph[LangGraph agent<br/>plan → approve ⏸ → fetch → write → QA → render]
  graph -->|ports only| ports{{8 Protocol ports}}
  ports --> idp[Identity]
  ports --> cat[Catalog]
  ports --> ds[DataSource<br/>DuckDB per-user views · Databricks SQL]
  ports --> llm[LLM<br/>Fake · Portkey → Ollama/remote]
  ports --> rend[Renderer<br/>python-pptx]
  ports --> st[StateStore<br/>memory · Postgres]
  ports --> tr[Tracer<br/>noop · MLflow 3]
  ports --> tpl[Templates<br/>approved SQL, sqlglot]
  boot[[bootstrap.py<br/>composition root]] -.wires adapters.-> ports
```

Only `bootstrap.py` imports adapters, and `tests/architecture` enforces this. Each port has a contract suite in `tests/contract`, which every adapter must pass.

## End-to-end walkthrough

What one request goes through. Run it yourself with `make up-instabox && make smoke-api`.

1. **Sign-in.** The UI or a client sends a bearer token. Locally these are fixed test tokens (`bob-token`); with `DECKSMITH_IDENTITY=jwt` they are signed JWTs. The identity port turns the token into a principal, such as `bob` (all regions). An anonymous call gets 401.
2. **Plan.** The LLM chooses from approved SQL templates and proposes an outline. It writes no SQL and no numbers.
3. **Approve.** The graph pauses on an interrupt. The checkpoint goes to Postgres, so a different process can resume it. `POST /v1/decks/{id}/decision` approves, edits or rejects the outline.
4. **Fetch as the user.** sqlglot compiles templates from Databricks SQL to DuckDB, and they run against the user's views. A user who sees no rows (carol) gets a `no_data` refusal (409), not an empty deck.
5. **Write and check.** Slides refer to numbers only as `{{fact:fN}}`. The guardrail rejects any bare digit (446). The QA loop retries invalid output up to three times.
6. **Render and download.** python-pptx renders native charts and tables. `GET /v1/decks/{id}/file` returns the PPTX, and only to the run's owner; anyone else gets 404.
7. **Observe.** Each step logs a JSON line carrying `run_id` and `duration_ms`. MLflow records a trace, and errors follow the taxonomy in [docs/errors.md](docs/errors.md).

## Engineering practices

| Area | What is in place |
| --- | --- |
| Tests | Unit, contract (per port), architecture, integration, e2e, and stack tests. CI fails below 90% branch coverage |
| Types and style | ruff (lint and format), strict mypy over `src` and `tests`, and type hints throughout |
| Config | pydantic-settings, with start-up validation of adapter combinations (D11) |
| Errors and logs | A stable error taxonomy (`code`, `category`, `retryable`) and JSON logs (D10) |
| Dependencies | `uv.lock`, installs with `--locked`, Dependabot, and pip-audit (D12) |
| Security | CodeQL, trivy, a CycloneDX SBOM, hadolint, non-root containers and `no-new-privileges` |
| Containers | Healthchecks, memory and CPU limits, and log rotation on every service |
| Releases | Conventional Commits, with release-please producing SemVer tags and a CHANGELOG (D13) |
| Dev environment | `make help`, pre-commit, and a devcontainer (`.devcontainer/`) |
| Cloud e2e | A lean profile for 8 GB InstaBox VMs, plus a manual workflow (D14, [docs/instabox.md](docs/instabox.md)) |

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
| [docker-compose.yml](docker-compose.yml) | `core`, `app` and `instabox` profiles |
| [docs/errors.md](docs/errors.md) | Error codes, HTTP statuses and retryability |
| [docs/instabox.md](docs/instabox.md) | End-to-end runs on an 8 GB InstaBox VM |
| [configs/portkey/](configs/portkey) | Example gateway configs for each tier |
| [src/decksmith/sql/templates/](src/decksmith/sql/templates) | The approved SQL templates |
| [evals/golden/golden.jsonl](evals/golden/golden.jsonl) | Ten golden prompts with expectations |

## Step by step (manual)

The same as `make quickstart`, one target at a time:

```bash
make install       # locked install with uv (pip fallback)
make seed          # data/lakehouse.duckdb, with per-user views for alice, bob and carol
make test          # unit, contract, architecture, integration and e2e tests (fake LLM)
make demo          # one deck each for bob (all regions), alice (EU-West) and carol (no access)
make api           # http://localhost:8000/docs
make ui            # http://localhost:8501 (in a second terminal)
```

`make demo` works with or without Docker. By default it uses the fake LLM, DuckDB and in-memory state. See [Local stack](#local-stack-apple-silicon-16-gb-or-more) to switch to the services.

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
| Postgres 18 | 5433 | Lakebase (LangGraph checkpoints) and the MLflow store |
| MLflow 3 | 5001 | Managed MLflow (tracing, `genai.evaluate`) |
| Unity Catalog OSS | 8081 | Unity Catalog names and registration (no row filters) |
| Portkey OSS gateway | 8787 | Portkey Enterprise hybrid (inline configs) |
| RustFS | 9000 / 9001 | S3 and UC volumes; replaces MinIO, whose images are no longer on Docker Hub |
| Agent API | 8000 | Databricks App backend |
| Streamlit UI | 8501 | Databricks App front end |
| Ollama (native) | 11434 | Bedrock models, offline |

## Lean stack and InstaBox (8 GB)

```bash
cp .env.instabox .env && make up-instabox   # Postgres, MLflow, Portkey, agent API and UI (~4.5 GB limits)
make e2e-stack && make smoke-api            # E1–E8 on real Postgres, then curl drives the API
```

On a fresh [InstaBox](https://instabox.sh) VM, a single command runs everything headlessly and writes `out/instabox-summary.md`. See [docs/instabox.md](docs/instabox.md):

```bash
curl -fsSL https://raw.githubusercontent.com/santoshshinde2012/deck-smith-local/main/scripts/instabox/bootstrap.sh | bash
```

![bootstrap.sh on a fresh InstaBox VM](docs/evidence/instabox-bootstrap.gif)

[docs/instabox.md](docs/instabox.md#evidence-from-a-real-run) has screenshots from that run: the UI, MLflow traces, the API docs and the rendered deck.

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
tests/           unit, contract, architecture, integration, e2e
```

## Status and next steps

This repo implements phases LD0–LD1 of the local plan. Next:

- LD2: run the online profile against Bedrock EU with synthetic data, and add LLM-judge scorers.
- `spark` and `airflow` compose profiles for SQL parity on Delta.
- LD3: hybrid runs against a Databricks workspace (E9–E10).

The model IDs in `configs/portkey` are **examples only**. Replace them with the models you have access to.
