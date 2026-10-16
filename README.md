# deck-smith-local

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

DeckSmith is an AI agent that builds PowerPoint decks from governed data. This repository runs it end to end on a laptop, on a local stack shaped like Databricks, using ports and adapters (SOLID).

> **Status:** the full implementation, documentation and CI are in [pull request #1](https://github.com/santoshshinde2012/deck-smith-local/pull/1), which is under review. That PR covers the agent, the renderer, seed data, evaluation, Docker Compose, tests, architecture and decision records. Its branch README has the full quickstart.

## What this is, and what it is not

- **It is** a runnable reference: a LangGraph agent with human approval, numbers only from approved SQL, and native `.pptx` output. Everything runs offline in CI with a fake LLM.
- **It is not** a hosted product, a security boundary, or verified against a live Databricks workspace.

## Quickstart (from the PR branch)

```bash
git clone https://github.com/santoshshinde2012/deck-smith-local && cd deck-smith-local
git switch feat/core-local-stack
python3 -m venv .venv && make install && make seed && make test && make demo
```

All data is synthetic. Licensed under [MIT](LICENSE).
