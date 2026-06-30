from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

from mygm_worker.analytics.json_tools import (
    array_field,
    float_value,
    int_value,
    object_field,
    string_value,
)
from mygm_worker.analytics.models import (
    JsonObject,
    JsonValue,
    ManagerIdentity,
    ManagerIdentitySummary,
    TeamSeason,
)

if TYPE_CHECKING:
    from mygm_worker.analytics.reader import FixtureReader


def load_team_seasons(
    reader: FixtureReader,
) -> tuple[dict[str, ManagerIdentity], list[TeamSeason]]:
    managers: dict[str, ManagerIdentity] = {}
    team_seasons: list[TeamSeason] = []
    for season in reader.seasons():
        core = reader.core(season.season)
        member_names = _member_names(core)
        for team in array_field(core, "teams"):
            team_id = int_value(team.get("id"))
            owner_id = _team_owner(team)
            manager_key = (
                f"espn-owner:{owner_id}"
                if owner_id
                else f"unresolved:{season.season}:{team_id}"
            )
            display_name = member_names.get(owner_id, f"Unresolved owner {team_id}")
            if manager_key not in managers:
                managers[manager_key] = ManagerIdentity(
                    manager_key=manager_key,
                    display_name=display_name,
                    owner_id=owner_id,
                    is_unresolved=owner_id == "",
                )
            record = object_field(object_field(team, "record"), "overall")
            team_seasons.append(
                TeamSeason(
                    season=season.season,
                    team_id=team_id,
                    team_name=_team_name(team),
                    manager_key=manager_key,
                    wins=int_value(record.get("wins")),
                    losses=int_value(record.get("losses")),
                    ties=int_value(record.get("ties")),
                    points_for=float_value(record.get("pointsFor")),
                    points_against=float_value(record.get("pointsAgainst")),
                    source_file=str(reader.root / f"season_{season.season}" / "core.json"),
                )
            )
    return managers, team_seasons


def manager_summary(
    managers: dict[str, ManagerIdentity],
    team_seasons: list[TeamSeason],
) -> ManagerIdentitySummary:
    unresolved = sum(1 for manager in managers.values() if manager.is_unresolved)
    return ManagerIdentitySummary(
        manager_count=len(managers),
        unresolved_owner_buckets=unresolved,
        team_season_count=len(team_seasons),
        all_team_seasons_mapped=len(team_seasons) > 0 and unresolved == 0,
    )


def manager_rows(
    *,
    managers: dict[str, ManagerIdentity],
    team_seasons: list[TeamSeason],
) -> list[JsonObject]:
    aliases = _team_aliases(team_seasons)
    return [
        _manager_row(manager, aliases.get(manager.manager_key, []))
        for manager in sorted(managers.values(), key=lambda item: item.manager_key)
    ]


def _member_names(core: JsonObject) -> dict[str, str]:
    names: dict[str, str] = {}
    for member in array_field(core, "members"):
        member_id = string_value(member.get("id"))
        display_name = string_value(member.get("displayName"))
        first_name = string_value(member.get("firstName"))
        last_name = string_value(member.get("lastName"))
        full_name = " ".join(part for part in (first_name, last_name) if part)
        names[member_id] = full_name or display_name or member_id
    return names


def _manager_row(
    manager: ManagerIdentity,
    aliases: list[JsonValue],
) -> JsonObject:
    caveats: list[JsonValue] = (
        ["missing ESPN owner data; score excluded"] if manager.is_unresolved else []
    )
    return {
        "managerKey": manager.manager_key,
        "displayName": manager.display_name,
        "ownerId": manager.owner_id,
        "aliases": aliases,
        "scoreEligible": not manager.is_unresolved,
        "caveats": caveats,
    }


def _team_aliases(team_seasons: list[TeamSeason]) -> dict[str, list[JsonValue]]:
    aliases: defaultdict[str, list[JsonValue]] = defaultdict(list)
    for row in sorted(
        team_seasons,
        key=lambda item: (item.manager_key, item.season, item.team_id),
    ):
        aliases[row.manager_key].append(
            {
                "season": row.season,
                "teamId": row.team_id,
                "teamName": row.team_name,
            }
        )
    return dict(aliases)


def _team_owner(team: JsonObject) -> str:
    primary_owner = string_value(team.get("primaryOwner"))
    if primary_owner:
        return primary_owner
    owners = team.get("owners")
    if isinstance(owners, list) and owners:
        return string_value(owners[0])
    return ""


def _team_name(team: JsonObject) -> str:
    name = string_value(team.get("name"))
    if name:
        return name
    location = string_value(team.get("location"))
    nickname = string_value(team.get("nickname"))
    combined = " ".join(part for part in (location, nickname) if part)
    return combined or f"Team {int_value(team.get('id'))}"
