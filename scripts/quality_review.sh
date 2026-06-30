set -euo pipefail
. scripts/harness_lib.sh

evidence="$evidence_dir/quality-review-mygm-espn-private-alpha.txt"
exec > >(tee "$evidence") 2>&1

run_step "api quality" bash -lc "cd services/api && uv run ruff check . && uv run basedpyright && uv run pytest -q"
run_step "worker quality" bash -lc "cd services/worker && uv run ruff check . && uv run basedpyright && uv run pytest -q -p no:capture"
run_step "web quality" bash -lc "cd apps/web && npm run lint && npm run typecheck && npm run test && npm run build"

printf '%s\n' "quality review: PASS"
