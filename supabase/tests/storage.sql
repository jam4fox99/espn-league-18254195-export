\set ON_ERROR_STOP on

begin;

set local role postgres;

insert into auth.users (id, aud, role, email, encrypted_password, email_confirmed_at, raw_app_meta_data, raw_user_meta_data, created_at, updated_at)
values ('00000000-0000-0000-0000-0000000000a1', 'authenticated', 'authenticated', 'alpha-storage@example.com', crypt('password', gen_salt('bf')), now(), '{"provider":"email","providers":["email"]}'::jsonb, '{}'::jsonb, now(), now());

insert into public.profiles (id, email)
values ('00000000-0000-0000-0000-0000000000a1', 'alpha-storage@example.com');

insert into public.organizations (id, name, created_by)
values ('10000000-0000-0000-0000-000000000001', 'Alpha Storage Org', '00000000-0000-0000-0000-0000000000a1');

insert into public.organization_members (organization_id, user_id, role)
values ('10000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-0000000000a1', 'owner');

insert into public.leagues (id, organization_id, provider, provider_league_id, name, created_by)
values ('20000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001', 'espn', 'alpha-storage', 'Alpha Storage League', '00000000-0000-0000-0000-0000000000a1');

insert into public.league_members (league_id, user_id, role)
values ('20000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-0000000000a1', 'commissioner');

insert into storage.objects (id, bucket_id, name, owner)
values
  ('40000000-0000-0000-0000-000000000001', 'raw-imports', 'org/10000000-0000-0000-0000-000000000001/league/20000000-0000-0000-0000-000000000001/import/30000000-0000-0000-0000-000000000001/core.json', '00000000-0000-0000-0000-0000000000a1'),
  ('40000000-0000-0000-0000-000000000002', 'derived-artifacts', 'league/20000000-0000-0000-0000-000000000001/source_import/30000000-0000-0000-0000-000000000001/transform/v1/summary.json', '00000000-0000-0000-0000-0000000000a1');

set local role anon;
do $$
begin
  if (select count(*) from storage.objects where bucket_id = 'raw-imports') <> 0 then
    raise exception 'anon should not read raw imports';
  end if;

  if (select count(*) from storage.objects where bucket_id = 'derived-artifacts') <> 0 then
    raise exception 'anon should not read derived artifacts';
  end if;
end;
$$;

set local role authenticated;
set local request.jwt.claim.sub = '00000000-0000-0000-0000-0000000000a1';

do $$
begin
  if (select count(*) from storage.objects where bucket_id = 'raw-imports') <> 1 then
    raise exception 'league member should read raw imports';
  end if;

  if (select count(*) from storage.objects where bucket_id = 'derived-artifacts') <> 1 then
    raise exception 'league member should read derived artifacts';
  end if;
end;
$$;

rollback;

\echo STORAGE PASS
