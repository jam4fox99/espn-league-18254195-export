set -u

evidence_dir="${MYGM_EVIDENCE_DIR:-.omo/evidence}"
mkdir -p "$evidence_dir"

fail() {
  printf '%s\n' "$1" >&2
  exit "${2:-1}"
}

require_file() {
  test -f "$1" || fail "MISSING_SURFACE: $1"
}

require_dir() {
  test -d "$1" || fail "MISSING_SURFACE: $1"
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || fail "MISSING_TOOL: $1"
}

run_step() {
  name="$1"
  shift
  printf '== %s ==\n' "$name"
  "$@"
}
