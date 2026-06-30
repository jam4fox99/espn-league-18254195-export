set -euo pipefail
. scripts/harness_lib.sh

evidence="$evidence_dir/friend-test-mygm-espn-private-alpha.md"
exec > >(tee "$evidence") 2>&1

run_step "env validation" bash scripts/validate_env.sh
run_step "fixture contract" make verify-fixtures
run_step "worker fixture import" bash scripts/worker_fixture_import.sh
run_step "local health smoke" bash scripts/local_health_smoke.sh

require_file "apps/web/package.json"
require_file "apps/web/e2e/connect-import.spec.ts"
require_file "apps/web/e2e/invite-gate.spec.ts"
require_file "apps/web/e2e/connect-invalid-credential.spec.ts"

run_step "web friend-test playwright" bash -lc "cd apps/web && npm run e2e -- --project=chromium --output ../../.omo/evidence/task-12-playwright"

api_base="${API_BASE:-http://127.0.0.1:8000}"
raw_code="$(curl -sS -o /tmp/mygm-raw-artifact-denied.out -w '%{http_code}' "$api_base/v1/import-runs/00000000-0000-0000-0000-000000000000/artifacts" || true)"
printf 'raw artifact unauth status: %s\n' "$raw_code" | tee "$evidence_dir/friend-test-raw-artifact-denied.txt" >/dev/null
case "$raw_code" in
  401|403|404) ;;
  *) fail "RAW_ARTIFACT_PRIVACY_FAILED: expected 401, 403, or 404 for unauth artifact request, got ${raw_code:-curl-failed}" ;;
esac

printf '%s\n' "friend test: PASS"
