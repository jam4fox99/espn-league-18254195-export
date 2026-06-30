set -euo pipefail
. scripts/harness_lib.sh

evidence="$evidence_dir/local-health-smoke-mygm-espn-private-alpha.txt"
exec > >(tee "$evidence") 2>&1

api_base="${API_BASE:-http://127.0.0.1:8000}"
web_base="${WEB_BASE:-http://127.0.0.1:3000}"

require_command curl

api_code="$(curl -sS -o /tmp/mygm-api-health.out -w '%{http_code}' "$api_base/healthz" || true)"
if test "$api_code" != "200"; then
  fail "MISSING_SURFACE: API health expected 200 at $api_base/healthz, got ${api_code:-curl-failed}"
fi

web_code="$(curl -sS -o /tmp/mygm-web-health.out -w '%{http_code}' "$web_base" || true)"
if test "$web_code" != "200"; then
  fail "MISSING_SURFACE: web root expected 200 at $web_base, got ${web_code:-curl-failed}"
fi

printf '%s\n' "local health smoke: PASS"
