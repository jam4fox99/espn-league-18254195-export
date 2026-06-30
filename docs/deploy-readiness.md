# Deploy Readiness

Status: Vercel frontend plus Vercel FastAPI alpha backend are live. Railway remains blocked for a
durable backend/worker deployment.

## Local Readiness Gates
- `make validate-env`
- `make verify-fixtures`
- `make worker-fixture-import`
- `make security-check`
- `make friend-test`
- `make quality-review`
- `make scope-fidelity-check`

## Backend and Worker
- Local API command: `cd services/api && uv run uvicorn mygm_api.main:app --host 0.0.0.0 --port 8000`
- Local worker fixture command: `cd services/worker && uv run mygm-worker analyze-fixture --fixture-root ../../tests/fixtures/espn/league_<id> --out ../../.omo/evidence/task-10-worker-fixture-import`
- Public alpha API: `https://mygm-api-alpha.vercel.app`
- The Vercel API project receives server-side `MYGM_CREDENTIAL_KEY_V1` and CORS origin config.
  Do not expose those values to `apps/web`.
- The Vercel API is an alpha bridge: it encrypts submitted ESPN cookies server-side, queues an
  in-memory import run, and serves fixture-backed analytics/status responses. Supabase durability and
  a deployed worker remain pending until Railway billing is fixed or another durable no-payment
  backend is selected.
- Railway API start command should match the API command with Railway-provided host/port.
- Railway worker start command should run the future polling worker when B/D publish that entry point. Until then, fixture analysis is the local readiness proof.

## Vercel
- Frontend: `https://mygm-espn-alpha.vercel.app`
- Frontend deploy receives only public env, including
  `NEXT_PUBLIC_API_BASE_URL=https://mygm-api-alpha.vercel.app`.
- Do not configure `SUPABASE_SERVICE_ROLE_KEY`, `MYGM_CREDENTIAL_KEY_V1`, `ESPN_SWID`,
  `ESPN_S2`, or real ESPN cookies in the frontend project.
- Production deploy should pass a live browser smoke where `/connect` submits through the public API
  and `/import-runs/[runId]` loads the queued run status.

## Evidence Paths
- Env validation: `.omo/evidence/env-validation-mygm-espn-private-alpha.txt`
- Secret scan: `.omo/evidence/secret-scan-mygm-espn-private-alpha.txt`
- Security check: `.omo/evidence/task-11-mygm-espn-private-alpha.txt`
- Friend test: `.omo/evidence/friend-test-mygm-espn-private-alpha.md`
- Raw artifact denial: `.omo/evidence/friend-test-raw-artifact-denied.txt`
- Worker fixture import: `.omo/evidence/worker-fixture-import-mygm-espn-private-alpha.txt`
- Worker fixture summary: `.omo/evidence/task-10-worker-fixture-import/summary.json`
- Plan compliance: `.omo/evidence/plan-compliance-mygm-espn-private-alpha.txt`
- Quality review: `.omo/evidence/quality-review-mygm-espn-private-alpha.txt`
- Scope fidelity: `.omo/evidence/scope-fidelity-mygm-espn-private-alpha.txt`
- Live Vercel connect smoke: `.omo/evidence/vercel-live-connect-public-api.png`
- Live Vercel status smoke: `.omo/evidence/vercel-live-status-public-api.png`
