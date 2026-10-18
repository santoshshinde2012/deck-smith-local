# Decision records

Each record is short: the context, the decision, and the consequences.

## D1. Ports and adapters with a single composition root

- **Context.** The same agent must run offline in CI, on a laptop stack, and on Databricks.
- **Decision.** The domain and application depend only on eight `Protocol` ports. Adapters are built in `bootstrap.py`, and settings choose them.
- **Consequences.** Settings select infrastructure adapters; workspace resources, authentication, managed services and deployment compatibility still need separate validation. An architecture test enforces the dependency rule.

## D2. LangGraph with a human approval interrupt

- **Context.** Fetching data before a person agrees the storyline wastes queries and trust.
- **Decision.** The graph pauses after planning, using `interrupt`. Approve, edit or reject resumes it from a checkpoint (Postgres locally, Lakebase on Databricks).
- **Consequences.** Runs survive restarts. Edits loop back to the planner.

## D3. Approved SQL templates; the LLM never writes SQL

- **Context.** Generated SQL is hard to govern and to test.
- **Decision.** The planner chooses a template ID and gives parameters as strings. Parameters are validated against each template's types and patterns. Templates are written in Databricks SQL, and sqlglot transpiles them for DuckDB.
- **Consequences.** A new question needs a new template, which is reviewed like code.

## D4. Numbers only through facts

- **Context.** LLMs misquote numbers.
- **Decision.** Only the data-fetch step creates facts with provenance. The writer refers to them as `{{fact:fN}}`. A gateway guardrail (status 446) and a deterministic check reject bare digits. The writer gets at most three attempts.
- **Consequences.** Numeric metrics reference facts with query, table and execution-time provenance. Narrative correctness and source freshness require separate review.

## D5. Deterministic python-pptx renderer

- **Context.** Decks must be editable and reproducible.
- **Decision.** The renderer draws native charts and text from a validated DeckSpec. It chooses layouts by name and puts provenance in the speaker notes.
- **Consequences.** The same spec gives the same slide XML (a content hash is checked in tests).

## D6. Identity flows to the data

- **Context.** Users must see only their own data.
- **Decision.** Queries run as the caller: an on-behalf-of token on Databricks, per-user views locally. The principal travels in a `ContextVar`, never in checkpointed state.
- **Consequences.** A user with no access gets a clear refusal. Credentials stay outside graph state and traced model inputs. Authentication precedes the automatically traced ResponsesAgent method, and credential-bearing model inputs are rejected at its outer boundary.

## D7. One LLM gateway

- **Context.** Model choice, fallbacks, budgets and guardrails should not live in agent code.
- **Decision.** All model calls go through Portkey (the OSS gateway locally), with a config for each tier: small for intake and planning, strong for writing.
- **Consequences.** Models can change without code changes. The fake LLM implements the same port for CI.

## D8. MLflow 3 for tracing and evaluation

- **Decision.** There is one span per node, and a golden set is scored with deterministic scorers through `mlflow.genai.evaluate`.
- **Consequences.** Regressions in integrity, sources or slide count fail the evaluation.

## D9. Contract tests per port, and a coverage gate

- **Context.** Liskov substitution only holds if every adapter of a port behaves the same.
- **Decision.** `tests/contract/` runs one set of assertions against every offline-constructible adapter of each port. CI fails below 90% branch coverage. The interface, UI and publisher modules are excluded, because they need a browser or live services.
- **Consequences.** A new adapter is added to its contract fixture. A coverage drop fails the PR.

## D10. Error taxonomy and structured logs

- **Context.** Clients and operators need stable, machine-readable failures and correlated logs.
- **Decision.** Every error carries `code`, `category`, `status_code` and `retryable` (see `docs/errors.md`). The API maps errors only from these attributes. Logs are JSON lines from the standard library, with `run_id` bound by a `ContextVar`. Application JSON logs omit tokens, prompts and row data. MLflow agent traces intentionally contain credential-free requests and outputs, including facts; access to the tracking destination must match that data. Regression tests verify that dummy credentials do not enter stored traces.
- **Consequences.** New errors need no interface change. Logs can be shipped as they are to any JSON log store.

## D11. Fail-fast configuration

- **Decision.** `Settings` (pydantic-settings) validates adapter combinations at start-up. For example, the Unity Catalog adapter requires the Databricks data source, a JWT secret must be at least 32 characters, and the Databricks host must use HTTPS.
- **Consequences.** A misconfiguration fails when the process starts, not halfway through a run.

## D12. Locked dependencies and supply-chain checks

- **Decision.**
  - `uv.lock` pins every transitive dependency. CI and the container image install with `uv sync --locked`.
  - Dependabot updates uv, GitHub Actions, Docker and Compose dependencies.
  - CodeQL scans Python and workflows.
  - Images are linted by hadolint, scanned by trivy (failing on fixable HIGH and CRITICAL findings) and get a CycloneDX SBOM.
  - pip-audit checks the lock.
  - Containers run as non-root users with `no-new-privileges`, and every service has a healthcheck and a memory limit.
- **Consequences.** Builds are reproducible. Vulnerable dependencies surface as PRs or failed checks.

## D13. Semantic versioning with release-please

- **Decision.** Commits follow Conventional Commits. release-please maintains a release PR that bumps the version and CHANGELOG. Merging it tags `vX.Y.Z` and attaches the wheel, sdist and SBOM to the GitHub release.
- **Consequences.** Version numbers follow the change type. No release is created by hand.

## D14. A lean profile for 8 GB cloud VMs (InstaBox)

- **Context.** Contributors without a 16 GB Mac, and CI, need a real end-to-end run on a small VM.
- **Decision.**
  - The `instabox` Compose profile runs Postgres, MLflow, Portkey, the agent API and the UI, about 4.5 GB of memory limits in total; MLflow alone peaks around 1.6 GB at start-up. It leaves out Unity Catalog OSS, the object store and Ollama.
  - It uses the fake LLM by default. A remote model is opt-in through Portkey, with keys kept in the InstaBox vault.
  - `scripts/instabox/bootstrap.sh` runs headlessly and writes a Markdown summary and JUnit XML.
  - The same profile runs in CI (`stack-e2e`). A manual workflow provisions a real InstaBox VM, using the `INSTABOX_API_KEY` repo secret.
- **Consequences.** The end-to-end path is tested on every PR, and on demand on a fresh VM.
