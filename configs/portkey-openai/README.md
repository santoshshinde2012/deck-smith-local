# Portkey configs for a hosted provider, using your own key

These configs route both tiers to OpenAI through the local Portkey OSS gateway. No key is stored here. Each target says `"api_key": "$DECKSMITH_LLM_API_KEY"`; the agent fills in your key from the environment in memory and sends it only to the local gateway, which calls the provider. It is never written to a file or logged. If the variable is unset, start-up fails with `configuration_error`.

```bash
export DECKSMITH_LLM=portkey DECKSMITH_PORTKEY_CONFIG_DIR=configs/portkey-openai
export DECKSMITH_LLM_API_KEY=sk-...     # your key, in the environment only; never commit it
make quickstart-offline                 # or: make quickstart (Docker); needs the gateway on :8787
```

The model names (`gpt-4o-mini`, `gpt-4o`) are examples. Another Portkey provider works the same way: change `provider` and `model`. Real models are not deterministic. The guardrail and the numeric-integrity checks still apply, but a run can fail QA, which the fake LLM never does.
