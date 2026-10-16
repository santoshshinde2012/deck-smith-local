# Changelog

All notable changes are listed here. The format follows Keep a Changelog, and versions follow SemVer.

## [Unreleased]

### Added

- Contract tests for every port, and a 90% coverage gate.
- An error taxonomy (`docs/errors.md`), JSON logs carrying `run_id`, and start-up config validation.
- `uv.lock`, Dependabot, CodeQL, trivy, an SBOM, hadolint and pip-audit.
- Release automation with release-please.
- Non-root multi-stage images, plus healthchecks and resource limits in Compose.
- The `instabox` lean profile, `scripts/instabox/bootstrap.sh`, `scripts/smoke_api.sh`, the `instabox-e2e` workflow and the `stack-e2e` CI job.
- A devcontainer, ADRs D9–D14, and a README walkthrough and architecture diagram.

## [0.1.1] - 2026-10-16

### Changed

- Prepared for public release:
  - MIT licence;
  - SECURITY.md, CODE_OF_CONDUCT.md, and issue and PR templates;
  - README badges, a "what this is / is not" section and a self-contained design summary;
  - design context made self-contained: `docs/decisions.md` and `docs/test-plan.md`;
  - Portkey model IDs marked as examples;
  - fresh-clone quickstart and a sample output deck in `docs/examples/`.

## [0.1.0] - 2026-10-16

### Added

- Ports and adapters core:
  - eight ports;
  - local adapters: fake LLM, Portkey OSS gateway, DuckDB, per-user-view catalog, UC OSS decorator, python-pptx renderer, memory and Postgres checkpoints, MLflow tracer, static and JWT identity;
  - Databricks adapters: SQL Statement API, Unity Catalog passthrough, Apps OBO identity.
- LangGraph agent:
  - intake, planner, human approval interrupt, data fetch, writer, deterministic check, render;
  - a bounded QA loop;
  - no-data refusal.
- Fact registry and DeckSpec schema, with numeric-integrity and chart-consistency checks. The bare-number guardrail returns status 446.
- Five SQL templates in Databricks SQL, transpiled to DuckDB with sqlglot.
- Seed generator (synthetic, seed 42), with per-user views for alice, bob and carol, and a UC OSS and S3 publisher.
- FastAPI (`/v1/decks`, `/responses`), the MLflow `ResponsesAgent` wrapper and a Streamlit UI.
- Evaluation: a golden set of ten prompts, deterministic scorers, and an `mlflow.genai.evaluate` harness.
- Tests: unit, architecture (dependency rule), integration, and e2e scenarios E1–E8 offline. E9–E11 are skipped with reasons.
- Docker Compose `core` and `app` profiles, a Makefile, GitHub Actions CI and pre-commit.
