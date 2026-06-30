\set ON_ERROR_STOP on

begin;

do $$
begin
  if (
    select count(*)
    from information_schema.columns
    where table_schema = 'public'
      and table_name = 'league_credentials'
      and column_name in ('swid', 'espn_s2', 'password', 'secret', 'plaintext', 'cookie')
  ) <> 0 then
    raise exception 'league_credentials has plaintext ESPN credential columns';
  end if;

  if (
    select count(*)
    from information_schema.columns
    where table_schema = 'public'
      and table_name = 'league_credentials'
      and column_name in ('credential_version', 'key_id', 'nonce', 'ciphertext', 'expires_at', 'rotated_at', 'last_validated_at', 'status', 'consent_version', 'authorized_by', 'created_by')
  ) <> 11 then
    raise exception 'league_credentials does not expose ciphertext metadata contract';
  end if;

  if (
    select count(*)
    from storage.buckets
    where id in ('raw-imports', 'derived-artifacts')
      and public = false
  ) <> 2 then
    raise exception 'raw and derived buckets should be private';
  end if;

  if (
    select count(*)
    from public.provider_capabilities
    where provider in ('sleeper', 'yahoo')
      and status = 'post_mvp'
  ) <> 2 then
    raise exception 'Sleeper and Yahoo should be post-MVP provider capabilities only';
  end if;
end;
$$;

rollback;

\echo CONSTRAINTS PASS
