# MyGM V1 Contract

Status: Active foundation contract  
Last refreshed: 2026-06-25  
Owners: F owns this contract; D owns API implementation; E owns web implementation; A owns Supabase schema/RLS; B/C own worker import and analytics.

This document freezes names and boundaries so parallel implementation can proceed without inventing incompatible routes, environment variables, score versions, storage paths, or job states.

## Product Boundary
- V1 is ESPN-only and private-alpha invite-gated.
- Browser clients may use Supabase Auth, the public Supabase anon key, and the Railway API base URL only.
- Browser clients must not receive service-role keys, encryption keys, `SWID`, `espn_s2`, raw ESPN artifacts, raw import manifests, or private storage paths.
- Long ESPN imports, player lookup, trade grading, waiver grading, and GM rating calculations run in the worker, never in Vercel functions or inline API request handlers.
- Scores are retrospective value-captured surfaces. Do not claim true ex-ante decision quality.
- 2026 partial/preseason rows are excluded from career analytics by default.

## Web Routes

### Public and Auth Entry
- `/`: private-alpha entry surface with login/import CTA and privacy note.
- `/login`: Supabase login.
- `/invite/[inviteCode]`: invite acceptance and alpha gate.
- `/connect`: ESPN connect wizard and credential validation.
- `/import-runs/[runId]`: import progress/status page.
- `/s/[shareSlug]`: unauthenticated privacy-safe public report card.

### Authenticated League App
- `/leagues/[leagueId]`: league dashboard.
- `/leagues/[leagueId]/seasons/[seasonYear]`: season overview.
- `/leagues/[leagueId]/gms`: GM leaderboard.
- `/leagues/[leagueId]/gms/[managerId]`: manager report card/profile.
- `/leagues/[leagueId]/trades`: canonical trade grades.
- `/leagues/[leagueId]/waivers`: waiver/free-agent grades.
- `/leagues/[leagueId]/records`: all-time records.
- `/leagues/[leagueId]/formula`: formula and provenance.
- `/leagues/[leagueId]/data-health`: warnings, caveats, coverage, ungraded/withheld explanations.
- `/leagues/[leagueId]/settings`: league credentials, share settings, manager claims, and data deletion/export links.
- `/admin/import-runs`: internal-only import/job status.

## API Routes

All API routes are rooted at `/v1`. Protected routes require a Supabase user JWT and server-side authorization. Route IDs are UUIDs unless a name explicitly says slug or code.

### Alpha, Auth, and Membership
- `GET /v1/me`: current profile, alpha access, organizations, league memberships, and internal-admin flag.
- `POST /v1/alpha-invites/accept`: accept invite by email/code and create membership.
- `GET /v1/organizations/{organization_id}/leagues`: list leagues visible to the caller.
- `POST /v1/manager-claims`: request manager identity claim.
- `PATCH /v1/manager-claims/{claim_id}`: approve, reject, or cancel a manager claim.

### League and Credentials
- `POST /v1/leagues`: create ESPN league record.
- `GET /v1/leagues/{league_id}`: league summary and current version pointer.
- `POST /v1/leagues/{league_id}/credentials`: store or rotate ESPN credentials. Request includes `leagueId`, `SWID`, `espn_s2`, `consentVersion`, and selected seasons. Response returns `credentialVersion`; never echo credentials.
- `POST /v1/leagues/{league_id}/credentials/validate`: validate credentials without starting import. Response returns validation status and safe league metadata only.
- `DELETE /v1/leagues/{league_id}/credentials`: revoke stored credentials.

### Imports and Reprocessing
- `POST /v1/leagues/{league_id}/import-runs`: enqueue import with `startYear`, `endYear`, `includeActivity`, `forceRefresh`; accepts `Idempotency-Key`.
- `GET /v1/import-runs/{run_id}`: status, step, counts, warnings, and error summary.
- `GET /v1/import-runs/{run_id}/artifacts`: authenticated artifact manifest or signed URLs only; unauthenticated requests return `401` or `403`.
- `POST /v1/import-runs/{run_id}/cancel`: best-effort cancel before next step starts.
- `POST /v1/import-runs/{run_id}/retry`: retry failed retryable steps.
- `POST /v1/leagues/{league_id}/reprocess-runs`: derive from an existing import with target outputs and formula/version options.
- `GET /v1/reprocess-runs/{run_id}`: derived status and output version.
- `POST /v1/versions/{version_id}/publish`: atomically move the league `current` pointer after validation.

### Analytics Queries
- `GET /v1/leagues/{league_id}/dashboard?version=current`
- `GET /v1/leagues/{league_id}/seasons/{season_year}?version=current`
- `GET /v1/leagues/{league_id}/gms?scope=all_time&version=current`
- `GET /v1/leagues/{league_id}/gms/{manager_id}?version=current`
- `GET /v1/leagues/{league_id}/trades?version=current`
- `GET /v1/leagues/{league_id}/waivers?version=current`
- `GET /v1/leagues/{league_id}/records?version=current`
- `GET /v1/leagues/{league_id}/formula?version=current`
- `GET /v1/leagues/{league_id}/data-health?version=current`
- `GET /v1/leagues/{league_id}/players/{player_id}/weekly-points?season=2025`

### Share Links
- `POST /v1/leagues/{league_id}/share-links`: create opaque share link.
- `GET /v1/leagues/{league_id}/share-links`: list authenticated share links.
- `DELETE /v1/share-links/{share_link_id}`: revoke share link.
- `GET /v1/share/{share_slug}`: public privacy-safe report-card payload.
- `GET /v1/share/{share_slug}/og.png`: public Open Graph PNG. Must not reveal raw artifacts, internal IDs, private emails, ESPN cookies, import logs, or non-public league settings.

## Job States
- Import/reprocess run states: `queued`, `running`, `succeeded`, `failed`, `cancel_requested`, `cancelled`, `dead`.
- Step states: `pending`, `running`, `succeeded`, `retry_scheduled`, `failed_retryable`, `failed_terminal`, `skipped`.
- Every run records `credentialVersion`, source counts, warning count, error summary, and current worker step. It never records credential values.

## Storage Paths
- Private raw imports bucket: `raw-imports`.
- Private derived artifacts bucket: `derived-artifacts`.
- Share preview bucket: `share-previews`.
- Raw import object prefix: `org/{organizationId}/league/{leagueId}/import/{runId}/raw/{seasonYear}/{documentName}.json`.
- Derived object prefix: `org/{organizationId}/league/{leagueId}/version/{versionId}/{artifactName}.json`.
- Share preview prefix: `share/{shareSlug}/{versionId}/og.png`.
- Raw and derived buckets are never public. Share previews are public only when they contain privacy-safe rendered output.

## Score and Version Names
- Trade score model: `trade_outcome_v1`.
- Acquisition score model: `acquisition_outcome_v1`.
- Season GM score model: `season_gm_rating_v1`.
- Career GM score model: `career_gm_rating_v1`.
- Records model: `records_v1`.
- Data health model: `data_health_v1`.
- Current alias: `current`.
- Every score row includes model name, model version, confidence, source coverage, formula inputs, warnings, and source references.

## Environment Variables

### Root and Local Harness
- `MYGM_FIXTURE_ZIP`: optional path to a fixture ZIP. If omitted, the local harness discovers a single `espn_league_*_export.zip`.
- `MYGM_FIXTURE_ROOT`: optional materialized fixture root. If omitted, the local harness discovers a single `tests/fixtures/espn/league_*` directory.
- `API_BASE`: local API base URL. Default: `http://127.0.0.1:8000`.
- `WEB_BASE`: local web base URL. Default: `http://127.0.0.1:3000`.

### Web, Public Only
- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- `NEXT_PUBLIC_API_BASE_URL`

### API and Worker, Server Only
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `SUPABASE_DB_URL`
- `MYGM_CREDENTIAL_KEY_V1`
- `MYGM_CREDENTIAL_KEY_ID`
- `MYGM_ALLOWED_ORIGINS`
- `MYGM_IMPORT_POLL_INTERVAL_SECONDS`

### Never in Vercel or Client Bundles
- `SUPABASE_SERVICE_ROLE_KEY`
- `MYGM_CREDENTIAL_KEY_V1`
- `ESPN_SWID`
- `ESPN_S2`
- `espn_s2`
- Any real ESPN cookie or service account value.

## Fixture Contract
- ZIP entries: 337.
- ZIP non-directory files: 306.
- Seasons: 2020, 2021, 2022, 2023, 2024, 2025, 2026.
- Transaction-period payloads: 118.
- Box-score payloads: 118.
- Player-week rows: 28,294.
- WAIVER rows: 2,662.
- FREEAGENT rows: 1,237.
- Executed accepted trade rows: 95.
- Graded trade rows: 70.
- Canonical graded trade events: 51.

Run `make verify-fixtures` before using fixture data in worker, analytics, API, or web tests.

## Cross-Team Handoff
- A may rely on bucket names, score model names, credential metadata names, and share link privacy boundaries.
- B may rely on fixture root, job states, credential version names, and raw storage prefixes.
- C may rely on score model names, 2026 exclusion, and fixture count contract.
- D may implement exactly the API paths listed here unless a leader-approved contract update lands.
- E may implement exactly the web routes, env names, design tokens, and interaction-state requirements in `DESIGN.md` and this file.
