from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from mygm_worker.analytics.identity import load_team_seasons
from mygm_worker.analytics.json_tools import int_value

if TYPE_CHECKING:
    from mygm_worker.analytics.models import ManagerIdentity, TeamSeason
    from mygm_worker.analytics.reader import FixtureReader

DEFAULT_PLAYOFF_TEAM_COUNT = 6


@dataclass(frozen=True, slots=True)
class TeamStanding:
    season: int
    team_id: int
    manager_key: str
    display_name: str
    team_name: str
    rank_final: int
    playoff_seed: int
    made_playoffs: bool
    is_champion: bool
    is_runner_up: bool
    wins: int
    losses: int
    ties: int
    points_for: float
    points_against: float


@dataclass(frozen=True, slots=True)
class SeasonStandings:
    season: int
    is_partial: bool
    playoff_team_count: int
    champion_manager_key: str | None
    champion_display_name: str | None
    champion_team_name: str | None
    runner_up_manager_key: str | None
    runner_up_display_name: str | None
    standings: tuple[TeamStanding, ...]


def season_standings(
    reader: FixtureReader,
    managers: dict[str, ManagerIdentity],
    team_seasons: list[TeamSeason],
) -> tuple[SeasonStandings, ...]:
    partial_by_season = {season.season: season.is_partial for season in reader.seasons()}
    rank_lookup = _rank_lookup(reader)
    by_season: dict[int, list[TeamStanding]] = {}
    playoff_counts: dict[int, int] = {}
    for team in team_seasons:
        ranks = rank_lookup.get((team.season, team.team_id), (0, 0))
        rank_final, playoff_seed = ranks
        playoff_count = _playoff_team_count(reader, team.season)
        playoff_counts[team.season] = playoff_count
        is_partial = partial_by_season.get(team.season, False)
        made_playoffs = (not is_partial) and 1 <= playoff_seed <= playoff_count
        by_season.setdefault(team.season, []).append(
            TeamStanding(
                season=team.season,
                team_id=team.team_id,
                manager_key=team.manager_key,
                display_name=_display_name(managers, team.manager_key),
                team_name=team.team_name,
                rank_final=rank_final,
                playoff_seed=playoff_seed,
                made_playoffs=made_playoffs,
                is_champion=(not is_partial) and rank_final == 1,
                is_runner_up=(not is_partial) and rank_final == 2,
                wins=team.wins,
                losses=team.losses,
                ties=team.ties,
                points_for=team.points_for,
                points_against=team.points_against,
            )
        )
    return tuple(
        _season_standings(
            season,
            partial_by_season.get(season, False),
            playoff_counts.get(season, DEFAULT_PLAYOFF_TEAM_COUNT),
            rows,
        )
        for season, rows in sorted(by_season.items())
    )


def _season_standings(
    season: int,
    is_partial: bool,
    playoff_team_count: int,
    rows: list[TeamStanding],
) -> SeasonStandings:
    ordered = tuple(sorted(rows, key=_standing_sort_key))
    champion = next((row for row in ordered if row.is_champion), None)
    runner_up = next((row for row in ordered if row.is_runner_up), None)
    return SeasonStandings(
        season=season,
        is_partial=is_partial,
        playoff_team_count=playoff_team_count,
        champion_manager_key=champion.manager_key if champion else None,
        champion_display_name=champion.display_name if champion else None,
        champion_team_name=champion.team_name if champion else None,
        runner_up_manager_key=runner_up.manager_key if runner_up else None,
        runner_up_display_name=runner_up.display_name if runner_up else None,
        standings=ordered,
    )


def _standing_sort_key(row: TeamStanding) -> tuple[int, float]:
    # rankFinal of 0 means "not yet decided" (partial season); push to the back
    # and fall back to points-for so partial-season tables still read sensibly.
    rank = row.rank_final if row.rank_final > 0 else 999
    return (rank, -row.points_for)


def _rank_lookup(reader: FixtureReader) -> dict[tuple[int, int], tuple[int, int]]:
    lookup: dict[tuple[int, int], tuple[int, int]] = {}
    for season in reader.seasons():
        core = reader.core(season.season)
        teams = core.get("teams")
        if not isinstance(teams, list):
            continue
        for team in teams:
            if not isinstance(team, dict):
                continue
            team_id = int_value(team.get("id"))
            lookup[(season.season, team_id)] = (
                int_value(team.get("rankCalculatedFinal")),
                int_value(team.get("playoffSeed")),
            )
    return lookup


def _playoff_team_count(reader: FixtureReader, season: int) -> int:
    core = reader.core(season)
    settings = core.get("settings")
    if not isinstance(settings, dict):
        return DEFAULT_PLAYOFF_TEAM_COUNT
    schedule = settings.get("scheduleSettings")
    if not isinstance(schedule, dict):
        return DEFAULT_PLAYOFF_TEAM_COUNT
    count = int_value(schedule.get("playoffTeamCount"))
    return count if count > 0 else DEFAULT_PLAYOFF_TEAM_COUNT


def _display_name(managers: dict[str, ManagerIdentity], manager_key: str) -> str:
    manager = managers.get(manager_key)
    return manager.display_name if manager is not None else manager_key


def standings_for_fixture(reader: FixtureReader) -> tuple[SeasonStandings, ...]:
    managers, team_seasons = load_team_seasons(reader)
    return season_standings(reader, managers, team_seasons)
