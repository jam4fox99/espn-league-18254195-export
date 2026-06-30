from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from mygm_worker.analytics.json_tools import array_field, string_value

if TYPE_CHECKING:
    from mygm_worker.analytics.models import JsonObject
    from mygm_worker.analytics.reader import FixtureReader


@dataclass(slots=True)
class _OwnerLogos:
    seasons_played: set[int] = field(default_factory=set)
    logo_by_season: dict[int, str] = field(default_factory=dict)


def build_logo_index(reader: FixtureReader) -> dict[str, JsonObject]:
    """Map each resolved ``espn-owner:`` managerKey to its season logo timeline.

    Owners are grouped by their ESPN GUID (``primaryOwner`` / first ``owners`` entry), never
    by ``team.id`` which is reused across seasons. Teams without a GUID are skipped, so
    unresolved-owner managers receive no logo entry.
    """
    owners: dict[str, _OwnerLogos] = {}
    for season in reader.seasons():
        core = reader.core(season.season)
        for team in array_field(core, "teams"):
            owner_id = _team_owner(team)
            if not owner_id:
                continue
            record = owners.setdefault(owner_id, _OwnerLogos())
            record.seasons_played.add(season.season)
            logo = string_value(team.get("logo"))
            if logo:
                record.logo_by_season[season.season] = logo
    return {
        f"espn-owner:{owner_id}": _logo_json(record)
        for owner_id, record in owners.items()
    }


def _logo_json(record: _OwnerLogos) -> JsonObject:
    main_season = max(record.seasons_played)
    return {
        "main": record.logo_by_season.get(main_season),
        "mainSeason": main_season,
        "bySeason": {
            str(season): record.logo_by_season[season]
            for season in sorted(record.logo_by_season)
        },
    }


def _team_owner(team: JsonObject) -> str:
    primary_owner = string_value(team.get("primaryOwner"))
    if primary_owner:
        return primary_owner
    owners = team.get("owners")
    if isinstance(owners, list) and owners:
        return string_value(owners[0])
    return ""
