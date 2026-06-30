# Local Harness

This harness is local-first and does not require paid Railway access. It runs API, worker, and web services from the checked-out source with public container images.

## Commands

- `make validate-env`: checks committed env examples and contract env names without printing secret values.
- `make verify-fixtures`: materializes and verifies the ESPN fixture contract.
- `make worker-fixture-import`: runs the worker fixture analysis and writes `.omo/evidence/task-10-worker-fixture-import/summary.json`.
- `make local-health-smoke`: checks `API_BASE/healthz` and `WEB_BASE`.
- `make security-check`: runs env validation, secret/client-bundle scans, API security tests, and A's Supabase hardening SQL when available.
- `make friend-test`: runs env, fixture, worker, local health, Playwright, and raw-artifact unauth denial checks.

## Compose

Run individual profiles:

```bash
docker compose -f infra/local/compose.yml --profile api up api
docker compose -f infra/local/compose.yml --profile web up web
docker compose -f infra/local/compose.yml --profile worker run --rm worker
```

Run app profiles together after dependencies are ready:

```bash
docker compose -f infra/local/compose.yml --profile app up
```

Railway deployment remains adaptable until billing is available. Keep backend and worker start commands aligned with the compose commands.
