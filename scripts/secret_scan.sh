set -euo pipefail
. scripts/harness_lib.sh

evidence="$evidence_dir/secret-scan-mygm-espn-private-alpha.txt"
exec > >(tee "$evidence") 2>&1

require_command rg

client_matches="$(find apps/web -path '*/node_modules' -prune -o -path '*/.next' -prune -o -path '*/playwright-report' -prune -o -type f \( -name '*.ts' -o -name '*.tsx' -o -name '*.js' -o -name '*.jsx' -o -name '*.mjs' -o -name '*.css' -o -name '*.json' \) -print0 2>/dev/null | xargs -0 rg -l 'SUPABASE_SERVICE_ROLE_KEY|MYGM_CREDENTIAL_KEY_V1|ESPN_S2|ESPN_SWID' 2>/dev/null || true)"
if test -n "$client_matches"; then
  printf '%s\n' "$client_matches"
  fail "CLIENT_SECRET_REFERENCE: forbidden server-only key name appears in apps/web source"
fi

repo_matches="$(find . -path './.git' -prune -o -path './apps/web/node_modules' -prune -o -path './apps/web/.next' -prune -o -path './services/*/.venv' -prune -o -path './espn_exports' -prune -o -path './tests/fixtures/espn' -prune -o -type f \( -name '*.env' -o -name '*.local' -o -name '*.example' -o -name '*.md' -o -name '*.py' -o -name '*.ts' -o -name '*.tsx' -o -name '*.yml' -o -name '*.yaml' -o -name '*.toml' -o -name 'Makefile' \) -print0 | xargs -0 rg -l 'espn_s2=[^[:space:]<]+|ESPN_S2=[^[:space:]<]+|SWID=\\{?[A-F0-9-]{8,}\\}?|SUPABASE_SERVICE_ROLE_KEY=eyJ|MYGM_CREDENTIAL_KEY_V1=[A-Za-z0-9+/]{32,}' 2>/dev/null || true)"
if test -n "$repo_matches"; then
  printf '%s\n' "$repo_matches"
  fail "SECRET_VALUE_REFERENCE: secret-like value appears in repository text"
fi

printf '%s\n' "secret scan: PASS"
