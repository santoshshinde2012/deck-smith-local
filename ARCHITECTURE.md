# Architecture

DeckSmith Local is the DeckSmith agent with its infrastructure swapped for local stand-ins. The agent's logic depends only on small interfaces called **ports**, and every concrete technology sits behind one of them in an **adapter**. The graph is tested on DuckDB with a fake LLM. Configurable Databricks SQL and identity adapters pass mocked tests; a live workspace deployment still needs validation and infrastructure setup.

The [README](README.md#why) explains what DeckSmith is for. The [decision records](docs/decisions.md) and the [test plan](docs/test-plan.md) complete the design.

## Contents

- [Colour key](#colour-key)
- [System context](#system-context)
- [Ports and adapters](#ports-and-adapters)
- [The agent graph](#the-agent-graph)
- [A request, end to end](#a-request-end-to-end)
- [Security and permissions](#security-and-permissions)
- [Deployment](#deployment)
- [SOLID, principle by principle](#solid-principle-by-principle)
- [How production controls are emulated locally](#how-production-controls-are-emulated-locally)
- [Adding an adapter](#adding-an-adapter)
- [Editing the diagrams](#editing-the-diagrams)

## Colour key

Every diagram in this repository uses one semantic palette on a white canvas, with dark lines and labels (#24292F). The diagrams are committed as images, so they look the same in GitHub's light and dark themes.

| Colour | Class | Meaning |
| --- | --- | --- |
| Purple | `ui` | People and the Streamlit UI |
| Blue | `app` | API, agent runtime and the composition root |
| Green | `core` | Domain and application core |
| Amber | `port` | Ports (Python `Protocol`s) |
| Light blue | `local` | Local adapters (laptop, CI, InstaBox) |
| Orange | `dbx` | Databricks adapters |
| Grey | `store` | Data stores, volumes and artefacts |
| Magenta | `llm` | LLM gateway and model calls |
| Teal | `obs` | Observability (MLflow) |
| Dark grey, dashed | `ext` | External systems |
| Red | `sec` | Security checks, guardrails and refusals |

## System context

<p align="center">
  <a href="docs/assets/diagrams/system-context.svg"><picture>
    <source type="image/svg+xml" srcset="docs/assets/diagrams/system-context.svg">
    <img src="docs/assets/diagrams/system-context.png" alt="System context. Analysts talk to the UI; the agent reaches governed data, models, state and tracing only through its ports.">
  </picture></a>
</p>
<p align="center"><sub>Open the image for full size · Mermaid source: <a href="docs/diagrams/system-context.mmd"><code>docs/diagrams/system-context.mmd</code></a></sub></p>

The planner picks approved SQL templates. Numeric metrics reference scalar facts or chart-series facts; checks validate their types and citations. The ports have local implementations and proposed Databricks replacements. Managed state, tracing and storage require deployment configuration and live verification.

## Ports and adapters

<p align="center">
  <a href="docs/assets/diagrams/hexagonal.svg"><picture>
    <source type="image/svg+xml" srcset="docs/assets/diagrams/hexagonal.svg">
    <img src="docs/assets/diagrams/hexagonal.png" alt="Ports and adapters. The core depends only on the eight ports; each port has local and Databricks adapters, and bootstrap.py wires one per port from settings.">
  </picture></a>
</p>
<p align="center"><sub>Open the image for full size · Mermaid source: <a href="docs/diagrams/hexagonal.mmd"><code>docs/diagrams/hexagonal.mmd</code></a></sub></p>

| Layer | Package | May import |
| --- | --- | --- |
| Domain | `decksmith.domain` | Standard library and pydantic only |
| Ports | `decksmith.ports` | Domain |
| Application | `decksmith.application` | Domain, ports, LangGraph, sqlglot |
| Adapters | `decksmith.adapters.local`, `decksmith.adapters.databricks` | Domain, ports, their own SDKs; never each other |
| Composition root | `decksmith.bootstrap` | Everything; it is the only module that imports adapters |
| Interfaces | `decksmith.interfaces` | Application, bootstrap |

`tests/architecture/test_dependencies.py` enforces this table. It parses every module's imports, and CI fails when a layer reaches outward.

| Port | What it does | Local adapters | Databricks adapter |
| --- | --- | --- | --- |
| `LLMGateway` | One gateway for every model call | `FakeLLM` (CI), `PortkeyGateway` (Portkey OSS: Ollama, or a hosted provider with your key) | `PortkeyGateway` pointed at Portkey Enterprise hybrid |
| `DataSource` | Runs approved SQL as the user | `DuckDBDataSource` (read-only attach) | `DatabricksSqlDataSource` (SQL Statement Execution API with the user's token) |
| `Catalog` | Logical table name to the object this user may query | `PerUserViewCatalog`, optionally wrapped by `UnityCatalogOssCatalog` | `UnityCatalogPassthrough` (UC enforces row filters) |
| `TemplateRepository` | Approved, parameterised SQL templates | `FileTemplateRepository` (`src/decksmith/sql/templates/*.sql`) | Same files |
| `Renderer` | DeckSpec plus facts to `.pptx` | `PptxRenderer` (python-pptx, theme, layout registry, native charts) | Same |
| `StateStore` | LangGraph checkpoints | `InMemoryStateStore`, `PostgresStateStore` | `PostgresStateStore` pointed at Lakebase |
| `Tracer` | One span per node | `NoopTracer`, `MlflowTracer` (MLflow OSS) | `MlflowTracer` (managed MLflow) |
| `IdentityProvider` | Request headers to a `Principal` | `StaticTokenIdentity` (alice, bob, carol), `JwtIdentity` | `DatabricksAppsIdentity` (`x-forwarded-access-token`) |

You select each adapter with a `DECKSMITH_*` variable (see [Configuration](README.md#configuration)). The SQL templates are written once, in Databricks SQL. `SqlCompiler` transpiles them with sqlglot for DuckDB; on Databricks the step does nothing.

## The agent graph

<p align="center">
  <a href="docs/assets/diagrams/agent-graph.svg"><picture>
    <source type="image/svg+xml" srcset="docs/assets/diagrams/agent-graph.svg">
    <img src="docs/assets/diagrams/agent-graph.png" alt="The agent graph: a human approval interrupt, a no-data exit, and a bounded writer and QA loop.">
  </picture></a>
</p>
<p align="center"><sub>Open the image for full size · Mermaid source: <a href="docs/diagrams/agent-graph.mmd"><code>docs/diagrams/agent-graph.mmd</code></a></sub></p>

The graph enforces three rules:

- **The LLM never writes SQL.** The planner picks a template ID and gives parameters as strings. `validate_params` checks them against each template's types and patterns when the planner proposes the outline, so a bad plan fails before approval and before any query runs.
- **Numeric metrics use typed facts.** Only `data_fetch` adds query results to the fact registry. Writer text uses scalar placeholders, while charts use series references. Checks reject missing references, series used as scalar placeholders, inconsistent chart categories/units and missing source coverage. Two checks catch bare digits in writer text, including notes and chart names: the `NoBareNumbersGuardrail` gateway decorator, which stands in for Portkey's guardrail and returns status 446, and the deterministic `check` node. Either one sends the run back to the writer. After three writes the run fails and no deck is rendered.
- **No data means no deck.** If any requested query is denied or returns no rows, the run ends with `no_data` and a plain explanation, never a partial or empty deck. The message mentions access only when the catalog or warehouse refused the user; an empty result may mean the period has no data or that row-level policies hid it.

The final check also enforces the approved slide IDs, order, layouts, audience and period, and a sources appendix covering referenced facts. These checks do not prove that a title or recommendation is a sound interpretation. Spelled-out numbers and metric meanings require review.

Facts retain executed SQL, normalized parameters, a template hash and the query timestamp. That provenance supports reproduction; it does not establish source freshness or a table snapshot version.

## A request, end to end

<p align="center">
  <a href="docs/assets/diagrams/request-sequence.svg"><picture>
    <source type="image/svg+xml" srcset="docs/assets/diagrams/request-sequence.svg">
    <img src="docs/assets/diagrams/request-sequence.png" alt="Request to deck. The run pauses for approval before any data is read; data is fetched as the user; the writer is guarded and checked before rendering.">
  </picture></a>
</p>
<p align="center"><sub>Open the image for full size · Mermaid source: <a href="docs/diagrams/request-sequence.mmd"><code>docs/diagrams/request-sequence.mmd</code></a></sub></p>

The `Principal`, which carries the user's token, travels in a `ContextVar` (`application/context.py`). HTTP authentication occurs before ResponsesAgent tracing. Only a credential-free model request enters the automatically traced `predict` method; credential-bearing custom inputs are rejected before tracing. The principal never enters graph state. Direct integrations use the authenticated header entry point rather than putting credentials in `custom_inputs`. Each step logs a JSON line with `run_id` and `duration_ms`, and errors follow the taxonomy in [docs/errors.md](docs/errors.md).

## Security and permissions

<p align="center">
  <a href="docs/assets/diagrams/security-flow.svg"><picture>
    <source type="image/svg+xml" srcset="docs/assets/diagrams/security-flow.svg">
    <img src="docs/assets/diagrams/security-flow.png" alt="Security and permissions. Every request becomes a principal; data is read only through approved templates and the user's own views; numbers come only from facts; runs belong to their owner.">
  </picture></a>
</p>
<p align="center"><sub>Open the image for full size · Mermaid source: <a href="docs/diagrams/security-flow.mmd"><code>docs/diagrams/security-flow.mmd</code></a></sub></p>

- **Who you are.** `StaticTokenIdentity` maps the fixed test tokens to alice (her region only), bob (all regions) and carol (no access). `JwtIdentity` validates HS256 tokens; `DatabricksAppsIdentity` reads the on-behalf-of token that Databricks Apps forwards.
- **What you can see.** Locally, each user has one view per table (`v_<table>__<user>`) and no view means no access. On Databricks, Unity Catalog row filters do the same job. The local views are an emulation, **not a security boundary** ([SECURITY.md](SECURITY.md)).
- **Whose run it is.** Runs and file downloads are looked up by owner, so another user gets 404. This does not enforce recipient permissions on a copied or emailed PowerPoint. Saved decks reflect query-time access and do not automatically respond to later policy changes.
- **Secrets.** A provider key for the real-LLM path comes from `DECKSMITH_LLM_API_KEY`, is held as a `SecretStr`, is filled into the gateway config in memory only, and never appears in logs or files.

## Deployment

<p align="center">
  <a href="docs/assets/diagrams/deployment.svg"><picture>
    <source type="image/svg+xml" srcset="docs/assets/diagrams/deployment.svg">
    <img src="docs/assets/diagrams/deployment.png" alt="Deployment. One Compose project with three profiles: core (full stack), app (agent containers) and instabox (lean, about 4.5 GB). Host ports are on the left of each arrow label.">
  </picture></a>
</p>
<p align="center"><sub>Open the image for full size · Mermaid source: <a href="docs/diagrams/deployment.mmd"><code>docs/diagrams/deployment.mmd</code></a></sub></p>

| Profile | Services | Use it for |
| --- | --- | --- |
| `instabox` | postgres, mlflow, portkey, agent, ui (about 4.5 GB of limits) | `make quickstart-docker`, CI `stack-e2e`, 8 GB VMs |
| `core` | postgres, mlflow, portkey, unitycatalog, objectstore | The full local stack (`make up`), with the agent native or via `app` |
| `app` | agent, ui | Adding the containerised agent to `core` (`make up-app`) |

Every service has memory and CPU limits, log rotation and `no-new-privileges`, and every service in the `instabox` profile has a healthcheck. The agent and UI share one multi-stage image that runs as a non-root user and ships without pip.

## SOLID, principle by principle

**Single responsibility.** Each class has one reason to change: `SqlCompiler` resolves table names and transpiles SQL; `FactFetcher` turns query rows into `Fact` objects; `DeckNodes` holds one method per graph step; `DeckService` holds the use cases (start, decide, get); `PptxRenderer` only renders; the numeric-integrity rules are pure functions in `domain/integrity.py`.

**Open/closed.** Behaviour is extended without editing the core. The bare-number guardrail is a decorator around any `LLMGateway`, and `UnityCatalogOssCatalog` is a decorator around any `Catalog`. A new slide layout is a painter added to `LayoutRegistry`; a new theme is a token set. A new backend means a new adapter plus one factory in `bootstrap.py`; nothing in `domain`, `ports` or `application` changes.

**Liskov substitution.** Local and Databricks adapters satisfy the same `Protocol` with the same error contract: access problems raise `AccessDenied`, bad credentials raise `AuthenticationError`. `tests/contract/` runs the same behavioural assertions against every offline-constructible adapter of a port, so the application has no branches by environment. Every domain error carries a stable `code`, `category`, `status_code` and `retryable` flag, and the API maps errors only from those attributes.

**Interface segregation.** Eight small ports, not one "platform" object. The renderer knows nothing about SQL, the data source knows nothing about LLMs, and `StateStore` exposes only `checkpointer()` and `close()`.

**Dependency inversion.** The application depends on abstractions in `decksmith.ports`. Concrete classes are created in one place:

<p align="center">
  <a href="docs/assets/diagrams/composition-root.svg"><picture>
    <source type="image/svg+xml" srcset="docs/assets/diagrams/composition-root.svg">
    <img src="docs/assets/diagrams/composition-root.png" alt="Settings choose one adapter per port; bootstrap is the only place concrete classes are built.">
  </picture></a>
</p>
<p align="center"><sub>Open the image for full size · Mermaid source: <a href="docs/diagrams/composition-root.mmd"><code>docs/diagrams/composition-root.mmd</code></a></sub></p>

Tests use the same root and override only what they need. For example, `build_container(settings, llm=FakeLLM({"writer": ["bare_digit"]}))` drives the QA loop.

## How production controls are emulated locally

| Production control | Local stand-in | Fidelity |
| --- | --- | --- |
| UC row filters by region | One view per user and table (`v_<table>__<user>`); no view means `AccessDenied` | Same results for the three test users. The emulation is not a security boundary |
| Apps OBO token | Static bearer tokens (`alice-token`, and so on) or HS256 JWTs | Same `Principal` shape. Real OBO is scenario E10, tier L3 |
| Lakebase checkpoints | Postgres 18 with LangGraph `PostgresSaver` | Same saver |
| Managed MLflow | MLflow 3 OSS server with a Postgres store | Same tracing and `genai.evaluate` APIs |
| Portkey Enterprise hybrid | Portkey OSS gateway; configs sent inline in `x-portkey-config` | No stored configs, budgets or virtual keys locally. The 446 guardrail is emulated in code |
| Databricks SQL warehouse | DuckDB with sqlglot transpiling Databricks SQL | Parity is scenario E9, tier L3, not yet verified |
| S3 or UC volumes | RustFS (S3-compatible), because Docker Hub no longer serves `minio/minio` | S3 API only |

## Adding an adapter

1. Implement the port's `Protocol` in `adapters/local/` or `adapters/databricks/`. Raise the domain errors, not SDK errors.
2. Add a factory to the matching registry in `bootstrap.py`, and add a `Literal` value in `config.py`.
3. Add unit tests, and add the adapter to its port's suite in `tests/contract/`. Use `httpx.MockTransport` or a stub client; no network. If the adapter needs other settings, add a rule to the validator in `config.py`.
4. Run `make check`. The architecture test catches any import that crosses a layer.

## Editing the diagrams

Each diagram's Mermaid source is a file in [`docs/diagrams/`](docs/diagrams). `make diagrams` renders every source to an SVG and a PNG fallback in [`docs/assets/diagrams/`](docs/assets/diagrams), on a white background with the shared theme in [`docs/diagrams/mermaid.json`](docs/diagrams/mermaid.json). The Markdown embeds those images rather than Mermaid blocks, because GitHub re-themes Mermaid blocks in dark mode and the white canvas would be lost.

1. Edit or add `docs/diagrams/<name>.mmd`. Start it with `%% diagram: <name>` and a `%% caption:` line; the caption becomes the image's alt text.
2. Use only the classes in the [colour key](#colour-key), copied verbatim from `PALETTE` in [`scripts/diagrams.py`](scripts/diagrams.py), and the shared group style. Don't add a `%%{init}%%` block.
3. Run `make diagrams` (Node.js for `npx`, or `MMDC` pointing at an installed `mmdc`), embed the image where it belongs, and commit the source, the images and `manifest.json` together.

`make diagrams-check`, which CI runs, fails when a source breaks a rule, a document still contains a Mermaid block, an embedded image is missing, or an image is older than its source. `manifest.json` records a hash of each source and the theme for that comparison.
