# Local environment and test plan

## Fidelity tiers

| Tier | What runs | Purpose |
| --- | --- | --- |
| L0 | Pure Python: schema, renderer, integrity checks | Fast unit loop |
| L1 | Full graph offline (fake LLM, DuckDB), plus the `core` compose profile | End-to-end on a laptop |
| L2 | L1 with real models through the gateway (Ollama or a cloud provider), synthetic data | Quality, cost and latency |
| L3 | Hybrid: the Databricks adapters against a workspace | Parity and real identity |
| L4 | Staging workspace with network and governance controls | Release readiness |

## Scenarios

| ID | Scenario | Tier | Passes when |
| --- | --- | --- | --- |
| E1 | DeckSpec schema and renderer golden output | L0 | Same spec and theme give the same slide XML; overflow is flagged; shapes stay on the slide |
| E2 | Numeric integrity | L0 | Every `{{fact}}` resolves; no bare digits; chart series match facts |
| E3 | Interrupt and resume across a restart | L1 | A run resumes from the checkpoint store |
| E4 | Request to SQL facts to DeckSpec to PPTX | L1 | Deck produced; all deterministic gates pass |
| E5 | Permission emulation | L1 | alice gets facts for her region only; carol gets a clean refusal |
| E6 | Gateway behaviour | L1 | Fallback works; the guardrail returns 446 on a bare digit |
| E7 | Golden-set evaluation | L2 | Deterministic scorers at 100% |
| E8 | Cost and latency | L2 | Tokens recorded per node |
| E9 | SQL templates on Databricks SQL | L3 | Same facts as local, within tolerance |
| E10 | Real row filters and on-behalf-of identity | L3 | Matches E5's expectations |
| E11 | Staging controls | L4 | Network, residency and budget checks pass |

The README records which scenarios run in CI.

## Phases

| Phase | Scope | Exit |
| --- | --- | --- |
| LD0 | Schema, renderer, integrity checks, fixtures | E1–E2 green in CI |
| LD1 | `core` compose profile, seed data, gateway, Postgres checkpoints, MLflow | E3–E6 green on a laptop (done in v0.1) |
| LD2 | Real models with synthetic data; golden set of ten | E7–E8 recorded |
| LD3 | Databricks adapters against a workspace | E9–E10 green |
| LD4 | Staging | E11 |

## Test users

| User | Access | Expected |
| --- | --- | --- |
| alice | Her region only | Deck with figures for her region |
| bob | All regions | Full deck |
| carol | None | Clear "no data visible to you" refusal |
