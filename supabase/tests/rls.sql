\set ON_ERROR_STOP on

begin;

set local role postgres;

insert into auth.users (id, aud, role, email, encrypted_password, email_confirmed_at, raw_app_meta_data, raw_user_meta_data, created_at, updated_at)
values
  ('00000000-0000-0000-0000-0000000000a1', 'authenticated', 'authenticated', 'alpha@example.com', crypt('password', gen_salt('bf')), now(), '{"provider":"email","providers":["email"]}'::jsonb, '{}'::jsonb, now(), now()),
  ('00000000-0000-0000-0000-0000000000b2', 'authenticated', 'authenticated', 'bravo@example.com', crypt('password', gen_salt('bf')), now(), '{"provider":"email","providers":["email"]}'::jsonb, '{}'::jsonb, now(), now());

insert into public.profiles (id, email)
values
  ('00000000-0000-0000-0000-0000000000a1', 'alpha@example.com'),
  ('00000000-0000-0000-0000-0000000000b2', 'bravo@example.com');

insert into public.organizations (id, name, created_by)
values
  ('10000000-0000-0000-0000-000000000001', 'Alpha Org', '00000000-0000-0000-0000-0000000000a1'),
  ('10000000-0000-0000-0000-000000000002', 'Bravo Org', '00000000-0000-0000-0000-0000000000b2');

insert into public.organization_members (organization_id, user_id, role)
values
  ('10000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-0000000000a1', 'owner'),
  ('10000000-0000-0000-0000-000000000002', '00000000-0000-0000-0000-0000000000b2', 'owner');

insert into public.leagues (id, organization_id, provider, provider_league_id, name, created_by)
values
  ('20000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001', 'espn', 'alpha-league', 'Alpha League', '00000000-0000-0000-0000-0000000000a1'),
  ('20000000-0000-0000-0000-000000000002', '10000000-0000-0000-0000-000000000002', 'espn', 'bravo-league', 'Bravo League', '00000000-0000-0000-0000-0000000000b2');

insert into public.league_members (league_id, user_id, role)
values
  ('20000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-0000000000a1', 'commissioner'),
  ('20000000-0000-0000-0000-000000000002', '00000000-0000-0000-0000-0000000000b2', 'commissioner');

insert into public.ingestion_runs (id, organization_id, league_id, requested_by, status)
values
  ('30000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-0000000000a1', 'succeeded'),
  ('30000000-0000-0000-0000-000000000002', '10000000-0000-0000-0000-000000000002', '20000000-0000-0000-0000-000000000002', '00000000-0000-0000-0000-0000000000b2', 'succeeded');

insert into public.source_documents (organization_id, league_id, ingestion_run_id, bucket_id, object_path, sha256, source_kind)
values
  ('10000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000001', '30000000-0000-0000-0000-000000000001', 'raw-imports', 'org/10000000-0000-0000-0000-000000000001/league/20000000-0000-0000-0000-000000000001/import/30000000-0000-0000-0000-000000000001/core.json', repeat('a', 64), 'core'),
  ('10000000-0000-0000-0000-000000000002', '20000000-0000-0000-0000-000000000002', '30000000-0000-0000-0000-000000000002', 'raw-imports', 'org/10000000-0000-0000-0000-000000000002/league/20000000-0000-0000-0000-000000000002/import/30000000-0000-0000-0000-000000000002/core.json', repeat('b', 64), 'core');

set local role authenticated;
set local request.jwt.claim.sub = '00000000-0000-0000-0000-0000000000a1';

do $$
begin
  if (select count(*) from public.organizations) <> 1 then
    raise exception 'user A should see only their org';
  end if;

  if (select count(*) from public.leagues) <> 1 then
    raise exception 'user A should see only their league';
  end if;

  if (select count(*) from public.source_documents) <> 1 then
    raise exception 'user A should see only their source documents';
  end if;

  if (select count(*) from public.ingestion_runs) <> 1 then
    raise exception 'user A should see only their ingestion runs';
  end if;

  if not exists (
    select 1
    from public.source_documents
    where league_id = '20000000-0000-0000-0000-000000000001'
  ) then
    raise exception 'user A should read own source rows';
  end if;
end;
$$;

rollback;

\echo RLS PASS
