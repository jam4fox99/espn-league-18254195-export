set -euo pipefail
. scripts/harness_lib.sh

evidence="$evidence_dir/task-11-mygm-espn-private-alpha.txt"
exec > >(tee "$evidence") 2>&1

run_step "env validation" bash scripts/validate_env.sh
run_step "secret scan" bash scripts/secret_scan.sh

if test -f services/api/pyproject.toml; then
  run_step "api security and contract tests" true
  if ! (cd services/api && uv run pytest -p no:capture tests/security tests/contracts -q); then
    fail "API_SECURITY_TEST_FAILED: cd services/api && uv run pytest -p no:capture tests/security tests/contracts -q"
  fi
else
  fail "MISSING_SURFACE: services/api/pyproject.toml"
fi

if test -f supabase/tests/security_hardening.sql; then
  test -n "${SUPABASE_DB_URL:-}" || fail "MISSING_ENV: SUPABASE_DB_URL required for supabase/tests/security_hardening.sql"
  run_step "supabase security hardening sql" psql "$SUPABASE_DB_URL" -v ON_ERROR_STOP=1 -f supabase/tests/security_hardening.sql
else
  fail "MISSING_SURFACE: supabase/tests/security_hardening.sql"
fi

printf '%s\n' "security check: PASS"
