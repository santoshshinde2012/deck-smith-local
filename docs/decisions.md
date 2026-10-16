# Decision records

Each record is short: the context, the decision, and the consequences.

## D1. Ports and adapters with a single composition root

- **Context.** The same agent must run offline in CI, on a laptop stack, and on Databricks.
- **Decision.** The domain and application depend only on eight `Protocol` ports. Adapters are built in `bootstrap.py`, and settings choose them.
- **Consequences.** Moving between environments changes configuration, not code. An architecture test enforces the dependency rule.

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
- **Consequences.** Every number on a slide can be traced to a query, a table and a time.

## D5. Deterministic python-pptx renderer

- **Context.** Decks must be editable and reproducible.
- **Decision.** The renderer draws native charts and text from a validated DeckSpec. It chooses layouts by name and puts provenance in the speaker notes.
- **Consequences.** The same spec gives the same slide XML (a content hash is checked in tests).

## D6. Identity flows to the data

- **Context.** Users must see only their own data.
- **Decision.** Queries run as the caller: an on-behalf-of token on Databricks, per-user views locally. The principal travels in a `ContextVar`, never in checkpointed state.
- **Consequences.** A user with no access gets a clear refusal. Tokens are never persisted.

## D7. One LLM gateway

- **Context.** Model choice, fallbacks, budgets and guardrails should not live in agent code.
- **Decision.** All model calls go through Portkey (the OSS gateway locally), with a config for each tier: small for intake and planning, strong for writing.
- **Consequences.** Models can change without code changes. The fake LLM implements the same port for CI.

## D8. MLflow 3 for tracing and evaluation

- **Decision.** There is one span per node, and a golden set is scored with deterministic scorers through `mlflow.genai.evaluate`.
- **Consequences.** Regressions in integrity, sources or slide count fail the evaluation.
