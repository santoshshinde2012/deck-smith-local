# Changelog

<!-- Release Please generates list markers and spacing independently of historical entries. -->
<!-- markdownlint-disable-file MD004 MD012 -->

All notable changes are listed here. The format follows Keep a Changelog, and versions follow SemVer.

## [0.2.0](https://github.com/santoshshinde2012/deck-smith-local/compare/v0.1.1...v0.2.0) (2026-10-17)


### Features

* best-practice hardening and InstaBox e2e (wip) ([8c331a1](https://github.com/santoshshinde2012/deck-smith-local/commit/8c331a1f3c0820f9d69fd98e3c11f5ed46529a19))
* CI/CodeQL/supply-chain/release workflows, devcontainer, InstaBox workflow and docs, ADRs D9-D14; fix mlflow OOM on 8 GB VMs and agent out volume ([5b92524](https://github.com/santoshshinde2012/deck-smith-local/commit/5b9252458c83a98eef106c44152737d587c5f839))
* DeckSmith local stack, LD0-LD1 (ports and adapters, LangGraph agent, renderer, seed, evals, compose, CI) ([d59fdb9](https://github.com/santoshshinde2012/deck-smith-local/commit/d59fdb9772ec20c4fc044f5305cca7d74f9b6768))
* end-to-end best practices and InstaBox e2e profile ([cbf922c](https://github.com/santoshshinde2012/deck-smith-local/commit/cbf922c4f581c970fa1be28c68eac10dcda6ad0a))
* try-it-in-5-minutes quickstart, scripted use case, grouped Dependabot, Postgres 18 and action bumps ([772ae20](https://github.com/santoshshinde2012/deck-smith-local/commit/772ae2015aa7bff091177b08b4a83b668c37f2bc))


### Bug Fixes

* **compose:** use the psycopg2 driver for the MLflow Postgres store ([eba40a7](https://github.com/santoshshinde2012/deck-smith-local/commit/eba40a7f740bb0708c1fb3c03c0f84139b3988b0))
* **devcontainer:** use the base image + uv-managed Python 3.12 (python image's stale yarn apt key broke docker-in-docker) ([1b6efc5](https://github.com/santoshshinde2012/deck-smith-local/commit/1b6efc565c452fe45465695caf850a88e0b801a0))
* **docker:** drop pip from runtime images to clear trivy HIGH findings; CodeQL Action v4 ([43216a6](https://github.com/santoshshinde2012/deck-smith-local/commit/43216a6bf095daeebde0b7089ae5ae24718e9f77))
* **docker:** drop pip from the agent and MLflow images (trivy HIGH) ([cf8025c](https://github.com/santoshshinde2012/deck-smith-local/commit/cf8025cdd920b3dc1ca1d8a92e33231267341976))
* **instabox:** move containerd root to /data too (Docker 29 image store filled the 16 GB system disk) ([b64d2c4](https://github.com/santoshshinde2012/deck-smith-local/commit/b64d2c45cad0e8ba6ce2d2e299955627fc141720))
* **instabox:** recreate a .venv whose interpreter is missing (e.g. created inside the devcontainer) ([e74e5f4](https://github.com/santoshshinde2012/deck-smith-local/commit/e74e5f4080fbc6262d13912d3cb7525b589149a1))
* **instabox:** use the user-writable /data/workspace ([41fca12](https://github.com/santoshshinde2012/deck-smith-local/commit/41fca12d0241a9eded45a646bf7ec5ca1f36fb63))
* pool Postgres checkpointer connections (thread-safe for mlflow evaluate); ci: audit the exported lock, bump trivy/hadolint actions ([baf139f](https://github.com/santoshshinde2012/deck-smith-local/commit/baf139fc097e71495d6769a4368a18e407b9fa1c))
* **quickstart:** list only this run's decks, labelled by user ([6d162cd](https://github.com/santoshshinde2012/deck-smith-local/commit/6d162cd0a593c3b3f0705820406e38a4bf0d42f4))
* real-LLM path and UI behind a proxy, found on a fresh InstaBox run ([c5daa68](https://github.com/santoshshinde2012/deck-smith-local/commit/c5daa68829960d12a933a53c8d6f2edd9c533614))
* untrack the .venv symlink; quiet apt in bootstrap ([fee8176](https://github.com/santoshshinde2012/deck-smith-local/commit/fee8176a40aaf86f2e27c1163b5951577b36ef2e))


### Documentation

* diagrams as white-background images, with a freshness check ([5bccb8b](https://github.com/santoshshinde2012/deck-smith-local/commit/5bccb8b92605944a4aada1c1753622a7cdb01ca2))
* fresh-clone quickstart and sample output deck ([1a3789a](https://github.com/santoshshinde2012/deck-smith-local/commit/1a3789ac908426858ea10524e40a8b1dc2b71ffb))
* InstaBox run evidence (asciinema cast, GIF, UI/MLflow/API/deck screenshots); single-PR branch notes ([ecb296e](https://github.com/santoshshinde2012/deck-smith-local/commit/ecb296eb537b380031a27a28741bc426dcb88d86))
* public-facing README and MIT licence on main ([4bb6fb3](https://github.com/santoshshinde2012/deck-smith-local/commit/4bb6fb3ea1ec659e805ff48ee7732d70343b493f))
* public-facing README on main ([76777a4](https://github.com/santoshshinde2012/deck-smith-local/commit/76777a4eb0af0570f755c4942c158a936872064d))
* README with architecture up front, and diagrams in one semantic palette ([b52a5b9](https://github.com/santoshshinde2012/deck-smith-local/commit/b52a5b9a840a689e5419a9f27b4860fe306661d6))
* **readme:** add end-to-end system architecture near the top ([4bc23d1](https://github.com/santoshshinde2012/deck-smith-local/commit/4bc23d115f3d0fbd2d1d972c33b60cece06cfd41))
* render diagrams to images on a white canvas ([fc9332e](https://github.com/santoshshinde2012/deck-smith-local/commit/fc9332e22599e4acd7f9068d0b4ba30323f913a0))
* rewrite README and architecture diagrams with one semantic palette ([52a57b6](https://github.com/santoshshinde2012/deck-smith-local/commit/52a57b62a914aad5cab0f9c6cb693096a7d805f3))

## [Unreleased]

### Added

- Contract tests for every port, and a 90% coverage gate.
- An error taxonomy (`docs/errors.md`), JSON logs carrying `run_id`, and start-up config validation.
- `uv.lock`, Dependabot, CodeQL, trivy, an SBOM, hadolint and pip-audit.
- Release automation with release-please.
- Non-root multi-stage images, plus healthchecks and resource limits in Compose.
- The `instabox` lean profile, `scripts/instabox/bootstrap.sh`, `scripts/smoke_api.sh`, the `instabox-e2e` workflow and the `stack-e2e` CI job.
- A devcontainer, ADRs D9–D14, and a README walkthrough and architecture diagram.
- "Try it in 5 minutes": `make quickstart` (Docker or offline; an optional real LLM through the Portkey gateway with your own `DECKSMITH_LLM_API_KEY`), `make e2e-usecase` (the 11-step use case, with a pass/fail table) and `make stop`.
- The Streamlit UI joins the `instabox` profile; CI gains a `quickstart-offline` job, and `stack-e2e` runs the use case.
- `configs/portkey-openai/`: example configs for a hosted provider, using the user's own key.
- InstaBox run evidence in `docs/evidence/`: an asciinema recording, a GIF, and screenshots of the UI, MLflow, the API docs and the deck.

### Changed

- CodeQL Action v3 → v4.39.0 (node24; v3 is deprecated in December 2026), pinned by SHA.
- Every GitHub Action is pinned to a full commit SHA, with the version in a comment. This clears CodeQL `actions/unpinned-tag` (alerts 6, 24–26, 199–201, 368, 369).
- Postgres 16 → 18. The data volume is now `pg18-data` and mounted at `/var/lib/postgresql`, because Postgres 18 keeps PGDATA in a versioned subdirectory. A local Postgres 16 volume (`pg-data`) is left untouched and unused; delete it with `docker volume rm decksmith-local_pg-data`.
- GitHub Actions: checkout v7, setup-uv v7, upload-artifact v7, release-please-action v5.
- Dependabot opens one grouped PR per ecosystem per month.
- mypy now checks `tests` as well as `src`, using the pydantic plugin.
- `decksmith.__version__` and the API version are read from the package metadata, so `pyproject.toml` is the single source.

### Deferred

- Python 3.14 base images (#5, #7). The MLflow image does not build: the pinned `psycopg2-binary` 2.9.10 has no 3.14 wheel. trivy also fails the 3.14 agent image on a fixable HIGH (msgpack 1.1.2, GHSA-6v7p-g79w-8964). Dependabot ignores `python >= 3.14` until the pins and the CI matrix move.

### Fixed

- The agent and MLflow images no longer ship pip. On `python:3.13-slim`, pip 26.2.1 bundles msgpack 1.1.2, urllib3 2.7.0 and setuptools 70.3.0, which trivy fails as fixable HIGH (GHSA-6v7p-g79w-8964, CVE-2026-97687, CVE-2026-97689, CVE-2025-47273). The latest pip still bundles them, so upgrading doesn't help. The runtime never uses pip.
- The Portkey adapter sends each config as one line; pretty-printed JSON was an illegal header value, so `DECKSMITH_LLM=portkey` failed before any call. Gateway failures now map to `upstream_unavailable` (503) instead of a bare 500, and the error text carries only the type and status.
- The UI behind a reverse proxy, such as `instabox port publish`, stayed blank because Streamlit rejected the WebSocket origin. `DECKSMITH_UI_PUBLIC_HOST` fixes it.
- The Postgres checkpointer uses a connection pool, so it is safe for threaded callers such as `mlflow.genai.evaluate`.
- MLflow gets 2 GiB and one worker; it was killed for running out of memory at 1 GiB on 8 GB VMs.
- The containerised agent writes decks to a named volume, because a bind mount was not writable by the non-root user on Linux.
- The InstaBox bootstrap moves containerd's image store to `/data`, because Docker 29 filled the 16 GB system disk.

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
