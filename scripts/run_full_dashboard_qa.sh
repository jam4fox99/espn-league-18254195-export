#!/usr/bin/env bash
set -euo pipefail
. scripts/harness_lib.sh

target_evidence_dir=".omo/evidence/task-12-mygm-espn-full-dashboard/full-dashboard"
while test "$#" -gt 0; do
  case "$1" in
    --evidence-dir)
      shift
      target_evidence_dir="$1"
      ;;
    *)
      fail "UNKNOWN_ARGUMENT: $1"
      ;;
  esac
  shift
done

mkdir -p "$target_evidence_dir"
target_evidence_dir_abs="$(cd "$target_evidence_dir" && pwd)"
exec > >(tee "$target_evidence_dir/run-full-dashboard-qa.txt") 2>&1

api_port="${API_PORT:-8000}"
web_port="${WEB_PORT:-3000}"
api_base="${API_BASE:-http://127.0.0.1:${api_port}}"
web_base="${WEB_BASE:-http://127.0.0.1:${web_port}}"
fixture_root="${MYGM_FIXTURE_ROOT:-}"
api_pid=""
web_pid=""

cleanup() {
  if test -n "$web_pid"; then
    kill "$web_pid" >/dev/null 2>&1 || true
  fi
  if test -n "$api_pid"; then
    kill "$api_pid" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

if test -z "$fixture_root"; then
  fixture_root="$(find tests/fixtures/espn -mindepth 1 -maxdepth 1 -type d -name 'league_*' 2>/dev/null | sort | head -n 1 || true)"
fi
test -n "$fixture_root" || fail "MYGM_FIXTURE_ROOT_REQUIRED"
require_dir "$fixture_root"
require_file "scripts/api_snapshot_smoke.py"
require_file "apps/web/e2e/full-dashboard-flow.spec.ts"

wait_for_url() {
  url="$1"
  label="$2"
  for _ in $(seq 1 120); do
    code="$(curl -sS -o /tmp/mygm-dashboard-qa.out -w '%{http_code}' "$url" || true)"
    if test "$code" = "200"; then
      printf '%s\n' "$label ready at $url"
      return 0
    fi
    sleep 1
  done
  fail "MISSING_SURFACE: $label did not become ready at $url"
}

if curl -sS -o /tmp/mygm-api-existing.out "$api_base/healthz" >/dev/null 2>&1; then
  printf '%s\n' "api already ready at $api_base"
else
  run_step "start api" bash -lc "cd services/api && MYGM_CREDENTIAL_KEY_V1='AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=' MYGM_CREDENTIAL_KEY_ID='qa-key' MYGM_ALLOWED_ORIGINS='[\"http://127.0.0.1:${web_port}\"]' uv run uvicorn mygm_api.main:app --host 127.0.0.1 --port ${api_port}" &
  api_pid="$!"
fi
wait_for_url "$api_base/healthz" "api"

if curl -sS -o /tmp/mygm-web-existing.out "$web_base" >/dev/null 2>&1; then
  printf '%s\n' "web already ready at $web_base"
else
  run_step "start web" bash -lc "cd apps/web && NEXT_PUBLIC_API_BASE_URL='${api_base}' npm run dev -- --port ${web_port}" &
  web_pid="$!"
fi
wait_for_url "$web_base" "web"

run_step "local health smoke" bash -lc "MYGM_EVIDENCE_DIR='${target_evidence_dir}' API_BASE='${api_base}' WEB_BASE='${web_base}' make local-health-smoke"
run_step "api core smoke" uv run --script scripts/api_snapshot_smoke.py --fixture-root "$fixture_root" --scenario core --evidence "$target_evidence_dir/api-core.txt"
run_step "api missing snapshot smoke" uv run --script scripts/api_snapshot_smoke.py --fixture-root "$fixture_root" --scenario missing-snapshot --evidence "$target_evidence_dir/api-missing-snapshot.txt"
run_step "api recompute smoke" uv run --script scripts/api_snapshot_smoke.py --fixture-root "$fixture_root" --scenario recompute --evidence "$target_evidence_dir/api-recompute.txt"
run_step "browser full dashboard flow" bash -lc "cd apps/web && MYGM_EVIDENCE_DIR='${target_evidence_dir_abs}' NEXT_PUBLIC_API_BASE_URL='${api_base}' npm run e2e -- e2e/full-dashboard-flow.spec.ts --project=chromium"

printf '%s\n' "full dashboard QA: PASS"
