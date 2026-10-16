#!/usr/bin/env bash
# End-to-end run of deck-smith-local on a fresh InstaBox VM (4 vCPU, 8 GB, x86_64), headless.
#
#   curl -fsSL https://raw.githubusercontent.com/santoshshinde2012/deck-smith-local/main/scripts/instabox/bootstrap.sh \
#     | DECKSMITH_REF=main bash
#
# Steps: Docker (installed if missing, data-root moved to /data), clone, install (uv, locked), seed,
# lean compose profile, offline test suite with coverage, live-stack e2e, API smoke test, demo.
# Writes out/instabox-summary.md and out/e2e-junit.xml and prints the summary. Exits non-zero on failure.
# Needs no credentials: the fake LLM is used unless DECKSMITH_LLM is set in the environment.
set -Eeuo pipefail

REPO_URL="${DECKSMITH_REPO:-https://github.com/santoshshinde2012/deck-smith-local.git}"
REF="${DECKSMITH_REF:-main}"
# InstaBox keeps home and the workspace on the 20 GB /data disk (/data/workspace is user-writable).
if [ -n "${DECKSMITH_WORKDIR:-}" ]; then WORK="$DECKSMITH_WORKDIR"
elif [ -w /data/workspace ]; then WORK=/data/workspace
else WORK="$HOME/work"; fi
DIR="$WORK/deck-smith-local"
SUDO=""; [ "$(id -u)" -eq 0 ] || SUDO="sudo"

declare -a STEPS=()
started_all=$(date +%s)
step() { # name, command...
  local name="$1"; shift
  local t0; t0=$(date +%s)
  echo "::: $name"
  if "$@"; then STEPS+=("| $name | ok | $(( $(date +%s) - t0 ))s |")
  else local rc=$?; STEPS+=("| $name | FAILED ($rc) | $(( $(date +%s) - t0 ))s |"); summary; exit "$rc"; fi
}

ensure_tools() {
  local missing=()
  for t in git make curl; do command -v "$t" >/dev/null || missing+=("$t"); done
  python3 -c "import venv, ensurepip" 2>/dev/null || missing+=(python3-venv)
  if [ ${#missing[@]} -gt 0 ]; then $SUDO env DEBIAN_FRONTEND=noninteractive apt-get update -qq && $SUDO env DEBIAN_FRONTEND=noninteractive apt-get install -y -qq "${missing[@]}"; fi
  command -v uv >/dev/null || { curl -LsSf https://astral.sh/uv/install.sh | sh; export PATH="$HOME/.local/bin:$PATH"; }
}

ensure_docker() {
  if ! command -v docker >/dev/null; then curl -fsSL https://get.docker.com | $SUDO sh; fi
  # The system disk is small; keep images and volumes on the 20 GB /data disk.
  if [ -d /data ] && [ "$(docker info --format '{{.DockerRootDir}}' 2>/dev/null || $SUDO docker info --format '{{.DockerRootDir}}')" != "/data/docker" ]; then
    $SUDO mkdir -p /data/docker /etc/docker
    echo '{ "data-root": "/data/docker" }' | $SUDO tee /etc/docker/daemon.json >/dev/null
    $SUDO systemctl restart docker 2>/dev/null || $SUDO service docker restart
  fi
  docker info >/dev/null 2>&1 || { $SUDO usermod -aG docker "$USER" 2>/dev/null || true; DOCKER="$SUDO docker"; }
  ${DOCKER:-docker} compose version >/dev/null
}

checkout() {
  mkdir -p "$WORK"
  if [ -d "$DIR/.git" ]; then git -C "$DIR" fetch -q origin "$REF" && git -C "$DIR" checkout -q FETCH_HEAD
  else git clone -q "$REPO_URL" "$DIR" && git -C "$DIR" checkout -q "$REF"; fi
  cd "$DIR"
}

install() { python3 -m venv .venv && make install; }
configure() { [ -f .env ] || cp .env.instabox .env; }
stack() { make up-instabox COMPOSE="${DOCKER:-docker} compose"; }

summary() {
  cd "$DIR" 2>/dev/null || return 0
  mkdir -p out
  {
    echo "# deck-smith-local on InstaBox"
    echo
    echo "| Item | Value |"
    echo "| --- | --- |"
    echo "| Commit | $(git rev-parse --short HEAD 2>/dev/null) ($REF) |"
    echo "| Machine | $(uname -m), $(nproc) vCPU, $(free -g | awk '/Mem:/ {print $2}') GiB RAM, kernel $(uname -r) |"
    echo "| Docker | $(${DOCKER:-docker} version --format '{{.Server.Version}}' 2>/dev/null), root $(${DOCKER:-docker} info --format '{{.DockerRootDir}}' 2>/dev/null) |"
    echo "| Python | $(.venv/bin/python --version 2>&1) |"
    echo "| Total time | $(( $(date +%s) - started_all ))s |"
    echo
    echo "| Step | Result | Time |"
    echo "| --- | --- | --- |"
    printf '%s\n' "${STEPS[@]}"
    echo
    echo "## Containers"
    echo
    echo '```text'
    ${DOCKER:-docker} stats --no-stream --format 'table {{.Name}}\t{{.MemUsage}}\t{{.CPUPerc}}' 2>/dev/null || true
    echo '```'
    [ -f out/e2e-junit.xml ] && python3 - <<'PY'
import xml.etree.ElementTree as ET
s = ET.parse("out/e2e-junit.xml").getroot()
s = s if s.tag == "testsuite" else s[0]
print(f"\nLive-stack e2e: {s.get('tests')} tests, {s.get('failures')} failures, {s.get('errors')} errors, {s.get('skipped')} skipped")
PY
  } > out/instabox-summary.md
  cat out/instabox-summary.md
}

step "tools" ensure_tools
step "docker" ensure_docker
step "checkout" checkout
step "install (uv, locked)" install
step "configure (.env.instabox)" configure
step "seed" make seed
step "compose up (instabox profile)" stack
step "offline tests + coverage gate" make test
step "live-stack e2e" make e2e-stack
step "API smoke (containerised agent)" make smoke-api
step "demo (Postgres + MLflow)" make demo
summary
