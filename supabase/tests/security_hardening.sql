\set ON_ERROR_STOP on

begin;

set local role postgres;

insert into auth.users (id, aud, role, email, encrypted_password, email_confirmed_at, raw_app_meta_data, raw_user_meta_data, created_at, updated_at)
values
  ('00000000-0000-0000-0000-0000000000a1', 'authenticated', 'authenticated', 'owner-a@example.com', crypt('password', gen_salt('bf')), now(), '{"provider":"email","providers":["email"]}'::jsonb, '{}'::jsonb, now(), now()),
  ('00000000-0000-0000-0000-0000000000b2', 'authenticated', 'authenticated', 'owner-b@example.com', crypt('password', gen_salt('bf')), now(), '{"provider":"email","providers":["email"]}'::jsonb, '{}'::jsonb, now(), now()),
  ('00000000-0000-0000-0000-0000000000c3', 'authenticated', 'authenticated', 'invited@example.com', crypt('password', gen_salt('bf')), now(), '{"provider":"email","providers":["email"]}'::jsonb, '{}'::jsonb, now(), now()),
  ('00000000-0000-0000-0000-0000000000d4', 'authenticated', 'authenticated', 'outsider@example.com', crypt('password', gen_salt('bf')), now(), '{"provider":"email","providers":["email"]}'::jsonb, '{}'::jsonb, now(), now());

insert into public.profiles (id, email, display_name)
values
  ('00000000-0000-0000-0000-0000000000a1', 'owner-a@example.com', 'Owner A'),
  ('00000000-0000-0000-0000-0000000000b2', 'owner-b@example.com', 'Owner B'),
  ('00000000-0000-0000-0000-0000000000c3', 'invited@example.com', 'Invited User'),
  ('00000000-0000-0000-0000-0000000000d4', 'outsider@example.com', 'Outsider');

insert into public.organizations (id, name, created_by)
values
  ('10000000-0000-0000-0000-000000000001', 'Org A', '00000000-0000-0000-0000-0000000000a1'),
  ('10000000-0000-0000-0000-000000000002', 'Org B', '00000000-0000-0000-0000-0000000000b2');

insert into public.organization_members (organization_id, user_id, role)
values
  ('10000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-0000000000a1', 'owner'),
  ('10000000-0000-0000-0000-000000000002', '00000000-0000-0000-0000-0000000000b2', 'owner');

insert into public.leagues (id, organization_id, provider, provider_league_id, name, created_by)
values
  ('20000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001', 'espn', 'league-a', 'League A', '00000000-0000-0000-0000-0000000000a1'),
  ('20000000-0000-0000-0000-000000000002', '10000000-0000-0000-0000-000000000002', 'espn', 'league-b', 'League B', '00000000-0000-0000-0000-0000000000b2');

insert into public.league_members (league_id, user_id, role)
values
  ('20000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-0000000000a1', 'commissioner'),
  ('20000000-0000-0000-0000-000000000002', '00000000-0000-0000-0000-0000000000b2', 'commissioner');

insert into public.managers (id, organization_id, league_id, provider, provider_manager_id, display_name)
values
  ('60000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000001', 'espn', 'manager-a', 'Manager A'),
  ('60000000-0000-0000-0000-000000000002', '10000000-0000-0000-0000-000000000002', '20000000-0000-0000-0000-000000000002', 'espn', 'manager-b', 'Manager B');

insert into public.ingestion_runs (id, organization_id, league_id, requested_by, status)
values
  ('30000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-0000000000a1', 'succeeded'),
  ('30000000-0000-0000-0000-000000000002', '10000000-0000-0000-0000-000000000002', '20000000-0000-0000-0000-000000000002', '00000000-0000-0000-0000-0000000000b2', 'succeeded');

insert into public.source_documents (organization_id, league_id, ingestion_run_id, bucket_id, object_path, sha256, source_kind)
values
  ('10000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000001', '30000000-0000-0000-0000-000000000001', 'raw-imports', 'org/10000000-0000-0000-0000-000000000001/league/20000000-0000-0000-0000-000000000001/import/30000000-0000-0000-0000-000000000001/core.json', repeat('a', 64), 'core'),
  ('10000000-0000-0000-0000-000000000002', '20000000-0000-0000-0000-000000000002', '30000000-0000-0000-0000-000000000002', 'raw-imports', 'org/10000000-0000-0000-0000-000000000002/league/20000000-0000-0000-0000-000000000002/import/30000000-0000-0000-0000-000000000002/core.json', repeat('b', 64), 'core');

insert into public.storage_artifacts (organization_id, league_id, ingestion_run_id, bucket_id, object_path, artifact_kind, transform_version, sha256)
values
  ('10000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000001', '30000000-0000-0000-0000-000000000001', 'derived-artifacts', 'league/20000000-0000-0000-0000-000000000001/source_import/30000000-0000-0000-0000-000000000001/transform/v1/summary.json', 'summary', 'v1', repeat('c', 64)),
  ('10000000-0000-0000-0000-000000000002', '20000000-0000-0000-0000-000000000002', '30000000-0000-0000-0000-000000000002', 'derived-artifacts', 'league/20000000-0000-0000-0000-000000000002/source_import/30000000-0000-0000-0000-000000000002/transform/v1/summary.json', 'summary', 'v1', repeat('d', 64));

insert into public.league_credentials (organization_id, league_id, credential_version, key_id, nonce, ciphertext, expires_at, status, consent_version, authorized_by, created_by)
values
  ('10000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000001', 1, 'key-v1', decode('00112233445566778899aabb', 'hex'), decode('deadbeef', 'hex'), now() + interval '7 days', 'active', 'consent-v1', '00000000-0000-0000-0000-0000000000a1', '00000000-0000-0000-0000-0000000000a1');

insert into public.share_links (id, organization_id, league_id, manager_id, slug, token_hash, status, expires_at, created_by)
values
  ('70000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000001', '60000000-0000-0000-0000-000000000001', 'share-a', encode(digest('share-token-a', 'sha256'), 'hex'), 'active', now() + interval '7 days', '00000000-0000-0000-0000-0000000000a1');

insert into storage.objects (id, bucket_id, name, owner)
values
  ('40000000-0000-0000-0000-000000000001', 'raw-imports', 'org/10000000-0000-0000-0000-000000000001/league/20000000-0000-0000-0000-000000000001/import/30000000-0000-0000-0000-000000000001/core.json', '00000000-0000-0000-0000-0000000000a1'),
  ('40000000-0000-0000-0000-000000000002', 'derived-artifacts', 'league/20000000-0000-0000-0000-000000000001/source_import/30000000-0000-0000-0000-000000000001/transform/v1/summary.json', '00000000-0000-0000-0000-0000000000a1'),
  ('40000000-0000-0000-0000-000000000003', 'share-previews', 'league/20000000-0000-0000-0000-000000000001/share/share-a/card.png', '00000000-0000-0000-0000-0000000000a1');

insert into public.alpha_invites (id, organization_id, email, code, role, status, expires_at, created_by)
values
  ('50000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001', 'invited@example.com', 'LIVE-CODE', 'member', 'pending', now() + interval '1 day', '00000000-0000-0000-0000-0000000000a1'),
  ('50000000-0000-0000-0000-000000000002', '10000000-0000-0000-0000-000000000001', 'invited@example.com', 'EXPIRED-CODE', 'member', 'pending', now() - interval '1 day', '00000000-0000-0000-0000-0000000000a1'),
  ('50000000-0000-0000-0000-000000000003', '10000000-0000-0000-0000-000000000001', 'invited@example.com', 'REVOKED-CODE', 'member', 'revoked', now() + interval '1 day', '00000000-0000-0000-0000-0000000000a1');

do $$
begin
  if exists (
    select 1
    from information_schema.columns
    where table_schema = 'public'
      and table_name = 'league_credentials'
      and column_name in ('swid', 'espn_s2', 'password', 'secret', 'plaintext', 'cookie')
  ) then
    raise exception 'league_credentials contains plaintext credential-like columns';
  end if;

  if (
    select count(*)
    from information_schema.columns
    where table_schema = 'public'
      and table_name = 'league_credentials'
      and column_name in ('credential_version', 'key_id', 'nonce', 'ciphertext', 'expires_at', 'rotated_at', 'last_validated_at', 'status', 'consent_version', 'authorized_by', 'created_by')
  ) <> 11 then
    raise exception 'league_credentials ciphertext metadata contract changed';
  end if;
end;
$$;

set local role authenticated;
set local request.jwt.claim.sub = '00000000-0000-0000-0000-0000000000a1';

do $$
begin
  if (select count(*) from public.leagues) <> 1 then
    raise exception 'user A should see exactly one league';
  end if;

  if exists (select 1 from public.leagues where id = '20000000-0000-0000-0000-000000000002') then
    raise exception 'cross-tenant league read leaked';
  end if;

  if (select count(*) from public.source_documents) <> 1 then
    raise exception 'user A should see exactly one source document';
  end if;

  if (select count(*) from public.storage_artifacts) <> 1 then
    raise exception 'user A should see exactly one storage artifact';
  end if;

  if (select count(*) from public.league_credentials) <> 0 then
    raise exception 'authenticated users must not read league_credentials';
  end if;
end;
$$;

set local role service_role;

do $$
begin
  if (select count(*) from public.league_credentials) <> 1 then
    raise exception 'service_role should read league_credentials for API/worker internals';
  end if;
end;
$$;

set local role anon;

do $$
begin
  if (select count(*) from storage.objects where bucket_id in ('raw-imports', 'derived-artifacts', 'share-previews')) <> 0 then
    raise exception 'anon should not read private storage buckets or share previews directly';
  end if;
end;
$$;

set local role authenticated;
set local request.jwt.claim.sub = '00000000-0000-0000-0000-0000000000d4';

do $$
begin
  if (select count(*) from storage.objects where bucket_id in ('raw-imports', 'derived-artifacts', 'share-previews')) <> 0 then
    raise exception 'non-member should not read private storage buckets or share previews';
  end if;

  insert into public.manager_claims (league_id, manager_id, user_id)
  values ('20000000-0000-0000-0000-000000000001', '60000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-0000000000d4');

  raise exception 'non-member should not create manager claim';
exception
  when insufficient_privilege then
    null;
end;
$$;

set local request.jwt.claim.sub = '00000000-0000-0000-0000-0000000000a1';

do $$
begin
  if (select count(*) from storage.objects where bucket_id = 'raw-imports') <> 1 then
    raise exception 'league member should read own raw import object';
  end if;

  if (select count(*) from storage.objects where bucket_id = 'derived-artifacts') <> 1 then
    raise exception 'league member should read own derived artifact object';
  end if;

  if (select count(*) from storage.objects where bucket_id = 'share-previews') <> 1 then
    raise exception 'league member should read active share preview object';
  end if;
end;
$$;

set local request.jwt.claim.sub = '00000000-0000-0000-0000-0000000000d4';

do $$
begin
  update public.alpha_invites
  set status = 'accepted',
      accepted_by = '00000000-0000-0000-0000-0000000000d4',
      accepted_at = now()
  where code = 'LIVE-CODE';

  if found then
    raise exception 'wrong email should not accept live invite';
  end if;
end;
$$;

set local request.jwt.claim.sub = '00000000-0000-0000-0000-0000000000c3';

do $$
begin
  update public.alpha_invites
  set status = 'accepted',
      accepted_by = '00000000-0000-0000-0000-0000000000c3',
      accepted_at = now()
  where code = 'EXPIRED-CODE';

  if found then
    raise exception 'expired invite should not be accepted';
  end if;

  update public.alpha_invites
  set status = 'accepted',
      accepted_by = '00000000-0000-0000-0000-0000000000c3',
      accepted_at = now()
  where code = 'REVOKED-CODE';

  if found then
    raise exception 'revoked invite should not be accepted';
  end if;

  update public.alpha_invites
  set status = 'accepted',
      accepted_by = '00000000-0000-0000-0000-0000000000c3',
      accepted_at = now()
  where code = 'LIVE-CODE';

  if not found then
    raise exception 'matching live invite should be accepted';
  end if;

  update public.alpha_invites
  set accepted_at = now()
  where code = 'LIVE-CODE';

  if found then
    raise exception 'accepted invite should not be reusable by invitee';
  end if;
end;
$$;

set local role postgres;

insert into public.organization_members (organization_id, user_id, role)
values ('10000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-0000000000c3', 'member');
insert into public.league_members (league_id, user_id, role)
values ('20000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-0000000000c3', 'manager');

set local role authenticated;
set local request.jwt.claim.sub = '00000000-0000-0000-0000-0000000000c3';

insert into public.manager_claims (league_id, manager_id, user_id)
values ('20000000-0000-0000-0000-000000000001', '60000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-0000000000c3');

do $$
begin
  if (select count(*) from public.manager_claims where user_id = '00000000-0000-0000-0000-0000000000c3') <> 1 then
    raise exception 'league member should create own manager claim';
  end if;
end;
$$;

rollback;

\echo SECURITY HARDENING PASS
