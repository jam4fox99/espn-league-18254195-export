create extension if not exists "citext";
create extension if not exists "pgcrypto";

create type public.provider_kind as enum ('espn', 'sleeper', 'yahoo');
create type public.alpha_invite_status as enum ('pending', 'accepted', 'revoked', 'expired');
create type public.org_member_role as enum ('owner', 'admin', 'member');
create type public.league_member_role as enum ('commissioner', 'manager', 'viewer');
create type public.manager_claim_status as enum ('pending', 'approved', 'rejected', 'revoked');
create type public.credential_status as enum ('active', 'expired', 'revoked', 'invalid');
create type public.ingestion_run_status as enum ('queued', 'running', 'succeeded', 'failed', 'cancel_requested', 'cancelled');
create type public.import_step_status as enum ('queued', 'running', 'succeeded', 'failed', 'skipped');
create type public.share_link_status as enum ('active', 'revoked', 'expired');
create type public.audit_action as enum ('invite.accepted', 'claim.created', 'claim.reviewed', 'credential.created', 'credential.rotated', 'import.created', 'share.created', 'share.revoked');
create type public.transaction_kind as enum ('trade', 'waiver', 'freeagent', 'drop', 'draft', 'other');

create table public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  email citext not null unique,
  display_name text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.organizations (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  created_by uuid not null references auth.users(id),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.organization_members (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  role public.org_member_role not null default 'member',
  created_at timestamptz not null default now(),
  unique (organization_id, user_id)
);

create table public.alpha_invites (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  email citext not null,
  code text not null unique,
  role public.org_member_role not null default 'member',
  status public.alpha_invite_status not null default 'pending',
  expires_at timestamptz not null,
  accepted_by uuid references auth.users(id),
  accepted_at timestamptz,
  created_by uuid not null references auth.users(id),
  created_at timestamptz not null default now(),
  check (
    (status = 'accepted' and accepted_by is not null and accepted_at is not null)
    or (status <> 'accepted' and accepted_by is null and accepted_at is null)
  )
);

create table public.leagues (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  provider public.provider_kind not null default 'espn',
  provider_league_id text not null,
  name text not null,
  timezone text not null default 'America/New_York',
  created_by uuid not null references auth.users(id),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (provider, provider_league_id)
);

create table public.league_members (
  id uuid primary key default gen_random_uuid(),
  league_id uuid not null references public.leagues(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  role public.league_member_role not null default 'viewer',
  created_at timestamptz not null default now(),
  unique (league_id, user_id)
);

create table public.league_seasons (
  id uuid primary key default gen_random_uuid(),
  league_id uuid not null references public.leagues(id) on delete cascade,
  organization_id uuid not null references public.organizations(id) on delete cascade,
  season_year integer not null check (season_year between 2000 and 2100),
  status text not null default 'scheduled',
  is_partial boolean not null default false,
  source_import_run_id uuid,
  created_at timestamptz not null default now(),
  unique (league_id, season_year)
);

create table public.managers (
  id uuid primary key default gen_random_uuid(),
  league_id uuid not null references public.leagues(id) on delete cascade,
  organization_id uuid not null references public.organizations(id) on delete cascade,
  provider public.provider_kind not null default 'espn',
  provider_manager_id text not null,
  display_name text not null,
  email citext,
  created_at timestamptz not null default now(),
  unique (league_id, provider, provider_manager_id)
);

create table public.manager_claims (
  id uuid primary key default gen_random_uuid(),
  league_id uuid not null references public.leagues(id) on delete cascade,
  manager_id uuid not null references public.managers(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  status public.manager_claim_status not null default 'pending',
  evidence jsonb not null default '{}'::jsonb,
  reviewer_id uuid references auth.users(id),
  reviewed_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (league_id, manager_id, user_id),
  check (
    (status in ('approved', 'rejected', 'revoked') and reviewer_id is not null and reviewed_at is not null)
    or (status = 'pending' and reviewer_id is null and reviewed_at is null)
  )
);

create table public.team_seasons (
  id uuid primary key default gen_random_uuid(),
  league_season_id uuid not null references public.league_seasons(id) on delete cascade,
  league_id uuid not null references public.leagues(id) on delete cascade,
  organization_id uuid not null references public.organizations(id) on delete cascade,
  provider_team_id text not null,
  team_name text not null,
  wins integer,
  losses integer,
  ties integer,
  points_for numeric(12, 4),
  points_against numeric(12, 4),
  created_at timestamptz not null default now(),
  unique (league_season_id, provider_team_id)
);

create table public.team_season_managers (
  id uuid primary key default gen_random_uuid(),
  team_season_id uuid not null references public.team_seasons(id) on delete cascade,
  manager_id uuid not null references public.managers(id) on delete cascade,
  started_at date,
  ended_at date,
  created_at timestamptz not null default now(),
  unique (team_season_id, manager_id)
);

create table public.ingestion_runs (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  league_id uuid not null references public.leagues(id) on delete cascade,
  requested_by uuid not null references auth.users(id),
  credential_version integer,
  status public.ingestion_run_status not null default 'queued',
  idempotency_key text,
  requested_seasons int[] not null default '{}',
  started_at timestamptz,
  finished_at timestamptz,
  error_code text,
  error_message text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (league_id, idempotency_key)
);

create table public.import_run_steps (
  id uuid primary key default gen_random_uuid(),
  ingestion_run_id uuid not null references public.ingestion_runs(id) on delete cascade,
  organization_id uuid not null references public.organizations(id) on delete cascade,
  league_id uuid not null references public.leagues(id) on delete cascade,
  step_name text not null,
  status public.import_step_status not null default 'queued',
  attempt integer not null default 0,
  locked_by text,
  locked_at timestamptz,
  started_at timestamptz,
  finished_at timestamptz,
  error_code text,
  error_message text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (ingestion_run_id, step_name)
);

create table public.source_documents (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  league_id uuid not null references public.leagues(id) on delete cascade,
  ingestion_run_id uuid not null references public.ingestion_runs(id) on delete cascade,
  bucket_id text not null,
  object_path text not null,
  sha256 text not null check (sha256 ~ '^[a-f0-9]{64}$'),
  content_type text not null default 'application/json',
  source_kind text not null,
  source_url text,
  fetched_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  unique (bucket_id, object_path)
);

create table public.storage_artifacts (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  league_id uuid not null references public.leagues(id) on delete cascade,
  ingestion_run_id uuid references public.ingestion_runs(id) on delete set null,
  source_document_id uuid references public.source_documents(id) on delete set null,
  bucket_id text not null,
  object_path text not null,
  artifact_kind text not null,
  transform_version text,
  sha256 text check (sha256 is null or sha256 ~ '^[a-f0-9]{64}$'),
  created_at timestamptz not null default now(),
  unique (bucket_id, object_path)
);

create table public.players (
  id uuid primary key default gen_random_uuid(),
  provider public.provider_kind not null default 'espn',
  provider_player_id text not null,
  full_name text not null,
  positions text[] not null default '{}',
  created_at timestamptz not null default now(),
  unique (provider, provider_player_id)
);

create table public.provider_entity_map (
  id uuid primary key default gen_random_uuid(),
  provider public.provider_kind not null,
  entity_kind text not null,
  provider_entity_id text not null,
  internal_entity_id uuid not null,
  created_at timestamptz not null default now(),
  unique (provider, entity_kind, provider_entity_id)
);

create table public.matchups (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  league_id uuid not null references public.leagues(id) on delete cascade,
  league_season_id uuid not null references public.league_seasons(id) on delete cascade,
  week integer not null check (week > 0),
  home_team_season_id uuid references public.team_seasons(id) on delete set null,
  away_team_season_id uuid references public.team_seasons(id) on delete set null,
  home_score numeric(12, 4),
  away_score numeric(12, 4),
  created_at timestamptz not null default now()
);

create table public.roster_week_entries (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  league_id uuid not null references public.leagues(id) on delete cascade,
  league_season_id uuid not null references public.league_seasons(id) on delete cascade,
  team_season_id uuid not null references public.team_seasons(id) on delete cascade,
  player_id uuid not null references public.players(id),
  week integer not null check (week > 0),
  slot text not null,
  lineup_locked boolean not null default false,
  created_at timestamptz not null default now(),
  unique (team_season_id, player_id, week, slot)
);

create table public.player_week_stats (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  league_id uuid not null references public.leagues(id) on delete cascade,
  league_season_id uuid not null references public.league_seasons(id) on delete cascade,
  player_id uuid not null references public.players(id),
  week integer not null check (week > 0),
  fantasy_points numeric(12, 4),
  stat_source text not null default 'espn',
  created_at timestamptz not null default now(),
  unique (league_season_id, player_id, week, stat_source)
);

create table public.transactions (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  league_id uuid not null references public.leagues(id) on delete cascade,
  league_season_id uuid not null references public.league_seasons(id) on delete cascade,
  provider_transaction_id text not null,
  kind public.transaction_kind not null,
  occurred_at timestamptz not null,
  status text not null default 'executed',
  raw_source_document_id uuid references public.source_documents(id) on delete set null,
  created_at timestamptz not null default now(),
  unique (league_id, provider_transaction_id)
);

create table public.transaction_items (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  league_id uuid not null references public.leagues(id) on delete cascade,
  transaction_id uuid not null references public.transactions(id) on delete cascade,
  player_id uuid references public.players(id),
  manager_id uuid references public.managers(id),
  from_team_season_id uuid references public.team_seasons(id),
  to_team_season_id uuid references public.team_seasons(id),
  action text not null,
  created_at timestamptz not null default now()
);

create table public.score_models (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  version text not null,
  formula jsonb not null,
  is_active boolean not null default false,
  created_at timestamptz not null default now(),
  unique (name, version)
);

create table public.trade_events (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  league_id uuid not null references public.leagues(id) on delete cascade,
  league_season_id uuid not null references public.league_seasons(id) on delete cascade,
  canonical_key text not null,
  occurred_at timestamptz not null,
  score_model_id uuid references public.score_models(id),
  grade jsonb not null default '{}'::jsonb,
  confidence text not null default 'unknown',
  created_at timestamptz not null default now(),
  unique (league_id, canonical_key)
);

create table public.trade_event_sides (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  league_id uuid not null references public.leagues(id) on delete cascade,
  trade_event_id uuid not null references public.trade_events(id) on delete cascade,
  manager_id uuid references public.managers(id),
  team_season_id uuid references public.team_seasons(id),
  side_index integer not null,
  grade jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  unique (trade_event_id, side_index)
);

create table public.trade_event_players (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  league_id uuid not null references public.leagues(id) on delete cascade,
  trade_event_side_id uuid not null references public.trade_event_sides(id) on delete cascade,
  player_id uuid references public.players(id),
  direction text not null check (direction in ('sent', 'received')),
  post_trade_points numeric(12, 4),
  created_at timestamptz not null default now()
);

create table public.acquisition_events (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  league_id uuid not null references public.leagues(id) on delete cascade,
  league_season_id uuid not null references public.league_seasons(id) on delete cascade,
  transaction_id uuid references public.transactions(id) on delete set null,
  manager_id uuid references public.managers(id),
  player_id uuid references public.players(id),
  acquisition_type public.transaction_kind not null check (acquisition_type in ('waiver', 'freeagent')),
  occurred_at timestamptz not null,
  created_at timestamptz not null default now()
);

create table public.acquisition_grades (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  league_id uuid not null references public.leagues(id) on delete cascade,
  acquisition_event_id uuid not null references public.acquisition_events(id) on delete cascade,
  score_model_id uuid references public.score_models(id),
  grade jsonb not null default '{}'::jsonb,
  withheld_reason text,
  confidence text not null default 'unknown',
  created_at timestamptz not null default now(),
  unique (acquisition_event_id, score_model_id)
);

create table public.manager_score_snapshots (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  league_id uuid not null references public.leagues(id) on delete cascade,
  manager_id uuid not null references public.managers(id) on delete cascade,
  league_season_id uuid references public.league_seasons(id) on delete cascade,
  score_model_id uuid not null references public.score_models(id),
  scope text not null check (scope in ('season', 'career')),
  score numeric(12, 4),
  components jsonb not null default '{}'::jsonb,
  confidence text not null default 'unknown',
  warnings jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now()
);

create table public.data_quality_warnings (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  league_id uuid not null references public.leagues(id) on delete cascade,
  league_season_id uuid references public.league_seasons(id) on delete cascade,
  severity text not null check (severity in ('info', 'warning', 'error')),
  warning_code text not null,
  message text not null,
  source_document_id uuid references public.source_documents(id) on delete set null,
  created_at timestamptz not null default now()
);

create table public.league_current_versions (
  league_id uuid primary key references public.leagues(id) on delete cascade,
  organization_id uuid not null references public.organizations(id) on delete cascade,
  current_ingestion_run_id uuid references public.ingestion_runs(id) on delete set null,
  score_model_id uuid references public.score_models(id),
  transform_version text not null,
  published_at timestamptz not null default now(),
  published_by uuid references auth.users(id)
);

create table public.league_credentials (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  league_id uuid not null references public.leagues(id) on delete cascade,
  credential_version integer not null,
  key_id text not null,
  nonce bytea not null,
  ciphertext bytea not null,
  expires_at timestamptz,
  rotated_at timestamptz,
  last_validated_at timestamptz,
  status public.credential_status not null default 'active',
  consent_version text not null,
  authorized_by uuid not null references auth.users(id),
  created_by uuid not null references auth.users(id),
  created_at timestamptz not null default now(),
  unique (league_id, credential_version)
);

create table public.share_links (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  league_id uuid not null references public.leagues(id) on delete cascade,
  manager_id uuid references public.managers(id) on delete cascade,
  slug text not null unique,
  token_hash text not null unique,
  status public.share_link_status not null default 'active',
  expires_at timestamptz,
  revoked_at timestamptz,
  created_by uuid not null references auth.users(id),
  created_at timestamptz not null default now()
);

create table public.audit_events (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid references public.organizations(id) on delete cascade,
  league_id uuid references public.leagues(id) on delete cascade,
  actor_id uuid references auth.users(id),
  action public.audit_action not null,
  subject_table text,
  subject_id uuid,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table public.provider_capabilities (
  provider public.provider_kind primary key,
  status text not null check (status in ('mvp', 'post_mvp')),
  notes text not null
);

insert into public.provider_capabilities (provider, status, notes)
values
  ('espn', 'mvp', 'Private alpha ESPN import provider.'),
  ('sleeper', 'post_mvp', 'Neutral provider enum only; no V1 Sleeper product scope.'),
  ('yahoo', 'post_mvp', 'Neutral provider enum only; no V1 Yahoo product scope.');

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values
  ('raw-imports', 'raw-imports', false, null, null),
  ('derived-artifacts', 'derived-artifacts', false, null, null),
  ('share-previews', 'share-previews', false, null, array['image/png', 'image/jpeg', 'image/webp'])
on conflict (id) do update set
  public = excluded.public,
  file_size_limit = excluded.file_size_limit,
  allowed_mime_types = excluded.allowed_mime_types;

create or replace function public.current_user_is_org_member(target_organization_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1
    from public.organization_members om
    where om.organization_id = target_organization_id
      and om.user_id = auth.uid()
  );
$$;

create or replace function public.current_user_email_matches(target_email citext)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1
    from public.profiles p
    where p.id = auth.uid()
      and p.email = target_email
  );
$$;

create or replace function public.current_user_is_org_admin(target_organization_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1
    from public.organization_members om
    where om.organization_id = target_organization_id
      and om.user_id = auth.uid()
      and om.role in ('owner', 'admin')
  );
$$;

create or replace function public.current_user_is_league_member(target_league_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1
    from public.league_members lm
    where lm.league_id = target_league_id
      and lm.user_id = auth.uid()
  );
$$;

create or replace function public.current_user_can_review_claim(target_league_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1
    from public.league_members lm
    where lm.league_id = target_league_id
      and lm.user_id = auth.uid()
      and lm.role in ('commissioner', 'manager')
  );
$$;

create or replace function public.storage_org_id(object_name text)
returns uuid
language sql
immutable
as $$
  select case
    when split_part(object_name, '/', 1) = 'org'
      and split_part(object_name, '/', 2) ~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
      then split_part(object_name, '/', 2)::uuid
    else null
  end;
$$;

create or replace function public.storage_league_id(object_name text)
returns uuid
language sql
immutable
as $$
  select case
    when split_part(object_name, '/', 3) = 'league'
      and split_part(object_name, '/', 4) ~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
      then split_part(object_name, '/', 4)::uuid
    when split_part(object_name, '/', 1) = 'league'
      and split_part(object_name, '/', 2) ~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
      then split_part(object_name, '/', 2)::uuid
    else null
  end;
$$;

create or replace function public.current_user_can_read_storage_object(bucket_id text, object_name text)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select case
    when bucket_id = 'raw-imports'
      then public.current_user_is_org_member(public.storage_org_id(object_name))
        and public.current_user_is_league_member(public.storage_league_id(object_name))
    when bucket_id = 'derived-artifacts'
      then public.current_user_is_league_member(public.storage_league_id(object_name))
    when bucket_id = 'share-previews'
      then exists (
        select 1
        from public.share_links sl
        where sl.league_id = public.storage_league_id(object_name)
          and sl.status = 'active'
          and (sl.expires_at is null or sl.expires_at > now())
          and public.current_user_is_league_member(sl.league_id)
      )
    else false
  end;
$$;

create index organization_members_user_idx on public.organization_members(user_id);
create index alpha_invites_email_status_idx on public.alpha_invites(email, status);
create index leagues_organization_idx on public.leagues(organization_id);
create index league_members_user_idx on public.league_members(user_id);
create index manager_claims_user_idx on public.manager_claims(user_id);
create index ingestion_runs_league_status_idx on public.ingestion_runs(league_id, status);
create index source_documents_league_run_idx on public.source_documents(league_id, ingestion_run_id);
create index storage_artifacts_league_run_idx on public.storage_artifacts(league_id, ingestion_run_id);
create index league_credentials_league_status_idx on public.league_credentials(league_id, status);
create index share_links_league_status_idx on public.share_links(league_id, status);

alter table public.profiles enable row level security;
alter table public.organizations enable row level security;
alter table public.organization_members enable row level security;
alter table public.alpha_invites enable row level security;
alter table public.leagues enable row level security;
alter table public.league_members enable row level security;
alter table public.league_seasons enable row level security;
alter table public.managers enable row level security;
alter table public.manager_claims enable row level security;
alter table public.team_seasons enable row level security;
alter table public.team_season_managers enable row level security;
alter table public.ingestion_runs enable row level security;
alter table public.import_run_steps enable row level security;
alter table public.source_documents enable row level security;
alter table public.storage_artifacts enable row level security;
alter table public.players enable row level security;
alter table public.provider_entity_map enable row level security;
alter table public.matchups enable row level security;
alter table public.roster_week_entries enable row level security;
alter table public.player_week_stats enable row level security;
alter table public.transactions enable row level security;
alter table public.transaction_items enable row level security;
alter table public.score_models enable row level security;
alter table public.trade_events enable row level security;
alter table public.trade_event_sides enable row level security;
alter table public.trade_event_players enable row level security;
alter table public.acquisition_events enable row level security;
alter table public.acquisition_grades enable row level security;
alter table public.manager_score_snapshots enable row level security;
alter table public.data_quality_warnings enable row level security;
alter table public.league_current_versions enable row level security;
alter table public.league_credentials enable row level security;
alter table public.share_links enable row level security;
alter table public.audit_events enable row level security;
alter table public.provider_capabilities enable row level security;

create policy "profiles own row read" on public.profiles for select to authenticated using (id = auth.uid());
create policy "profiles own row insert" on public.profiles for insert to authenticated with check (id = auth.uid());
create policy "profiles own row update" on public.profiles for update to authenticated using (id = auth.uid()) with check (id = auth.uid());

create policy "organizations members read" on public.organizations for select to authenticated using (public.current_user_is_org_member(id));
create policy "organizations creator insert" on public.organizations for insert to authenticated with check (created_by = auth.uid());
create policy "organizations admins update" on public.organizations for update to authenticated using (public.current_user_is_org_admin(id)) with check (public.current_user_is_org_admin(id));

create policy "organization members read org" on public.organization_members for select to authenticated using (public.current_user_is_org_member(organization_id));
create policy "organization members admins insert" on public.organization_members for insert to authenticated with check (public.current_user_is_org_admin(organization_id));
create policy "organization members admins update" on public.organization_members for update to authenticated using (public.current_user_is_org_admin(organization_id)) with check (public.current_user_is_org_admin(organization_id));

create policy "alpha invites org admins read" on public.alpha_invites for select to authenticated using (public.current_user_is_org_admin(organization_id));
create policy "alpha invites invited users read own" on public.alpha_invites
  for select to authenticated
  using (
    public.current_user_email_matches(email)
    and status in ('pending', 'accepted')
    and expires_at > now()
  );
create policy "alpha invites org admins write" on public.alpha_invites for insert to authenticated with check (public.current_user_is_org_admin(organization_id) and created_by = auth.uid());
create policy "alpha invites accepted user update" on public.alpha_invites
  for update to authenticated
  using (
    status = 'pending'
    and expires_at > now()
    and public.current_user_email_matches(email)
  )
  with check (
    status = 'accepted'
    and accepted_by = auth.uid()
    and accepted_at is not null
    and public.current_user_email_matches(email)
  );
create policy "alpha invites org admins update" on public.alpha_invites
  for update to authenticated
  using (public.current_user_is_org_admin(organization_id))
  with check (public.current_user_is_org_admin(organization_id));

create policy "leagues members read" on public.leagues for select to authenticated using (public.current_user_is_league_member(id));
create policy "leagues org admins insert" on public.leagues for insert to authenticated with check (public.current_user_is_org_admin(organization_id) and created_by = auth.uid());
create policy "leagues org admins update" on public.leagues for update to authenticated using (public.current_user_is_org_admin(organization_id)) with check (public.current_user_is_org_admin(organization_id));

create policy "league members same league read" on public.league_members for select to authenticated using (public.current_user_is_league_member(league_id));
create policy "league members org admins insert" on public.league_members
  for insert to authenticated
  with check (exists (
    select 1 from public.leagues l
    where l.id = league_id
      and public.current_user_is_org_admin(l.organization_id)
  ));
create policy "league members commissioners update" on public.league_members
  for update to authenticated
  using (public.current_user_can_review_claim(league_id))
  with check (public.current_user_can_review_claim(league_id));

create policy "league seasons members read" on public.league_seasons for select to authenticated using (public.current_user_is_league_member(league_id));
create policy "league seasons service writes" on public.league_seasons for all to service_role using (true) with check (true);

create policy "managers league members read" on public.managers for select to authenticated using (public.current_user_is_league_member(league_id));
create policy "managers service writes" on public.managers for all to service_role using (true) with check (true);

create policy "manager claims league members read" on public.manager_claims for select to authenticated using (public.current_user_is_league_member(league_id));
create policy "manager claims league members insert own" on public.manager_claims
  for insert to authenticated
  with check (user_id = auth.uid() and status = 'pending' and public.current_user_is_league_member(league_id));
create policy "manager claims reviewers update" on public.manager_claims
  for update to authenticated
  using (public.current_user_can_review_claim(league_id))
  with check (public.current_user_can_review_claim(league_id));

create policy "team seasons league members read" on public.team_seasons for select to authenticated using (public.current_user_is_league_member(league_id));
create policy "team season managers league members read" on public.team_season_managers
  for select to authenticated
  using (exists (
    select 1 from public.team_seasons ts
    where ts.id = team_season_id
      and public.current_user_is_league_member(ts.league_id)
  ));

create policy "ingestion runs league members read" on public.ingestion_runs for select to authenticated using (public.current_user_is_league_member(league_id));
create policy "ingestion runs league members request" on public.ingestion_runs for insert to authenticated with check (requested_by = auth.uid() and public.current_user_is_league_member(league_id));
create policy "ingestion runs service update" on public.ingestion_runs for update to service_role using (true) with check (true);

create policy "import steps league members read" on public.import_run_steps for select to authenticated using (public.current_user_is_league_member(league_id));
create policy "source documents league members read" on public.source_documents for select to authenticated using (public.current_user_is_league_member(league_id));
create policy "storage artifacts league members read" on public.storage_artifacts for select to authenticated using (public.current_user_is_league_member(league_id));

create policy "players authenticated read" on public.players for select to authenticated using (true);
create policy "provider map authenticated read" on public.provider_entity_map for select to authenticated using (true);
create policy "matchups league members read" on public.matchups for select to authenticated using (public.current_user_is_league_member(league_id));
create policy "rosters league members read" on public.roster_week_entries for select to authenticated using (public.current_user_is_league_member(league_id));
create policy "player stats league members read" on public.player_week_stats for select to authenticated using (public.current_user_is_league_member(league_id));
create policy "transactions league members read" on public.transactions for select to authenticated using (public.current_user_is_league_member(league_id));
create policy "transaction items league members read" on public.transaction_items for select to authenticated using (public.current_user_is_league_member(league_id));
create policy "score models authenticated read" on public.score_models for select to authenticated using (true);
create policy "trade events league members read" on public.trade_events for select to authenticated using (public.current_user_is_league_member(league_id));
create policy "trade sides league members read" on public.trade_event_sides for select to authenticated using (public.current_user_is_league_member(league_id));
create policy "trade players league members read" on public.trade_event_players for select to authenticated using (public.current_user_is_league_member(league_id));
create policy "acquisitions league members read" on public.acquisition_events for select to authenticated using (public.current_user_is_league_member(league_id));
create policy "acquisition grades league members read" on public.acquisition_grades for select to authenticated using (public.current_user_is_league_member(league_id));
create policy "manager scores league members read" on public.manager_score_snapshots for select to authenticated using (public.current_user_is_league_member(league_id));
create policy "data quality league members read" on public.data_quality_warnings for select to authenticated using (public.current_user_is_league_member(league_id));
create policy "league versions league members read" on public.league_current_versions for select to authenticated using (public.current_user_is_league_member(league_id));
create policy "share links league members read" on public.share_links for select to authenticated using (public.current_user_is_league_member(league_id));
create policy "share links league members insert" on public.share_links for insert to authenticated with check (created_by = auth.uid() and public.current_user_is_league_member(league_id));
create policy "share links creators revoke" on public.share_links for update to authenticated using (created_by = auth.uid() and public.current_user_is_league_member(league_id)) with check (created_by = auth.uid() and public.current_user_is_league_member(league_id));
create policy "audit events org members read" on public.audit_events for select to authenticated using (organization_id is not null and public.current_user_is_org_member(organization_id));
create policy "provider capabilities authenticated read" on public.provider_capabilities for select to authenticated using (true);

create policy "league credentials service writes" on public.league_credentials for all to service_role using (true) with check (true);

create policy "service writes import facts" on public.import_run_steps for all to service_role using (true) with check (true);
create policy "service writes source documents" on public.source_documents for all to service_role using (true) with check (true);
create policy "service writes storage artifacts" on public.storage_artifacts for all to service_role using (true) with check (true);
create policy "service writes players" on public.players for all to service_role using (true) with check (true);
create policy "service writes provider map" on public.provider_entity_map for all to service_role using (true) with check (true);
create policy "service writes matchups" on public.matchups for all to service_role using (true) with check (true);
create policy "service writes rosters" on public.roster_week_entries for all to service_role using (true) with check (true);
create policy "service writes player stats" on public.player_week_stats for all to service_role using (true) with check (true);
create policy "service writes transactions" on public.transactions for all to service_role using (true) with check (true);
create policy "service writes transaction items" on public.transaction_items for all to service_role using (true) with check (true);
create policy "service writes score models" on public.score_models for all to service_role using (true) with check (true);
create policy "service writes trade events" on public.trade_events for all to service_role using (true) with check (true);
create policy "service writes trade sides" on public.trade_event_sides for all to service_role using (true) with check (true);
create policy "service writes trade players" on public.trade_event_players for all to service_role using (true) with check (true);
create policy "service writes acquisitions" on public.acquisition_events for all to service_role using (true) with check (true);
create policy "service writes acquisition grades" on public.acquisition_grades for all to service_role using (true) with check (true);
create policy "service writes manager scores" on public.manager_score_snapshots for all to service_role using (true) with check (true);
create policy "service writes data quality" on public.data_quality_warnings for all to service_role using (true) with check (true);
create policy "service writes league versions" on public.league_current_versions for all to service_role using (true) with check (true);
create policy "service writes audit events" on public.audit_events for all to service_role using (true) with check (true);

create policy "private raw imports are readable by league members" on storage.objects
  for select to authenticated
  using (bucket_id = 'raw-imports' and public.current_user_can_read_storage_object(bucket_id, name));

create policy "private derived artifacts are readable by league members" on storage.objects
  for select to authenticated
  using (bucket_id = 'derived-artifacts' and public.current_user_can_read_storage_object(bucket_id, name));

create policy "share previews are readable by league members" on storage.objects
  for select to authenticated
  using (bucket_id = 'share-previews' and public.current_user_can_read_storage_object(bucket_id, name));

create policy "service role manages mygm storage" on storage.objects
  for all to service_role
  using (bucket_id in ('raw-imports', 'derived-artifacts', 'share-previews'))
  with check (bucket_id in ('raw-imports', 'derived-artifacts', 'share-previews'));

grant usage on schema auth to anon, authenticated, service_role;
grant usage on schema public to anon, authenticated, service_role;
grant usage on schema storage to anon, authenticated, service_role;
grant select, insert, update, delete on all tables in schema public to authenticated;
grant select on storage.objects to anon, authenticated;
grant all on all tables in schema public to service_role;
grant all on storage.objects to service_role;
