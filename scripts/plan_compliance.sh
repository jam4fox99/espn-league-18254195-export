set -euo pipefail
. scripts/harness_lib.sh

evidence="$evidence_dir/plan-compliance-mygm-espn-private-alpha.txt"
exec > >(tee "$evidence") 2>&1

plan="${PLAN:-.omo/plans/mygm-espn-private-alpha.md}"
evidence_root="${EVIDENCE:-.omo/evidence}"
team_artifacts="${MYGM_TEAM_ARTIFACTS_DIR:-.omo/teams/019eff34-8f13-7913-8970-56c95138a12e/artifacts}"

require_file "$plan"
require_dir "$evidence_root"

has_path() {
  test -e "$1"
}

has_task_evidence() {
  task="$1"
  shift

  if find "$evidence_root" -maxdepth 2 \( -name "task-$task-*" -o -path "$evidence_root/task-$task-*" \) | grep -q .; then
    return 0
  fi

  for candidate in "$@"; do
    if has_path "$candidate"; then
      return 0
    fi
  done

  return 1
}

missing_tasks=""

for n in 1 2 3 4 5 6 7 8 9 10 11; do
  case "$n" in
    2)
      has_task_evidence "$n" "$team_artifacts/schema-auth-rls-task2.md" || missing_tasks="$missing_tasks task-$n"
      ;;
    4)
      has_task_evidence "$n" "$team_artifacts/analytics-scoring-handoff.md" || missing_tasks="$missing_tasks task-$n"
      ;;
    10)
      has_task_evidence "$n" "$evidence_root/worker-fixture-import-mygm-espn-private-alpha.txt" "$team_artifacts/F-tasks-10-12-harness-handoff.md" || missing_tasks="$missing_tasks task-$n"
      ;;
    11)
      has_task_evidence "$n" "$team_artifacts/schema-auth-rls-task11-hardening.md" || missing_tasks="$missing_tasks task-$n"
      ;;
    *)
      has_task_evidence "$n" || missing_tasks="$missing_tasks task-$n"
      ;;
  esac
done

if test -n "$missing_tasks"; then
  fail "MISSING_EVIDENCE:${missing_tasks} under $evidence_root or accepted team artifacts"
fi

require_file "DESIGN.md"
require_file "docs/contracts/mygm-v1.md"
require_file "Makefile"
require_file "infra/local/compose.yml"

printf '%s\n' "plan compliance: PASS"
