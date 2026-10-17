# Portkey gateway configs (examples)

These files are **examples**. Each one tries a local Ollama model first and falls back to Amazon Bedrock in `eu-central-1`.

The Ollama model names, and the Bedrock IDs (`eu.anthropic.claude-…`), are placeholders. Replace them with models you have pulled or have access to. JSON cannot carry comments, so this note marks them instead.

The agent sends the file for each tier inline, in the `x-portkey-config` header. The open-source gateway has no stored configs, so it needs the config in the request.
