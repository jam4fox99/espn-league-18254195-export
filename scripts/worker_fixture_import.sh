set -euo pipefail
. scripts/harness_lib.sh

evidence="$evidence_dir/worker-fixture-import-mygm-espn-private-alpha.txt"
exec > >(tee "$evidence") 2>&1

fixture_root="${MYGM_FIXTURE_ROOT:-}"
out_dir="${MYGM_WORKER_FIXTURE_OUT:-.omo/evidence/task-10-worker-fixture-import}"

if test -z "$fixture_root"; then
  fixture_root="$(find tests/fixtures/espn -mindepth 1 -maxdepth 1 -type d -name 'league_*' 2>/dev/null | sort | head -n 1 || true)"
fi
test -n "$fixture_root" || fail "MYGM_FIXTURE_ROOT_REQUIRED: set MYGM_FIXTURE_ROOT or add one tests/fixtures/espn/league_* fixture"

require_file "services/worker/pyproject.toml"
require_dir "$fixture_root"
mkdir -p "$out_dir"

run_step "worker analyze fixture" bash -lc "cd services/worker && uv run mygm-worker analyze-fixture --fixture-root ../../$fixture_root --out ../../$out_dir"
require_file "$out_dir/summary.json"
require_file "$out_dir/analytics_snapshot.json"
grep -q '"status": "PASS"' "$out_dir/summary.json" || fail "WORKER_FIXTURE_IMPORT_FAILED: expected PASS summary at $out_dir/summary.json"
grep -q '"snapshotVersion": "espn-league-analytics-snapshot-v1"' "$out_dir/analytics_snapshot.json" || fail "WORKER_FIXTURE_IMPORT_FAILED: expected analytics snapshot at $out_dir/analytics_snapshot.json"

printf '%s\n' "worker fixture import: PASS"
