.PHONY: verify-fixtures validate-env local-health-smoke worker-fixture-import security-check friend-test plan-compliance quality-review scope-fidelity-check

MYGM_FIXTURE_ZIP ?= $(shell find . -maxdepth 1 -type f -name 'espn_league_*_export.zip' 2>/dev/null | sort | head -n 1)
MYGM_FIXTURE_ROOT ?= $(shell find tests/fixtures/espn -mindepth 1 -maxdepth 1 -type d -name 'league_*' 2>/dev/null | sort | head -n 1)

verify-fixtures:
	MYGM_FIXTURE_ZIP="$(MYGM_FIXTURE_ZIP)" MYGM_FIXTURE_ROOT="$(MYGM_FIXTURE_ROOT)" uv run --script scripts/verify_fixtures.py

validate-env:
	bash scripts/validate_env.sh

local-health-smoke:
	bash scripts/local_health_smoke.sh

worker-fixture-import:
	bash scripts/worker_fixture_import.sh

security-check:
	bash scripts/security_check.sh

friend-test:
	bash scripts/friend_test.sh

plan-compliance:
	bash scripts/plan_compliance.sh

quality-review:
	bash scripts/quality_review.sh

scope-fidelity-check:
	bash scripts/scope_fidelity_check.sh
