#!/usr/bin/env bash
# Drive the running API end to end: create a run, approve it, download the deck, check refusals.
# Usage: scripts/smoke_api.sh [base_url]   (default http://localhost:8000). Exits non-zero on any failure.
set -euo pipefail
BASE="${1:-http://localhost:8000}"
REQ='{"request":"Build the Q3 2026 customer retention review for the exec team"}'
json() { python3 -c "import sys,json; print(json.load(sys.stdin)$1)"; }
call() { curl -fsS -H "Authorization: Bearer $1" -H 'Content-Type: application/json' "${@:2}"; }

curl -fsS "$BASE/healthz" >/dev/null
run_id=$(call bob-token -X POST "$BASE/v1/decks" -d "$REQ" | json '["run_id"]')
status=$(call bob-token -X POST "$BASE/v1/decks/$run_id/decision" -d '{"action":"approve"}' | json '["status"]')
[ "$status" = "done" ] || { echo "bob: expected done, got $status" >&2; exit 1; }
mkdir -p out && call bob-token -o out/smoke-deck.pptx "$BASE/v1/decks/$run_id/file"
head -c 2 out/smoke-deck.pptx | grep -q PK || { echo "download is not a pptx" >&2; exit 1; }

carol=$(call carol-token -X POST "$BASE/v1/decks" -d "$REQ" | json '["run_id"]')
cstatus=$(call carol-token -X POST "$BASE/v1/decks/$carol/decision" -d '{"action":"approve"}' | json '["status"]')
[ "$cstatus" = "no_data" ] || { echo "carol: expected no_data, got $cstatus" >&2; exit 1; }
code=$(curl -s -o /dev/null -w '%{http_code}' -H 'Authorization: Bearer alice-token' "$BASE/v1/decks/$run_id")
[ "$code" = "404" ] || { echo "alice reading bob's run: expected 404, got $code" >&2; exit 1; }
code=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$BASE/v1/decks" -H 'Content-Type: application/json' -d "$REQ")
[ "$code" = "401" ] || { echo "anonymous: expected 401, got $code" >&2; exit 1; }
echo "smoke ok: bob deck $(wc -c < out/smoke-deck.pptx) bytes (run $run_id), carol refused, isolation and auth enforced"
