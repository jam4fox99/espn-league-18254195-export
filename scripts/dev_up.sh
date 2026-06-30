#!/usr/bin/env bash
# Launch the MyGM app locally with a fully seeded demo league.
#
#   bash scripts/dev_up.sh
#
# Starts the FastAPI backend (seeded with the league_18254195 fixture snapshot) on
# :8000 and the Next.js web app on :3000, waits for both to be healthy, then blocks.
# Press Ctrl-C to stop both. All API data is in memory and reseeded on each launch.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

API_PORT="${API_PORT:-8000}"
WEB_PORT="${WEB_PORT:-3000}"
API_BASE="http://127.0.0.1:${API_PORT}"
WEB_BASE="http://127.0.0.1:${WEB_PORT}"

api_pid=""
web_pid=""
cleanup() {
  [ -n "$web_pid" ] && kill "$web_pid" >/dev/null 2>&1 || true
  [ -n "$api_pid" ] && kill "$api_pid" >/dev/null 2>&1 || true
}
trap cleanup INT TERM EXIT

wait_for_url() {
  local url="$1" label="$2"
  for _ in $(seq 1 120); do
    if [ "$(curl -sS -o /dev/null -w '%{http_code}' "$url" 2>/dev/null || true)" = "200" ]; then
      echo "  $label ready at $url"
      return 0
    fi
    sleep 1
  done
  echo "ERROR: $label did not become ready at $url" >&2
  exit 1
}

echo "Starting seeded API on ${API_BASE} ..."
( cd services/api && MYGM_DEV_PORT="${API_PORT}" uv run python ../../scripts/dev_seed_and_serve.py ) &
api_pid="$!"
wait_for_url "${API_BASE}/healthz" "api"

echo "Starting web on ${WEB_BASE} ..."
( cd apps/web && NEXT_PUBLIC_API_BASE_URL="${API_BASE}" npm run dev -- --port "${WEB_PORT}" ) &
web_pid="$!"
wait_for_url "${WEB_BASE}" "web"

cat <<EOF

  MyGM is running.
    Web:  ${WEB_BASE}            (click "View dashboard")
    API:  ${API_BASE}/docs       (OpenAPI explorer)

  The demo league is seeded at:
    ${WEB_BASE}/leagues/11111111-1111-4111-8111-111111111111

  Press Ctrl-C to stop both services.
EOF

wait
