# Architecture

DeckSmith Local is the DeckSmith agent with its infrastructure swapped for local stand-ins. The agent's logic depends only on small interfaces called **ports**, and every concrete technology sits behind one of them in an **adapter**. The same graph runs on DuckDB with a fake LLM in CI, or on the Databricks SQL Statement API with on-behalf-of user tokens, and only configuration changes.

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

Every diagram in this repository uses one semantic palette. Node colours are fixed, so they read the same in GitHub's light and dark themes; lines, labels and group outlines follow the theme.

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

```mermaid
%% diagram: system-context
%% caption: System context. Analysts talk to the UI; the agent reaches governed data, models, state and tracing only through its ports.
flowchart TB
  subgraph PEOPLE["People"]
    AN(["Analyst<br/>bob · alice · carol"]):::ui
  end

  subgraph SYS["deck-smith-local"]
    UI("Streamlit UI<br/>:8501"):::ui
    API("DeckSmith API + agent<br/>FastAPI · LangGraph · :8000"):::app
  end

  subgraph DEPS["Behind the ports: swapped by configuration"]
    IDP("Identity<br/>test tokens · JWT · Apps OBO"):::sec
    DATA[("Governed data<br/>DuckDB views → Databricks SQL")]:::store
    STATE[("Checkpoints<br/>Postgres → Lakebase")]:::store
    GW("LLM gateway<br/>Portkey OSS → Enterprise"):::llm
    OBS("Tracing and evals<br/>MLflow 3"):::obs
  end

  MODELS("Model providers<br/>Ollama · OpenAI · Bedrock"):::ext
  DECK[/"Editable .pptx<br/>facts + sources slide"/]:::store

  AN -->|asks, reviews outline, approves| UI
  UI -->|REST + bearer token| API
  API -->|resolve principal| IDP
  API -->|approved SQL, as the user| DATA
  API -->|pause and resume| STATE
  API -->|prompts; numbers only as fact IDs| GW
  GW -->|routes, retries, falls back| MODELS
  API -->|one span per node| OBS
  API -->|renders| DECK
  DECK -->|download| AN

  subgraph LEGEND["Legend"]
    direction LR
    K1(["UI / people"]):::ui ~~~ K2("Agent"):::app ~~~ K3("Identity"):::sec ~~~ K4[("Data store")]:::store ~~~ K5("LLM"):::llm ~~~ K6("Observability"):::obs ~~~ K7("External"):::ext
  end

  classDef ui fill:#8250DF,stroke:#6639BA,stroke-width:2px,color:#FFFFFF
  classDef app fill:#0969DA,stroke:#0550AE,stroke-width:2px,color:#FFFFFF
  classDef core fill:#1A7F37,stroke:#116329,stroke-width:2px,color:#FFFFFF
  classDef port fill:#FFF8C5,stroke:#9A6700,stroke-width:2px,color:#3B2300
  classDef local fill:#DDF4FF,stroke:#0969DA,stroke-width:2px,color:#0A3069
  classDef dbx fill:#FFF1E5,stroke:#BC4C00,stroke-width:2px,color:#762C00
  classDef store fill:#EAEEF2,stroke:#57606A,stroke-width:2px,color:#24292F
  classDef llm fill:#BF3989,stroke:#99286E,stroke-width:2px,color:#FFFFFF
  classDef obs fill:#1B7C83,stroke:#0E5A60,stroke-width:2px,color:#FFFFFF
  classDef ext fill:#57606A,stroke:#32383F,stroke-width:2px,color:#FFFFFF,stroke-dasharray:4 3
  classDef sec fill:#FFEBE9,stroke:#CF222E,stroke-width:2px,color:#82071E
  style PEOPLE fill:transparent,stroke:#8C959F,stroke-width:1px,stroke-dasharray:6 4
  style SYS fill:transparent,stroke:#8C959F,stroke-width:1px,stroke-dasharray:6 4
  style DEPS fill:transparent,stroke:#8C959F,stroke-width:1px,stroke-dasharray:6 4
  style LEGEND fill:transparent,stroke:#8C959F,stroke-width:1px,stroke-dasharray:6 4
```

The LLM never writes SQL and never types a number: it picks approved templates, and every figure in its output is a `{{fact:fN}}` reference that the renderer fills in. Every box under "Behind the ports" has a local and a Databricks implementation.

## Ports and adapters

```mermaid
%% diagram: hexagonal
%% caption: Ports and adapters. The core depends only on the eight ports; each port has local and Databricks adapters, and bootstrap.py wires one per port from settings.
flowchart TB
  subgraph DRIVING["Interfaces"]
    UI(["Streamlit UI"]):::ui
    API("FastAPI<br/>/v1/decks"):::app
    RA("ResponsesAgent<br/>/responses"):::app
  end

  subgraph CORE["Application core: no I/O, no SDKs"]
    SVC("DeckService<br/>start · decide · get"):::core
    GRAPH("LangGraph agent<br/>plan · approve · fetch<br/>write · check · render"):::core
    DOM("Domain<br/>DeckSpec · Fact · integrity"):::core
    GUARD("No-bare-numbers<br/>guardrail (446)"):::sec
    BOOT("bootstrap.py<br/>composition root"):::app
  end

  subgraph PORTS["Ports: eight Protocols"]
    P_ID{{"Identity<br/>Provider"}}:::port
    P_TPL{{"Template<br/>Repository"}}:::port
    P_CAT{{"Catalog"}}:::port
    P_DS{{"Data<br/>Source"}}:::port
    P_REN{{"Renderer"}}:::port
    P_ST{{"State<br/>Store"}}:::port
    P_TR{{"Tracer"}}:::port
    P_LLM{{"LLM<br/>Gateway"}}:::port
  end

  subgraph LOCAL["Local adapters: laptop, CI, InstaBox"]
    L_ID("Static tokens<br/>JWT"):::local
    L_TPL("SQL template<br/>files"):::local
    L_CAT("Per-user views<br/>+ UC OSS names"):::local
    L_DS("DuckDB<br/>via sqlglot"):::local
    L_REN("python-pptx<br/>native charts"):::local
    L_ST("In-memory<br/>Postgres 18"):::local
    L_TR("No-op<br/>MLflow OSS"):::local
    L_LLM("FakeLLM<br/>Portkey OSS"):::local
  end

  subgraph DBX["Databricks adapters"]
    D_ID("Apps<br/>on-behalf-of"):::dbx
    D_TPL("Same template<br/>files"):::dbx
    D_CAT("Unity Catalog<br/>row filters"):::dbx
    D_DS("SQL Statement<br/>API"):::dbx
    D_REN("Same<br/>renderer"):::dbx
    D_ST("Lakebase<br/>Postgres"):::dbx
    D_TR("Managed<br/>MLflow"):::dbx
    D_LLM("Portkey<br/>Enterprise hybrid"):::dbx
  end

  UI -->|HTTP + bearer token| API
  API --> SVC
  RA --> SVC
  BOOT -.->|builds with chosen adapters| SVC
  SVC --> GRAPH
  GRAPH --> DOM
  GRAPH --> P_ID & P_TPL & P_CAT & P_DS & P_REN & P_ST & P_TR
  GRAPH -->|writer| GUARD --> P_LLM

  P_ID -.- L_ID -.- D_ID
  P_LLM -.- L_LLM -.- D_LLM
  P_TPL -.- L_TPL -.- D_TPL
  P_CAT -.- L_CAT -.- D_CAT
  P_DS -.- L_DS -.- D_DS
  P_REN -.- L_REN -.- D_REN
  P_ST -.- L_ST -.- D_ST
  P_TR -.- L_TR -.- D_TR

  subgraph LEGEND["Legend · solid arrow: calls · dotted line: implements"]
    direction LR
    K1(["UI"]):::ui ~~~ K2("API · wiring"):::app ~~~ K3("Core"):::core ~~~ K4{{"Port"}}:::port ~~~ K5("Local adapter"):::local ~~~ K6("Databricks adapter"):::dbx ~~~ K7("Guardrail"):::sec
  end

  classDef ui fill:#8250DF,stroke:#6639BA,stroke-width:2px,color:#FFFFFF
  classDef app fill:#0969DA,stroke:#0550AE,stroke-width:2px,color:#FFFFFF
  classDef core fill:#1A7F37,stroke:#116329,stroke-width:2px,color:#FFFFFF
  classDef port fill:#FFF8C5,stroke:#9A6700,stroke-width:2px,color:#3B2300
  classDef local fill:#DDF4FF,stroke:#0969DA,stroke-width:2px,color:#0A3069
  classDef dbx fill:#FFF1E5,stroke:#BC4C00,stroke-width:2px,color:#762C00
  classDef store fill:#EAEEF2,stroke:#57606A,stroke-width:2px,color:#24292F
  classDef llm fill:#BF3989,stroke:#99286E,stroke-width:2px,color:#FFFFFF
  classDef obs fill:#1B7C83,stroke:#0E5A60,stroke-width:2px,color:#FFFFFF
  classDef ext fill:#57606A,stroke:#32383F,stroke-width:2px,color:#FFFFFF,stroke-dasharray:4 3
  classDef sec fill:#FFEBE9,stroke:#CF222E,stroke-width:2px,color:#82071E
  style DRIVING fill:transparent,stroke:#8C959F,stroke-width:1px,stroke-dasharray:6 4
  style CORE fill:transparent,stroke:#8C959F,stroke-width:1px,stroke-dasharray:6 4
  style PORTS fill:transparent,stroke:#8C959F,stroke-width:1px,stroke-dasharray:6 4
  style LOCAL fill:transparent,stroke:#8C959F,stroke-width:1px,stroke-dasharray:6 4
  style DBX fill:transparent,stroke:#8C959F,stroke-width:1px,stroke-dasharray:6 4
  style LEGEND fill:transparent,stroke:#8C959F,stroke-width:1px,stroke-dasharray:6 4
```

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
| `Renderer` | DeckSpec plus facts to `.pptx` | `PptxRenderer` (python-pptx, native charts) | Same |
| `StateStore` | LangGraph checkpoints | `InMemoryStateStore`, `PostgresStateStore` | `PostgresStateStore` pointed at Lakebase |
| `Tracer` | One span per node | `NoopTracer`, `MlflowTracer` (MLflow OSS) | `MlflowTracer` (managed MLflow) |
| `IdentityProvider` | Request headers to a `Principal` | `StaticTokenIdentity` (alice, bob, carol), `JwtIdentity` | `DatabricksAppsIdentity` (`x-forwarded-access-token`) |

You select each adapter with a `DECKSMITH_*` variable (see [Configuration](README.md#configuration)). The SQL templates are written once, in Databricks SQL. `SqlCompiler` transpiles them with sqlglot for DuckDB; on Databricks the step does nothing.

## The agent graph

```mermaid
%% diagram: agent-graph
%% caption: The agent graph: a human approval interrupt, a no-data exit, and a bounded writer and QA loop.
stateDiagram-v2
  direction LR
  [*] --> intake
  intake --> planner
  planner --> await_approval
  await_approval --> data_fetch: approve
  await_approval --> planner: edit
  await_approval --> [*]: reject
  data_fetch --> writer: facts
  data_fetch --> no_data: no visible rows
  writer --> check
  check --> render: clean
  check --> writer: issues, max 3 writes
  check --> failed: still failing
  render --> [*]
  no_data --> [*]
  failed --> [*]

  class intake, planner, data_fetch, writer, render core
  class await_approval ui
  class check sec
  class no_data, failed sec
  classDef ui fill:#8250DF,stroke:#6639BA,stroke-width:2px,color:#FFFFFF
  classDef app fill:#0969DA,stroke:#0550AE,stroke-width:2px,color:#FFFFFF
  classDef core fill:#1A7F37,stroke:#116329,stroke-width:2px,color:#FFFFFF
  classDef port fill:#FFF8C5,stroke:#9A6700,stroke-width:2px,color:#3B2300
  classDef local fill:#DDF4FF,stroke:#0969DA,stroke-width:2px,color:#0A3069
  classDef dbx fill:#FFF1E5,stroke:#BC4C00,stroke-width:2px,color:#762C00
  classDef store fill:#EAEEF2,stroke:#57606A,stroke-width:2px,color:#24292F
  classDef llm fill:#BF3989,stroke:#99286E,stroke-width:2px,color:#FFFFFF
  classDef obs fill:#1B7C83,stroke:#0E5A60,stroke-width:2px,color:#FFFFFF
  classDef ext fill:#57606A,stroke:#32383F,stroke-width:2px,color:#FFFFFF,stroke-dasharray:4 3
  classDef sec fill:#FFEBE9,stroke:#CF222E,stroke-width:2px,color:#82071E
```

The graph enforces three rules:

- **The LLM never writes SQL.** The planner picks a template ID and gives parameters as strings. `validate_params` checks them against each template's types and patterns before any query runs.
- **The LLM never writes numbers.** Only `data_fetch` creates `Fact` objects. The writer must refer to a number as `{{fact:fN}}`. Two checks catch bare digits: the `NoBareNumbersGuardrail` gateway decorator, which stands in for Portkey's guardrail and returns status 446, and the deterministic `check` node. Either one sends the run back to the writer. After three writes the run fails and no deck is rendered.
- **No data means no deck.** If none of the requested queries returns rows the user may see, the run ends with `no_data` and a plain explanation, never an empty deck.

## A request, end to end

```mermaid
%% diagram: request-sequence
%% caption: Request to deck. The run pauses for approval before any data is read; data is fetched as the user; the writer is guarded and checked before rendering.
sequenceDiagram
  autonumber
  box rgba(130,80,223,0.14) Client
    actor U as Analyst (bob)
    participant UI as Streamlit UI
  end
  box rgba(9,105,218,0.12) DeckSmith
    participant API as FastAPI
    participant G as LangGraph agent
  end
  box rgba(154,103,0,0.14) Ports and adapters
    participant ID as IdentityProvider
    participant L as LLMGateway
    participant ST as StateStore
    participant D as Catalog + DataSource
    participant R as Renderer
  end

  U->>UI: "Build the Q3 2026 retention review"
  UI->>API: POST /v1/decks (Bearer bob-token)
  API->>ID: principal(headers)
  ID-->>API: bob, all regions
  API->>G: start(request) with principal in a ContextVar
  G->>L: intake + planner (small tier)
  L-->>G: outline s01–s05 and template IDs
  G->>ST: checkpoint, then interrupt
  G-->>UI: awaiting_approval + outline
  rect rgba(26,127,55,0.12)
    Note over U,UI: Human in the loop: nothing has been read yet
    U->>UI: Edit ("drop the segment slide") or Approve
    UI->>API: POST /v1/decks/{id}/decision
    API->>G: resume from checkpoint
  end
  G->>D: approved SQL templates, as bob
  alt nothing visible to the user
    D-->>G: empty
    G-->>UI: status no_data, no deck
  else rows
    D-->>G: rows → facts f1…f5
    loop at most 3 writes
      G->>L: writer (strong tier), behind the bare-number guardrail
      L-->>G: slides that cite {{fact:fN}}
      G->>G: check numeric integrity and chart consistency
    end
    G->>R: render(spec, facts)
    R-->>G: .pptx with native charts and a sources slide
    G-->>UI: done, 5 slides, 5 facts
    UI->>API: GET /v1/decks/{id}/file
    API-->>U: editable PowerPoint
  end
```

The `Principal`, which carries the user's token, travels in a `ContextVar` (`application/context.py`). It is never stored in graph state, so the token is never written into a checkpoint. Each step logs a JSON line with `run_id` and `duration_ms`, and errors follow the taxonomy in [docs/errors.md](docs/errors.md).

## Security and permissions

```mermaid
%% diagram: security-flow
%% caption: Security and permissions. Every request becomes a principal; data is read only through approved templates and the user's own views; numbers come only from facts; runs belong to their owner.
flowchart TB
  REQ(["Request<br/>Authorization: Bearer …"]):::ui
  ID{{"IdentityProvider"}}:::port
  E401("401<br/>authentication_failed"):::sec
  PRIN("Principal<br/>user · groups · token<br/>held in a ContextVar,<br/>never checkpointed"):::core
  PLAN("Planner<br/>picks template IDs only;<br/>the LLM writes no SQL"):::core
  VAL("validate_params<br/>types and patterns"):::sec
  E422("422<br/>invalid_parameters"):::sec
  CAT{{"Catalog"}}:::port
  SKIP("Query skipped<br/>AccessDenied is caught"):::sec
  DS{{"DataSource"}}:::port
  E409("Status no_data<br/>a refusal, not an empty deck"):::sec
  FACTS("Facts f1…fn<br/>with provenance"):::core
  WRITE("Writer<br/>refers to {{fact:fN}}"):::llm
  G446("Guardrail + check<br/>bare digit → rewrite (446)<br/>max 3 writes"):::sec
  DECK[/"Deck owned by the user"/]:::store
  E404("404 to anyone else<br/>run_not_found"):::sec

  REQ --> ID
  ID -->|unknown or missing token| E401
  ID -->|valid| PRIN --> PLAN --> VAL
  VAL -->|bad parameter| E422
  VAL -->|ok| CAT
  CAT -->|"table → the user's view<br/>(UC row filters on Databricks)"| DS
  CAT -->|no view for this user| SKIP
  SKIP -->|no facts at all| E409
  DS -->|no rows| SKIP
  DS -->|rows| FACTS --> WRITE --> G446
  G446 -->|clean| DECK
  DECK -->|GET /file by another user| E404

  subgraph LEGEND["Legend"]
    direction TB
    K1(["Caller"]):::ui ~~~ K2{{"Port"}}:::port ~~~ K3("Core step"):::core ~~~ K4("LLM step"):::llm ~~~ K5("Check or refusal"):::sec ~~~ K6[/"Artefact"/]:::store
  end

  classDef ui fill:#8250DF,stroke:#6639BA,stroke-width:2px,color:#FFFFFF
  classDef app fill:#0969DA,stroke:#0550AE,stroke-width:2px,color:#FFFFFF
  classDef core fill:#1A7F37,stroke:#116329,stroke-width:2px,color:#FFFFFF
  classDef port fill:#FFF8C5,stroke:#9A6700,stroke-width:2px,color:#3B2300
  classDef local fill:#DDF4FF,stroke:#0969DA,stroke-width:2px,color:#0A3069
  classDef dbx fill:#FFF1E5,stroke:#BC4C00,stroke-width:2px,color:#762C00
  classDef store fill:#EAEEF2,stroke:#57606A,stroke-width:2px,color:#24292F
  classDef llm fill:#BF3989,stroke:#99286E,stroke-width:2px,color:#FFFFFF
  classDef obs fill:#1B7C83,stroke:#0E5A60,stroke-width:2px,color:#FFFFFF
  classDef ext fill:#57606A,stroke:#32383F,stroke-width:2px,color:#FFFFFF,stroke-dasharray:4 3
  classDef sec fill:#FFEBE9,stroke:#CF222E,stroke-width:2px,color:#82071E
  style LEGEND fill:transparent,stroke:#8C959F,stroke-width:1px,stroke-dasharray:6 4
```

- **Who you are.** `StaticTokenIdentity` maps the fixed test tokens to alice (EU-West), bob (all regions) and carol (no access). `JwtIdentity` validates HS256 tokens; `DatabricksAppsIdentity` reads the on-behalf-of token that Databricks Apps forwards.
- **What you can see.** Locally, each user has one view per table (`v_<table>__<user>`) and no view means no access. On Databricks, Unity Catalog row filters do the same job. The local views are an emulation, **not a security boundary** ([SECURITY.md](SECURITY.md)).
- **Whose run it is.** Runs and files are looked up by owner, so another user gets 404, not 403, and learns nothing about the run.
- **Secrets.** A provider key for the real-LLM path comes from `DECKSMITH_LLM_API_KEY`, is held as a `SecretStr`, is filled into the gateway config in memory only, and never appears in logs or files.

## Deployment

```mermaid
%% diagram: deployment
%% caption: Deployment. One Compose project with three profiles: core (full stack), app (agent containers) and instabox (lean, about 4.5 GB). Host ports are on the left of each arrow label.
flowchart TB
  BROWSER(["Browser / curl"]):::ui

  subgraph HOST["Docker Compose project: decksmith-local"]
    subgraph APPS["Agent containers · profiles: app, instabox"]
      UI("ui<br/>Streamlit · 8501"):::ui
      AGENT("agent<br/>FastAPI + LangGraph · 8000<br/>non-root, read-only data"):::app
    end
    subgraph PLATFORM["Platform services · profiles: core, instabox"]
      PG[("postgres<br/>Postgres 18 · 5433→5432")]:::store
      MLF("mlflow<br/>MLflow 3 · 5001→5000"):::obs
      PK("portkey<br/>Portkey OSS gateway · 8787"):::llm
    end
    subgraph COREONLY["Full stack only · profile: core"]
      UC("unitycatalog<br/>UC OSS · 8081→8080"):::store
      S3[("objectstore<br/>RustFS S3 · 9000, 9001")]:::store
    end
    subgraph VOLS["Named volumes"]
      V1[("pg18-data")]:::store
      V2[("mlflow-artifacts")]:::store
      V3[("agent-out<br/>generated decks")]:::store
      V4[("object-data")]:::store
    end
  end

  LAKE[("./data/lakehouse.duckdb<br/>synthetic, seed 42")]:::store
  OLLAMA("Ollama on the host<br/>optional · 11434"):::ext
  CLOUD("Hosted providers<br/>your own key"):::ext

  BROWSER -->|":8501"| UI
  BROWSER -->|":8000 /docs"| AGENT
  BROWSER -->|":5001 traces"| MLF
  UI -->|"http://agent:8000"| AGENT
  AGENT -->|checkpoints| PG
  AGENT -->|spans| MLF
  AGENT -->|LLM calls| PK
  AGENT -->|"bind mount, read-only"| LAKE
  AGENT --- V3
  MLF -->|backend store| PG
  MLF --- V2
  PG --- V1
  S3 --- V4
  PK -.-> OLLAMA
  PK -.-> CLOUD

  subgraph LEGEND["Legend"]
    direction LR
    K1(["UI"]):::ui ~~~ K2("Agent"):::app ~~~ K3[("Store / volume")]:::store ~~~ K4("Gateway"):::llm ~~~ K5("Observability"):::obs ~~~ K6("External"):::ext
  end

  classDef ui fill:#8250DF,stroke:#6639BA,stroke-width:2px,color:#FFFFFF
  classDef app fill:#0969DA,stroke:#0550AE,stroke-width:2px,color:#FFFFFF
  classDef core fill:#1A7F37,stroke:#116329,stroke-width:2px,color:#FFFFFF
  classDef port fill:#FFF8C5,stroke:#9A6700,stroke-width:2px,color:#3B2300
  classDef local fill:#DDF4FF,stroke:#0969DA,stroke-width:2px,color:#0A3069
  classDef dbx fill:#FFF1E5,stroke:#BC4C00,stroke-width:2px,color:#762C00
  classDef store fill:#EAEEF2,stroke:#57606A,stroke-width:2px,color:#24292F
  classDef llm fill:#BF3989,stroke:#99286E,stroke-width:2px,color:#FFFFFF
  classDef obs fill:#1B7C83,stroke:#0E5A60,stroke-width:2px,color:#FFFFFF
  classDef ext fill:#57606A,stroke:#32383F,stroke-width:2px,color:#FFFFFF,stroke-dasharray:4 3
  classDef sec fill:#FFEBE9,stroke:#CF222E,stroke-width:2px,color:#82071E
  style HOST fill:transparent,stroke:#8C959F,stroke-width:1px,stroke-dasharray:6 4
  style APPS fill:transparent,stroke:#8C959F,stroke-width:1px,stroke-dasharray:6 4
  style PLATFORM fill:transparent,stroke:#8C959F,stroke-width:1px,stroke-dasharray:6 4
  style COREONLY fill:transparent,stroke:#8C959F,stroke-width:1px,stroke-dasharray:6 4
  style VOLS fill:transparent,stroke:#8C959F,stroke-width:1px,stroke-dasharray:6 4
  style LEGEND fill:transparent,stroke:#8C959F,stroke-width:1px,stroke-dasharray:6 4
```

| Profile | Services | Use it for |
| --- | --- | --- |
| `instabox` | postgres, mlflow, portkey, agent, ui (about 4.5 GB of limits) | `make quickstart-docker`, CI `stack-e2e`, 8 GB VMs |
| `core` | postgres, mlflow, portkey, unitycatalog, objectstore | The full local stack (`make up`), with the agent native or via `app` |
| `app` | agent, ui | Adding the containerised agent to `core` (`make up-app`) |

Every service has memory and CPU limits, log rotation and `no-new-privileges`, and every service in the `instabox` profile has a healthcheck. The agent and UI share one multi-stage image that runs as a non-root user and ships without pip.

## SOLID, principle by principle

**Single responsibility.** Each class has one reason to change: `SqlCompiler` resolves table names and transpiles SQL; `FactFetcher` turns query rows into `Fact` objects; `DeckNodes` holds one method per graph step; `DeckService` holds the use cases (start, decide, get); `PptxRenderer` only renders; the numeric-integrity rules are pure functions in `domain/integrity.py`.

**Open/closed.** Behaviour is extended without editing the core. The bare-number guardrail is a decorator around any `LLMGateway`, and `UnityCatalogOssCatalog` is a decorator around any `Catalog`. A new backend means a new adapter plus one factory in `bootstrap.py`; nothing in `domain`, `ports` or `application` changes.

**Liskov substitution.** Local and Databricks adapters satisfy the same `Protocol` with the same error contract: access problems raise `AccessDenied`, bad credentials raise `AuthenticationError`. `tests/contract/` runs the same behavioural assertions against every offline-constructible adapter of a port, so the application has no branches by environment. Every domain error carries a stable `code`, `category`, `status_code` and `retryable` flag, and the API maps errors only from those attributes.

**Interface segregation.** Eight small ports, not one "platform" object. The renderer knows nothing about SQL, the data source knows nothing about LLMs, and `StateStore` exposes only `checkpointer()` and `close()`.

**Dependency inversion.** The application depends on abstractions in `decksmith.ports`. Concrete classes are created in one place:

```mermaid
%% diagram: composition-root
%% caption: Settings choose one adapter per port; bootstrap is the only place concrete classes are built.
flowchart LR
  CFG("Settings<br/>DECKSMITH_* environment, validated at start-up"):::sec
  REG("Adapter registries<br/>one factory per adapter"):::port
  BOOT("bootstrap.build_container<br/>composition root"):::app
  C("Container<br/>DeckService · identity · LLM · state store"):::core
  CFG -->|selects| BOOT
  REG -->|factories| BOOT
  BOOT -->|builds| C
  classDef ui fill:#8250DF,stroke:#6639BA,stroke-width:2px,color:#FFFFFF
  classDef app fill:#0969DA,stroke:#0550AE,stroke-width:2px,color:#FFFFFF
  classDef core fill:#1A7F37,stroke:#116329,stroke-width:2px,color:#FFFFFF
  classDef port fill:#FFF8C5,stroke:#9A6700,stroke-width:2px,color:#3B2300
  classDef local fill:#DDF4FF,stroke:#0969DA,stroke-width:2px,color:#0A3069
  classDef dbx fill:#FFF1E5,stroke:#BC4C00,stroke-width:2px,color:#762C00
  classDef store fill:#EAEEF2,stroke:#57606A,stroke-width:2px,color:#24292F
  classDef llm fill:#BF3989,stroke:#99286E,stroke-width:2px,color:#FFFFFF
  classDef obs fill:#1B7C83,stroke:#0E5A60,stroke-width:2px,color:#FFFFFF
  classDef ext fill:#57606A,stroke:#32383F,stroke-width:2px,color:#FFFFFF,stroke-dasharray:4 3
  classDef sec fill:#FFEBE9,stroke:#CF222E,stroke-width:2px,color:#82071E
```

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

The diagrams are Mermaid, so GitHub renders them natively in both themes. Keep three rules:

- Use only the classes in the [colour key](#colour-key), copied verbatim from `PALETTE` in [`scripts/diagrams.py`](scripts/diagrams.py).
- Don't add a `%%{init}%%` theme; it would break dark mode.
- Give each diagram a `%% diagram: <name>` line and a `%% caption:` line.

`make diagrams` checks the palette and renders every diagram with mermaid-cli in the default and dark themes; it needs Node.js for `npx`, or `MMDC` pointing at an installed `mmdc`. To preview one diagram as PNGs, run `python scripts/diagrams.py --png out/diagrams --only hexagonal`.
