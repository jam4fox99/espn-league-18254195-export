\set ON_ERROR_STOP on

begin;

set local role postgres;

insert into auth.users (id, aud, role, email, encrypted_password, email_confirmed_at, raw_app_meta_data, raw_user_meta_data, created_at, updated_at)
values
  ('00000000-0000-0000-0000-0000000000a1', 'authenticated', 'authenticated', 'owner@example.com', crypt('password', gen_salt('bf')), now(), '{"provider":"email","providers":["email"]}'::jsonb, '{}'::jsonb, now(), now()),
  ('00000000-0000-0000-0000-0000000000b2', 'authenticated', 'authenticated', 'invited@example.com', crypt('password', gen_salt('bf')), now(), '{"provider":"email","providers":["email"]}'::jsonb, '{}'::jsonb, now(), now()),
  ('00000000-0000-0000-0000-0000000000c3', 'authenticated', 'authenticated', 'outsider@example.com', crypt('password', gen_salt('bf')), now(), '{"provider":"email","providers":["email"]}'::jsonb, '{}'::jsonb, now(), now());

insert into public.profiles (id, email)
values
  ('00000000-0000-0000-0000-0000000000a1', 'owner@example.com'),
  ('00000000-0000-0000-0000-0000000000b2', 'invited@example.com'),
  ('00000000-0000-0000-0000-0000000000c3', 'outsider@example.com');

insert into public.organizations (id, name, created_by)
values ('10000000-0000-0000-0000-000000000001', 'Invite Org', '00000000-0000-0000-0000-0000000000a1');

insert into public.organization_members (organization_id, user_id, role)
values ('10000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-0000000000a1', 'owner');

insert into public.alpha_invites (id, organization_id, email, code, role, expires_at, created_by)
values ('50000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001', 'invited@example.com', 'INVITED-CODE', 'member', now() + interval '1 day', '00000000-0000-0000-0000-0000000000a1');

insert into public.leagues (id, organization_id, provider, provider_league_id, name, created_by)
values ('20000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001', 'espn', 'invite-league', 'Invite League', '00000000-0000-0000-0000-0000000000a1');

insert into public.league_members (league_id, user_id, role)
values ('20000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-0000000000a1', 'commissioner');

insert into public.managers (id, organization_id, league_id, provider, provider_manager_id, display_name)
values ('60000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000001', 'espn', 'manager-1', 'Invited Manager');

set local role authenticated;
set local request.jwt.claim.sub = '00000000-0000-0000-0000-0000000000c3';
set local request.jwt.claim.email = 'outsider@example.com';

do $$
begin
  update public.alpha_invites
  set status = 'accepted',
      accepted_by = '00000000-0000-0000-0000-0000000000c3',
      accepted_at = now()
  where code = 'INVITED-CODE';

  if found then
    raise exception 'uninvited user accepted another email invite';
  end if;
end;
$$;

set local request.jwt.claim.sub = '00000000-0000-0000-0000-0000000000b2';
set local request.jwt.claim.email = 'invited@example.com';

do $$
begin
  update public.alpha_invites
  set status = 'accepted',
      accepted_by = '00000000-0000-0000-0000-0000000000b2',
      accepted_at = now()
  where code = 'INVITED-CODE';

  if not found then
    raise exception 'invited email should accept invite';
  end if;

  insert into public.manager_claims (league_id, manager_id, user_id)
  values ('20000000-0000-0000-0000-000000000001', '60000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-0000000000b2');

  raise exception 'accepted invite alone should not create manager claim';
exception
  when insufficient_privilege then
    null;
end;
$$;

set local role postgres;
insert into public.organization_members (organization_id, user_id, role)
values ('10000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-0000000000b2', 'member');
insert into public.league_members (league_id, user_id, role)
values ('20000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-0000000000b2', 'manager');

set local role authenticated;
set local request.jwt.claim.sub = '00000000-0000-0000-0000-0000000000b2';
set local request.jwt.claim.email = 'invited@example.com';

insert into public.manager_claims (league_id, manager_id, user_id)
values ('20000000-0000-0000-0000-000000000001', '60000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-0000000000b2');

do $$
begin
  if (select count(*) from public.manager_claims where user_id = '00000000-0000-0000-0000-0000000000b2') <> 1 then
    raise exception 'league member should create own manager claim';
  end if;

  if (select status::text from public.manager_claims where user_id = '00000000-0000-0000-0000-0000000000b2') <> 'pending' then
    raise exception 'new manager claim should start pending';
  end if;
end;
$$;

rollback;

\echo INVITES PASS
