<!-- markdownlint-disable-next-line MD041 -->
<div align="center">

# deck-smith-local

**An AI agent that turns a plain-English request into an editable PowerPoint deck, built only from governed data, with numeric metrics traceable to reviewed SQL.**

[![CI](https://github.com/santoshshinde2012/deck-smith-local/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/santoshshinde2012/deck-smith-local/actions/workflows/ci.yml)
[![CodeQL](https://github.com/santoshshinde2012/deck-smith-local/actions/workflows/codeql.yml/badge.svg?branch=main)](https://github.com/santoshshinde2012/deck-smith-local/actions/workflows/codeql.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](pyproject.toml)
[![Version](https://img.shields.io/badge/dynamic/toml?url=https%3A%2F%2Fraw.githubusercontent.com%2Fsantoshshinde2012%2Fdeck-smith-local%2Fmain%2Fpyproject.toml&query=%24.project.version&label=version&color=orange)](CHANGELOG.md)

<img src="docs/examples/sample-deck.png" alt="The five-slide deck DeckSmith builds: title, headline KPIs, monthly churn trend, monthly churn by segment, and a sources slide" width="820">

<sub>A preview reconstructed from the PPTX text, geometry and chart data; fonts and axes may differ in PowerPoint. The deck <code>make demo</code> builds contains native, editable charts and text. <a href="docs/examples/sample-deck.pptx">Download the .pptx</a>.</sub>

</div>

DeckSmith plans the deck, waits for a person to approve the outline, fetches numbers through approved SQL as the signed-in user, and renders a native `.pptx`. This repository runs it entirely on your machine, on a local stack shaped like Databricks. Ports keep the graph independent of infrastructure. Databricks adapters and forwarded-header authentication are implemented and tested offline; workspace resources, networking, managed services and deployment remain unverified.

> [!NOTE]
> All data is synthetic (seed 42, about 8,000 subscriptions). No real customer data is used anywhere.

## Contents

- [Why](#why)
- [Try it in 5 minutes](#try-it-in-5-minutes)
- [Architecture](#architecture)
  - [System overview](#system-overview)
  - [Ports and adapters](#ports-and-adapters)
  - [From request to deck](#from-request-to-deck)
- [The use case, step by step](#the-use-case-step-by-step)
- [Features](#features)
- [Project layout](#project-layout)
- [Configuration](#configuration)
- [Testing](#testing)
- [Running on InstaBox](#running-on-instabox)
- [Security](#security)
- [Documentation and contributing](#documentation-and-contributing)
- [Roadmap](#roadmap)
- [License](#license)

## Why

Executive decks are full of numbers, and an LLM that writes those numbers itself will sooner or later make one up. Letting it write SQL against governed data raises a second problem: whose permissions does that query run with? DeckSmith answers both by design:

- **The LLM never writes SQL.** It picks from approved, parameterised templates.
- **Numeric metrics reference typed facts.** The renderer fills scalar placeholders and native chart series from query results. Checks reject bare digits in writer text, incorrect fact types and incompatible chart categories. These rules do not assess the truth of prose or spelled-out quantities.
- **A person approves the plan** before any data is touched.
- **Data is fetched as the user**, so two people asking the same question get decks with their own numbers, and someone with no access gets a clear refusal instead of an empty deck.

This repository is a runnable reference for that design. It is not a hosted product, a benchmark of model quality, or a security boundary: the local per-user views only emulate Unity Catalog row filters.

## Try it in 5 minutes

You need Python 3.11+, `make` and git. [uv](https://docs.astral.sh/uv/) is recommended, because `make install` then installs the exact locked versions; without it, pip is used. Docker is optional.

```bash
git clone https://github.com/santoshshinde2012/deck-smith-local.git && cd deck-smith-local
make quickstart        # install → seed → start API and UI → build decks; opens http://localhost:8501
make e2e-usecase       # asserts the whole use case below and prints a pass/fail table
make stop              # stop everything
```

`make quickstart` uses Docker when it is available and the offline path otherwise. You can pick one explicitly:

| Path | Command | What runs | Needs |
| --- | --- | --- | --- |
| **Offline** | `make quickstart-offline` | Fake LLM, DuckDB and in-memory state; the API and UI run natively | Python only; no Docker, keys or network after install |
| **Docker** | `make quickstart-docker` | Postgres checkpoints, MLflow traces (<http://localhost:5001>), the Portkey gateway, and the API and UI containers | Docker, about 4.5 GB of RAM |
| **Real LLM** | Set the variables below, then run either command | The same flow, with a hosted model behind the Portkey OSS gateway | Your own provider key |

<details>
<summary><b>Use a real LLM</b> (optional)</summary>

```bash
export DECKSMITH_LLM=portkey DECKSMITH_PORTKEY_CONFIG_DIR=configs/portkey-openai
export DECKSMITH_LLM_API_KEY=sk-...   # yours, from your shell only; never put it in a file
# Docker path: the gateway is already running on :8787. Offline path: run `npx @portkey-ai/gateway` first.
```

The agent puts the key into the gateway config in memory and sends it only to your local gateway, which calls the provider. It is never written to a file or logged ([configs/portkey-openai](configs/portkey-openai/README.md)). On the Docker path the agent container receives it as an environment variable. Real models are not deterministic, so a run can fail QA and be retried; the fake LLM never fails.

</details>

<details>
<summary><b>Run each step yourself</b></summary>

```bash
make install       # locked install with uv (pip fallback)
make seed          # data/lakehouse.duckdb, with per-user views for alice, bob and carol
make test          # unit, contract, architecture, integration and e2e tests (fake LLM)
make demo          # one deck each for bob (all regions), alice (EU-West) and carol (no access)
make api           # http://localhost:8000/docs
make ui            # http://localhost:8501 (in a second terminal)
```

Drive the API directly with the fixed test tokens (`alice-token`, `bob-token`, `carol-token`):

```bash
curl -s -X POST localhost:8000/v1/decks -H 'Authorization: Bearer bob-token' \
  -H 'Content-Type: application/json' -d '{"request":"Build the Q3 2026 customer retention review for the exec team"}'
curl -s -X POST localhost:8000/v1/decks/<run_id>/decision -H 'Authorization: Bearer bob-token' \
  -H 'Content-Type: application/json' -d '{"action":"approve"}'
curl -s -o deck.pptx localhost:8000/v1/decks/<run_id>/file -H 'Authorization: Bearer bob-token'
```

</details>

## Architecture

DeckSmith has a working local deployment and a Databricks deployment design. Settings choose the infrastructure adapters. Live SQL parity, Apps proxy authentication, Lakebase credentials, managed tracing, artifact storage and Agent Runtime hosting still need workspace validation.

### System overview

<p align="center">
  <a href="docs/assets/diagrams/system.svg"><picture>
    <source type="image/svg+xml" srcset="docs/assets/diagrams/system.svg">
    <img src="docs/assets/diagrams/system.png" alt="End-to-end system architecture. A tested local agent and a Databricks deployment design, connected through configurable adapters.">
  </picture></a>
</p>
<p align="center"><sub>Open the image for full size · Mermaid source: <a href="docs/diagrams/system.mmd"><code>docs/diagrams/system.mmd</code></a></sub></p>

A request goes from the browser through the Streamlit UI and FastAPI into the LangGraph agent, which pauses for a person's approval before it reads any data. Numeric metrics come from approved SQL templates run as the requesting user; each result becomes a fact in the registry, and checks validate writer references, chart alignment, source coverage and the approved slide structure. A dotted line joins each local service to the Databricks service that replaces it. Model calls go through the Portkey gateway to Ollama, Bedrock EU or OpenAI; in CI the in-process FakeLLM stands in for the gateway, so no keys or network are needed.

### Ports and adapters

<p align="center">
  <a href="docs/assets/diagrams/hexagonal.svg"><picture>
    <source type="image/svg+xml" srcset="docs/assets/diagrams/hexagonal.svg">
    <img src="docs/assets/diagrams/hexagonal.png" alt="Ports and adapters. The core depends only on the eight ports; each port has local and Databricks adapters, and bootstrap.py wires one per port from settings.">
  </picture></a>
</p>
<p align="center"><sub>Open the image for full size · Mermaid source: <a href="docs/diagrams/hexagonal.mmd"><code>docs/diagrams/hexagonal.mmd</code></a></sub></p>

The application core depends only on eight small `Protocol` ports, and each technology lives in an adapter with a local implementation and a Databricks implementation or deployment target. `bootstrap.py` is the composition root and the only module that imports adapters; `tests/architecture` enforces that rule, and `tests/contract` runs the same behavioural tests against each adapter of a port.

| Colour | Meaning | Colour | Meaning |
| --- | --- | --- | --- |
| Purple | People and UI | Light blue | Local adapters |
| Blue | API, agent and composition root | Orange | Databricks adapters |
| Green | Application core | Grey | Data stores and artefacts |
| Amber | Ports | Magenta | LLM gateway and models |
| Red | Guardrails and refusals | Teal / dark grey | Observability / external |

### From request to deck

<p align="center">
  <a href="docs/assets/diagrams/request-to-deck.svg"><picture>
    <source type="image/svg+xml" srcset="docs/assets/diagrams/request-to-deck.svg">
    <img src="docs/assets/diagrams/request-to-deck.png" alt="Request to deck, compact. The full version with every port call is in ARCHITECTURE.md.">
  </picture></a>
</p>
<p align="center"><sub>Open the image for full size · Mermaid source: <a href="docs/diagrams/request-to-deck.mmd"><code>docs/diagrams/request-to-deck.mmd</code></a></sub></p>

The run is checkpointed while it waits for approval. A new process can resume it when it uses the same persistent Postgres store; the default in-memory store lasts only for the current process. If any requested query is denied or returns no rows, the run stops with `no_data` and no deck is built; the message says whether access was denied or the queries returned nothing. The [full sequence](ARCHITECTURE.md#a-request-end-to-end), the [agent graph](ARCHITECTURE.md#the-agent-graph), the [security flow](ARCHITECTURE.md#security-and-permissions) and the [Compose deployment](ARCHITECTURE.md#deployment) are in [ARCHITECTURE.md](ARCHITECTURE.md), all in the same palette.

## The use case, step by step

An analyst needs the quarterly churn review for the exec team, built from governed data and safe to present.

1. **Ask.** Signed in as **bob** in the UI (<http://localhost:8501>), the analyst asks: *"Build the Q3 2026 customer retention review for the exec team."*
2. **Review the plan.** The agent proposes five slides: title, headline KPIs, monthly churn trend, monthly churn by segment, and sources. The run pauses before any data is touched. The analyst can **Edit** ("drop the segment slide"), **Reject** or **Approve**.
3. **Approve.** Only now does the agent run approved SQL templates, as bob.
4. **Download.** The default outline produces five slides and two native charts. Dropping the segment slide and approving that same run produces four slides and one chart. The required **Sources** appendix lists the facts; notes include the exact SQL, bound parameters, template hash and query timestamp. The API returns the same facts, and the UI lists them under the download button.
5. **Same request, different user.** Permissions change the outcome:

| User | Can see | Result |
| --- | --- | --- |
| **bob** | All regions | A full deck, with 6,172 active subscriptions |
| **alice** | EU-West only | A full deck with her own numbers (2,184 active subscriptions) |
| **carol** | Nothing | A clear refusal (`no_data`) and no deck |

The Q3 review reports **weighted monthly churn and NRR**, not cumulative quarter-start cohort retention. The legacy IDs `churn_rate_quarter` and `nrr_quarter` retain their names for compatibility; template descriptions and slide labels specify the monthly aggregation. `as_of` records when the query ran, not when the source table refreshed.

Downloaded decks are static files. Sharing one does not reapply the recipient's permissions.

Users can't see each other's runs (404), and anonymous calls are rejected (401). `make e2e-usecase` checks every step against the running API and writes `out/e2e-usecase.md`.

<details>
<summary><b>Example output</b> (offline path)</summary>

```text
1. API is up                                  PASS    API up at http://localhost:8000
2. bob asks for a churn review deck           PASS    run 57e6c445: outline s01, s02, s03, s04, s05, paused for approval
3. bob edits the outline (human in the loop)  PASS    edit applied (s01, s02, s03, s05); still waiting for approval
4. bob approves; data is fetched as bob       PASS    status done: 4 slides, 4 facts
5. bob downloads an editable PPTX             PASS    out/usecase-bob.pptx (4 slides, 1 native chart)
6. scalar and chart values match facts        PASS    4 scalar numbers and 3 chart points match facts; sources slide cites 4 fact IDs
7. alice (EU-West only) gets her own deck     PASS    run 39a25608: status done: 5 slides, 5 facts
8. alice's deck is consistent too             PASS    4 scalar numbers and 6 chart points match facts; sources slide cites 5 fact IDs
9. permissions change the numbers             PASS    active subscriptions: bob 6,172 (all regions) vs alice 2,184 (EU-West only)
10. carol (no access) is refused              PASS    no_data: None of the requested data is visible to you, so no deck was produced.
11. runs are private; auth is required        PASS    alice cannot see bob's run or file (404); anonymous request rejected (401)

11/11 steps passed
```

</details>

## Features

| Area | What is in place |
| --- | --- |
| Agent | LangGraph graph with a human-approval interrupt, resumable from a checkpoint; a bounded writer and QA loop |
| Numeric integrity | Scalar and series type checks, aligned chart categories/units, digit checks across writer text, source coverage, and approved slide structure |
| Data access | Approved SQL templates in Databricks SQL, transpiled to DuckDB by sqlglot; per-user views locally, Unity Catalog on Databricks |
| Output | Native, editable `.pptx` from python-pptx, with real charts and a sources appendix |
| Interfaces | FastAPI (`/v1/decks`, OpenAPI at `/docs`), a Streamlit UI, and an MLflow `ResponsesAgent` endpoint (`/responses`) |
| Observability | One MLflow span per node, JSON logs with `run_id` and `duration_ms`, and a stable [error taxonomy](docs/errors.md) |
| Evaluation | Ten golden prompts with deterministic scorers, also runnable through `mlflow.genai.evaluate` |
| Quality | ruff, strict mypy, 90% branch coverage gate, contract tests per port, an architecture test |
| Supply chain | `uv.lock` with `--locked` installs, Dependabot, pip-audit, CodeQL, trivy, hadolint, a CycloneDX SBOM, actions pinned to SHAs |
| Containers | Non-root multi-stage image without pip, `no-new-privileges`, memory and CPU limits, log rotation, healthchecks |
| Releases | Conventional Commits; release-please produces SemVer tags and the [CHANGELOG](CHANGELOG.md) |

## Project layout

```text
src/decksmith/
  domain/        DeckSpec, Fact, Outline, integrity rules, errors (pure)
  ports/         the eight Protocols
  application/   graph, nodes, SQL compiler, fact fetcher, guardrail, service
  adapters/      local/ and databricks/ implementations
  interfaces/    FastAPI, ResponsesAgent, Streamlit
  evaluation/    scorers and the golden-set harness
  seed/          synthetic data generator and UC OSS publisher
  sql/templates/ approved SQL in the Databricks dialect
  bootstrap.py   composition root
tests/           unit, contract, architecture, integration, e2e
configs/         Portkey gateway configs (local models, hosted OpenAI)
docker/          agent, MLflow and Postgres images
scripts/         quickstart, demo, use-case check, API smoke test, InstaBox bootstrap, diagram checker
docs/            decisions, errors, test plan, InstaBox guide, evidence
```

## Configuration

Every adapter is chosen with a `DECKSMITH_*` environment variable or a `.env` file. Settings are validated at start-up, so a combination that cannot work (for example `catalog=unity_catalog` with DuckDB) fails fast. [.env.example](.env.example) lists them all.

| Variable | Values (default first) | Port it selects |
| --- | --- | --- |
| `DECKSMITH_LLM` | `fake`, `portkey` | `LLMGateway` |
| `DECKSMITH_DATA_SOURCE` | `duckdb`, `databricks` | `DataSource` |
| `DECKSMITH_CATALOG` | `per_user_views`, `uc_oss`, `unity_catalog` | `Catalog` |
| `DECKSMITH_STATE_STORE` | `memory`, `postgres` | `StateStore` |
| `DECKSMITH_TRACER` | `noop`, `mlflow` | `Tracer` |
| `DECKSMITH_IDENTITY` | `static`, `jwt`, `databricks_apps` | `IdentityProvider` |

<details>
<summary><b>Other settings</b></summary>

| Variable | Default | Purpose |
| --- | --- | --- |
| `DECKSMITH_POSTGRES_DSN` | `postgresql://decksmith:decksmith@localhost:5433/decksmith` | Checkpoint store |
| `DECKSMITH_MLFLOW_TRACKING_URI` | `http://localhost:5001` | MLflow server |
| `DECKSMITH_PORTKEY_BASE_URL` | `http://localhost:8787` | Portkey gateway |
| `DECKSMITH_PORTKEY_CONFIG_DIR` | `configs/portkey` | Gateway config per model tier |
| `DECKSMITH_LLM_API_KEY` | empty | Your provider key for `llm=portkey`; held as a secret, never logged |
| `DECKSMITH_UC_OSS_URL` | `http://localhost:8081` | Unity Catalog OSS, for `catalog=uc_oss` |
| `DECKSMITH_JWT_SECRET` | empty | At least 32 characters, for `identity=jwt` |
| `DECKSMITH_DUCKDB_PATH` | `data/lakehouse.duckdb` | Local lakehouse file |
| `DECKSMITH_OUTPUT_DIR` | `out` | Where decks are written |
| `DECKSMITH_LOG_LEVEL`, `DECKSMITH_LOG_JSON` | `INFO`, `true` | Logging |
| `DECKSMITH_MAX_REQUEST_CHARS` | `2000` | Request length limit |
| `DECKSMITH_DATABRICKS_HOST`, `_WAREHOUSE_ID`, `_CATALOG` | empty, empty, `main` | Databricks adapters (tier L3) |

</details>

<details>
<summary><b>Full local stack</b> (Apple Silicon, 16 GB or more)</summary>

```bash
cp .env.example .env
make up            # Postgres :5433, MLflow :5001, UC OSS :8081, Portkey :8787, RustFS :9000/:9001
make publish       # Parquet to RustFS, plus tables registered in UC OSS as main.cs.*
ollama serve & ollama pull llama3.1:8b && ollama pull qwen2.5:14b   # optional, native
```

In `.env`, set `DECKSMITH_STATE_STORE=postgres`, `DECKSMITH_TRACER=mlflow` and `DECKSMITH_CATALOG=uc_oss`, plus `DECKSMITH_LLM=portkey` if Ollama is running. Then:

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

The model IDs in `configs/portkey` are examples only; replace them with models you have access to. The Bedrock fallback there also needs AWS credentials, which the repo does not wire in ([configs/portkey](configs/portkey/README.md)).

</details>

## Testing

```bash
make test          # unit, contract, architecture, integration and e2e (fake LLM, offline)
make check         # what CI runs: lint, strict type check, tests with the 90% coverage gate
make e2e-usecase   # the use case above, against a running API
make diagrams      # re-render the architecture images from docs/diagrams/*.mmd
```

<details>
<summary><b>What is tested where</b></summary>

| Scenario | Here | How |
| --- | --- | --- |
| E1 renderer golden | Yes | Slide XML content hash is stable across runs; overflow is flagged |
| E2 numeric integrity | Yes | Scalar references, chart values/categories, sources and the approved structure are checked |
| E3 interrupt and resume | Yes / stack | Resume in a fresh container from a shared checkpointer (offline), or from Postgres (`make stack-test`) |
| E4 request to PPTX | Yes | Full graph; QA loop recovers from invalid JSON and unknown facts, and gives up after three writes |
| E5 permissions | Yes | alice sees EU-West only; carol gets a clean `no_data` refusal |
| E6 gateway | Partly | The 446 bare-number guardrail and the rewrite are offline; retry and fallback need Portkey (`stack`) |
| E7 golden set | Yes | Ten prompts, deterministic scorers at 100%; also runs through `mlflow.genai.evaluate` |
| E8 cost and latency | Partly | Tokens recorded per node; latency is meaningful only with real models |
| E9–E11 | No | Need a Databricks workspace or staging; skipped with reasons |

The [test plan](docs/test-plan.md) defines the fidelity tiers L0–L4 and every scenario.

</details>

## Running on InstaBox

The `instabox` Compose profile is a lean stack for an 8 GB cloud VM: Postgres, MLflow, Portkey, the agent API and the UI, about 4.5 GB of memory limits in total.

```bash
cp .env.instabox .env && make up-instabox   # lean stack
make e2e-stack && make smoke-api            # E1–E8 on real Postgres, then curl drives the API
```

On a fresh [InstaBox](https://instabox.sh) VM, one command runs everything headlessly and writes `out/instabox-summary.md`:

```bash
curl -fsSL https://raw.githubusercontent.com/santoshshinde2012/deck-smith-local/main/scripts/instabox/bootstrap.sh | bash
```

<details>
<summary><b>Recording of a real run</b></summary>

![bootstrap.sh on a fresh InstaBox VM](docs/evidence/instabox-bootstrap.gif)

</details>

[docs/instabox.md](docs/instabox.md) covers the manual workflow, opening the UI from your browser, and [screenshots from a real run](docs/instabox.md#evidence-from-a-real-run).

## Security

- Requests resolve to a principal through the identity port; anonymous calls get 401, and another user's run or file gets 404.
- Queries run only from approved templates, with validated parameters, against the user's own views.
- Authentication runs before ResponsesAgent tracing. Credentials are excluded from model request bodies, trace inputs and checkpoint state; the principal travels through a `ContextVar`. Regression tests inspect stored traces with dummy credentials. Provider keys are inserted into gateway configuration in memory.
- The image runs as a non-root user without pip. CI runs CodeQL and pip-audit on every pull request, and the supply-chain workflow runs hadolint, trivy and an SBOM build whenever the images or dependencies change.

The local per-user views emulate row filters; they are **not** a security boundary. See [SECURITY.md](SECURITY.md) to report a vulnerability, and the [security and permissions diagram](ARCHITECTURE.md#security-and-permissions) for the full flow.

## Documentation and contributing

| Document | What it covers |
| --- | --- |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Diagrams, layers, ports and adapters, SOLID, fidelity of the local emulation |
| [docs/decisions.md](docs/decisions.md) | Architecture decision records |
| [docs/errors.md](docs/errors.md) | Error codes, HTTP statuses and retryability |
| [docs/test-plan.md](docs/test-plan.md) | Fidelity tiers L0–L4, scenarios E1–E11, phases LD0–LD4 |
| [docs/instabox.md](docs/instabox.md) | End-to-end runs on an 8 GB InstaBox VM |
| [configs/portkey/](configs/portkey) | Example gateway configs for each tier |
| [src/decksmith/sql/templates/](src/decksmith/sql/templates) | The approved SQL templates |
| [evals/golden/golden.jsonl](evals/golden/golden.jsonl) | Ten golden prompts with expectations |
| [CHANGELOG.md](CHANGELOG.md) | Releases |

Contributions are welcome. [CONTRIBUTING.md](CONTRIBUTING.md) covers setup, the workflow, quality gates and the dependency rule; `make help` lists every target, and a devcontainer is included. Please follow the [Code of Conduct](CODE_OF_CONDUCT.md).

## Roadmap

This repository implements phases LD0–LD1 of the [test plan](docs/test-plan.md). Next:

- **LD2.** Run the online profile against Bedrock EU with synthetic data, and add LLM-judge scorers.
- **SQL parity on Delta.** `spark` and `airflow` Compose profiles.
- **LD3.** Hybrid runs against a Databricks workspace (scenarios E9–E10).

## License

[MIT](LICENSE) © Santosh Shinde
