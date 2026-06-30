from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class StoragePathSet:
    raw_bucket: str
    raw_prefix: str
    derived_bucket: str
    derived_prefix: str
    share_bucket: str
    share_prefix: str


def contract_storage_paths(
    organization_id: str,
    league_id: str,
    run_id: str,
    version_id: str,
    share_slug: str,
) -> StoragePathSet:
    return StoragePathSet(
        raw_bucket="raw-imports",
        raw_prefix=f"org/{organization_id}/league/{league_id}/import/{run_id}/raw",
        derived_bucket="derived-artifacts",
        derived_prefix=f"org/{organization_id}/league/{league_id}/version/{version_id}",
        share_bucket="share-previews",
        share_prefix=f"share/{share_slug}/{version_id}/og.png",
    )
