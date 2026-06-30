set -euo pipefail
. scripts/harness_lib.sh

evidence="$evidence_dir/scope-fidelity-mygm-espn-private-alpha.txt"
exec > >(tee "$evidence") 2>&1

require_file "DESIGN.md"
require_file "docs/contracts/mygm-v1.md"

rg -q "Retrospective GM Rating|retrospective value|value captured" DESIGN.md docs/contracts/mygm-v1.md apps/web services/api services/worker || fail "SCOPE_COPY_MISSING: retrospective value framing"
rg -q "2026.*excluded|excluded.*2026" DESIGN.md docs/contracts/mygm-v1.md apps/web services/api services/worker || fail "SCOPE_COPY_MISSING: 2026 career exclusion"
rg -q "confidence|data health|source coverage" DESIGN.md docs/contracts/mygm-v1.md apps/web services/api services/worker || fail "SCOPE_COPY_MISSING: confidence/data-health framing"

forbidden_matches="$(
  rg -n "decision grade|projection|KTC|FantasyPros|Sleeper import|Yahoo import|gambling|betting" apps/web services/api services/worker 2>/dev/null \
    | rg -v "not a projection|No projections|no projections|without projection|never.*projection" || true
)"
if test -n "$forbidden_matches"; then
  printf '%s\n' "$forbidden_matches"
  fail "SCOPE_FORBIDDEN_COPY: forbidden V1 scope/copy term found"
fi

printf '%s\n' "scope fidelity: PASS"
