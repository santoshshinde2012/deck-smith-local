# Changelog

All notable changes are listed here. The format follows Keep a Changelog, and versions follow SemVer.

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
