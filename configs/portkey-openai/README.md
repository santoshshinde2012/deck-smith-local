# Portkey configs for a hosted provider, using your own key

These configs route both tiers to OpenAI through the local Portkey OSS gateway. No key is stored here: the agent sends `DECKSMITH_LLM_API_KEY` as the bearer token, and the gateway forwards it to the provider, because these targets have no `api_key` of their own.

```bash
export DECKSMITH_LLM=portkey DECKSMITH_PORTKEY_CONFIG_DIR=configs/portkey-openai
export DECKSMITH_LLM_API_KEY=sk-...     # your key, in the environment only; never commit it
make quickstart-offline                 # or: make quickstart (Docker); needs the gateway on :8787
```

The model names (`gpt-4o-mini`, `gpt-4o`) are examples. Another Portkey provider works the same way: change `provider` and `model`. Real models are not deterministic. The guardrail and the numeric-integrity checks still apply, but a run can fail QA, which the fake LLM never does.
