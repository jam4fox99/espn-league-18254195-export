set -euo pipefail
. scripts/harness_lib.sh

evidence="$evidence_dir/env-validation-mygm-espn-private-alpha.txt"
exec > >(tee "$evidence") 2>&1

require_file ".env.example"
require_file ".env.alpha.local.example"

grep -q '^MYGM_FIXTURE_ZIP=' .env.example || fail "MISSING_ENV_EXAMPLE_KEY: MYGM_FIXTURE_ZIP"
grep -q '^MYGM_FIXTURE_ROOT=' .env.example || fail "MISSING_ENV_EXAMPLE_KEY: MYGM_FIXTURE_ROOT"
grep -q '^API_BASE=' .env.example || fail "MISSING_ENV_EXAMPLE_KEY: API_BASE"
grep -q '^WEB_BASE=' .env.example || fail "MISSING_ENV_EXAMPLE_KEY: WEB_BASE"
grep -q '^NEXT_PUBLIC_SUPABASE_URL=' .env.alpha.local.example || fail "MISSING_ENV_EXAMPLE_KEY: NEXT_PUBLIC_SUPABASE_URL"
grep -q '^NEXT_PUBLIC_SUPABASE_ANON_KEY=' .env.alpha.local.example || fail "MISSING_ENV_EXAMPLE_KEY: NEXT_PUBLIC_SUPABASE_ANON_KEY"
grep -q '^NEXT_PUBLIC_API_BASE_URL=' .env.alpha.local.example || fail "MISSING_ENV_EXAMPLE_KEY: NEXT_PUBLIC_API_BASE_URL"
grep -q '^SUPABASE_SERVICE_ROLE_KEY=' .env.alpha.local.example || fail "MISSING_ENV_EXAMPLE_KEY: SUPABASE_SERVICE_ROLE_KEY"
grep -q '^MYGM_CREDENTIAL_KEY_V1=' .env.alpha.local.example || fail "MISSING_ENV_EXAMPLE_KEY: MYGM_CREDENTIAL_KEY_V1"

if rg -l -P '(^|[^A-Z0-9_])MYGM_CREDENTIAL_KEY([^A-Z0-9_]|$)' .env.example .env.alpha.local.example docs/contracts/mygm-v1.md Makefile infra .github 2>/dev/null; then
  fail "STALE_ENV_ALIAS: MYGM_CREDENTIAL_KEY without _V1"
fi

if rg -l 'ESPN_S2=|espn_s2=.*[^a-zA-Z_-]|SERVICE_ROLE_KEY=eyJ|MYGM_CREDENTIAL_KEY_V1=[A-Za-z0-9+/]{32,}' .env.example .env.alpha.local.example 2>/dev/null; then
  fail "SECRET_EXAMPLE_VALUE: env example appears to contain a real secret-like value"
fi

printf '%s\n' "env validation: PASS"
