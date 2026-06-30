\set ON_ERROR_STOP on

begin;

set local role postgres;

insert into auth.users (id, aud, role, email, encrypted_password, email_confirmed_at, raw_app_meta_data, raw_user_meta_data, created_at, updated_at)
values
  ('00000000-0000-0000-0000-0000000000a1', 'authenticated', 'authenticated', 'negative-alpha@example.com', crypt('password', gen_salt('bf')), now(), '{"provider":"email","providers":["email"]}'::jsonb, '{}'::jsonb, now(), now()),
  ('00000000-0000-0000-0000-0000000000b2', 'authenticated', 'authenticated', 'negative-bravo@example.com', crypt('password', gen_salt('bf')), now(), '{"provider":"email","providers":["email"]}'::jsonb, '{}'::jsonb, now(), now());

insert into public.profiles (id, email)
values
  ('00000000-0000-0000-0000-0000000000a1', 'negative-alpha@example.com'),
  ('00000000-0000-0000-0000-0000000000b2', 'negative-bravo@example.com');

insert into public.organizations (id, name, created_by)
values
  ('10000000-0000-0000-0000-000000000001', 'Negative Alpha Org', '00000000-0000-0000-0000-0000000000a1'),
  ('10000000-0000-0000-0000-000000000002', 'Negative Bravo Org', '00000000-0000-0000-0000-0000000000b2');

insert into public.organization_members (organization_id, user_id, role)
values
  ('10000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-0000000000a1', 'owner'),
  ('10000000-0000-0000-0000-000000000002', '00000000-0000-0000-0000-0000000000b2', 'owner');

insert into public.leagues (id, organization_id, provider, provider_league_id, name, created_by)
values
  ('20000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001', 'espn', 'negative-alpha', 'Negative Alpha League', '00000000-0000-0000-0000-0000000000a1'),
  ('20000000-0000-0000-0000-000000000002', '10000000-0000-0000-0000-000000000002', 'espn', 'negative-bravo', 'Negative Bravo League', '00000000-0000-0000-0000-0000000000b2');

insert into public.league_members (league_id, user_id, role)
values
  ('20000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-0000000000a1', 'commissioner'),
  ('20000000-0000-0000-0000-000000000002', '00000000-0000-0000-0000-0000000000b2', 'commissioner');

set local role authenticated;
set local request.jwt.claim.sub = '00000000-0000-0000-0000-0000000000a1';

do $$
begin
  if exists (
    select 1
    from public.leagues
    where id = '20000000-0000-0000-0000-000000000002'
  ) then
    raise exception 'cross tenant read leaked rows';
  end if;
end;
$$;

rollback;

\echo NEGATIVE CROSS TENANT READ PASS
