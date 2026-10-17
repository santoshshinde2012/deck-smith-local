#!/usr/bin/env bash
# Try DeckSmith in one command: install, seed, start the API and UI, produce decks, print where they are.
#
#   scripts/quickstart.sh [auto|docker|offline]      (or: make quickstart / make quickstart-offline)
#
# docker  : the lean compose stack (Postgres checkpoints, MLflow traces, Portkey, agent API + UI containers)
# offline : no Docker at all; fake LLM, DuckDB and in-memory state; API and UI run natively
# auto    : docker if a Docker daemon is reachable, else offline (default)
#
# Real LLM (optional): export DECKSMITH_LLM=portkey DECKSMITH_PORTKEY_CONFIG_DIR=configs/portkey-openai
# DECKSMITH_LLM_API_KEY=<your key> first. See configs/portkey-openai/README.md.
# Stop everything with: make stop
set -euo pipefail
cd "$(dirname "$0")/.."
MODE="${1:-auto}"
OUT=out
mkdir -p "$OUT/logs"
say() { printf '\n\033[1m== %s\033[0m\n' "$*"; }

if [ "$MODE" = auto ]; then
  if docker info >/dev/null 2>&1; then MODE=docker; else MODE=offline; fi
fi
case "$MODE" in docker|offline) ;; *) echo "usage: $0 [auto|docker|offline]" >&2; exit 2 ;; esac
say "DeckSmith quickstart ($MODE)"

say "1/4 install (locked with uv when available)"
command -v uv >/dev/null 2>&1 || [ -x .venv/bin/python ] || python3 -m venv .venv
make -s install >"$OUT/logs/install.log" 2>&1 || { tail -20 "$OUT/logs/install.log"; exit 1; }

say "2/4 seed synthetic data (seed 42, ~8,000 subscriptions; alice, bob, carol views)"
make -s seed

say "3/4 start the services"
if [ "$MODE" = docker ]; then
  [ -f .env ] || cp .env.instabox .env
  make -s up-instabox
  export DECKSMITH_STATE_STORE=postgres DECKSMITH_TRACER=mlflow
else
  # Offline: ignore any .env that points at services; keep the user's LLM choice if they set one.
  export DECKSMITH_STATE_STORE=memory DECKSMITH_TRACER=noop DECKSMITH_DATA_SOURCE=duckdb DECKSMITH_CATALOG=per_user_views
  make -s stop-native >/dev/null 2>&1 || true
  nohup .venv/bin/python -m uvicorn --factory decksmith.interfaces.api:app --port 8000 \
    >"$OUT/logs/api.log" 2>&1 < /dev/null & echo $! >> "$OUT/.quickstart.pids"
  DECKSMITH_API_URL=http://localhost:8000 nohup .venv/bin/python -m streamlit run src/decksmith/interfaces/ui.py \
    --server.port 8501 --server.headless true >"$OUT/logs/ui.log" 2>&1 < /dev/null & echo $! >> "$OUT/.quickstart.pids"
fi
for url in http://localhost:8000/healthz http://localhost:8501/_stcore/health; do
  for _ in $(seq 1 60); do curl -fs "$url" >/dev/null 2>&1 && break; sleep 2; done
  curl -fs "$url" >/dev/null || { echo "not responding: $url (see $OUT/logs or docker compose logs)" >&2; exit 1; }
done

say "4/4 build decks for bob, alice and carol (scripts/demo.py)"
DECKSMITH_LOG_LEVEL=WARNING .venv/bin/python scripts/demo.py | tee "$OUT/logs/demo.log"

say "Done"
echo "Generated decks (editable PowerPoint):"
# shellcheck disable=SC2012  # plain file names we generate; newest first
ls -1t "$OUT"/*.pptx 2>/dev/null | head -5 | sed 's/^/  /'
cat <<MSG

  UI       http://localhost:8501   act as bob, then Draft outline → Approve → Download deck
  API      http://localhost:8000/docs
MSG
[ "$MODE" = docker ] && echo "  MLflow   http://localhost:5001   (traces for every step)"
cat <<MSG

  Check the whole use case:   make e2e-usecase
  Stop everything:            make stop
MSG
if [ -z "${CI:-}" ] && [ "${QUICKSTART_OPEN:-1}" = 1 ]; then
  if command -v open >/dev/null 2>&1; then open http://localhost:8501 || true
  elif [ -n "${DISPLAY:-}" ] && command -v xdg-open >/dev/null 2>&1; then xdg-open http://localhost:8501 >/dev/null 2>&1 || true
  fi
fi
