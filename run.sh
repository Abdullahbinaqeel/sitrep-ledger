#!/usr/bin/env bash
#
# One-command launcher for SitRep Ledger.
#
#   ./run.sh              Run the agent locally on http://localhost:9000
#   ./run.sh --tunnel     Also open a public tunnel and auto-set PUBLIC_URL
#                         (paste the printed https URL into the SitRep Studio)
#
# First run creates a venv and installs deps. Config comes from .env
# (copy .env.example -> .env and add your LLM_API_KEY first).
#
set -euo pipefail
cd "$(dirname "$0")"

PORT="${PORT:-9000}"
USE_TUNNEL=0
[ "${1:-}" = "--tunnel" ] && USE_TUNNEL=1

# ── 1. venv + deps ────────────────────────────────────────────────────
if [ ! -d .venv ]; then
  echo "▸ Creating virtualenv (.venv)…"
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
echo "▸ Installing dependencies…"
pip install -q -r requirements.txt

# ── 2. config (.env) ──────────────────────────────────────────────────
if [ ! -f .env ]; then
  echo "⚠  No .env found. Copying .env.example → .env — edit it to add your LLM_API_KEY."
  cp .env.example .env
fi
set -a; source .env; set +a

if [ -z "${LLM_API_KEY:-}" ] && [[ "${LLM_BASE_URL:-}" != *"localhost"* && "${LLM_BASE_URL:-}" != *"127.0.0.1"* ]]; then
  echo "⚠  LLM_API_KEY is empty but LLM_BASE_URL is a hosted provider — the agent will fail to generate."
  echo "   Add your key to .env, then re-run."
fi

# ── 3. optional public tunnel ─────────────────────────────────────────
TUNNEL_PID=""
cleanup() { [ -n "$TUNNEL_PID" ] && kill "$TUNNEL_PID" 2>/dev/null || true; }
trap cleanup EXIT INT TERM

if [ "$USE_TUNNEL" = "1" ]; then
  echo "▸ Opening public tunnel (localhost.run)…"
  LOG="$(mktemp)"
  ssh -o StrictHostKeyChecking=accept-new -o ServerAliveInterval=20 \
      -o ServerAliveCountMax=3 -o ExitOnForwardFailure=yes \
      -R "80:localhost:${PORT}" nokey@localhost.run > "$LOG" 2>&1 &
  TUNNEL_PID=$!
  PUBLIC=""
  for _ in $(seq 1 20); do
    PUBLIC="$(grep -Eo 'https://[a-z0-9]+\.lhr\.life' "$LOG" 2>/dev/null | head -1 || true)"
    [ -n "$PUBLIC" ] && break
    sleep 1
  done
  if [ -n "$PUBLIC" ]; then
    export PUBLIC_URL="$PUBLIC"
    echo "▸ Public URL: $PUBLIC_URL"
    echo "  → Paste this into the SitRep Studio 'Endpoint URL' field."
  else
    echo "⚠  Could not obtain a tunnel URL; continuing local-only. (Tunnels are flaky — deploy to Render for a stable URL.)"
  fi
fi

# ── 4. run ────────────────────────────────────────────────────────────
echo ""
echo "▸ SitRep Ledger on http://localhost:${PORT}"
echo "    POST /run  ·  POST /test  ·  GET /health  ·  GET /dashboard/{workspace}"
echo "    Dashboard: ${PUBLIC_URL:-http://localhost:$PORT}/dashboard/my-team"
echo "    Ctrl+C to stop."
echo ""
exec uvicorn app:app --host 0.0.0.0 --port "${PORT}"
