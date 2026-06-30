from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mygm_worker.analytics.models import ManagerIdentity
    from mygm_worker.analytics.standings import SeasonStandings, TeamStanding


@dataclass(frozen=True, slots=True)
class CareerSeasonLine:
    season: int
    team_name: str
    rank_final: int
    made_playoffs: bool
    is_champion: bool
    wins: int
    losses: int
    ties: int
    points_for: float
    rating_score: float | None


@dataclass(frozen=True, slots=True)
class CareerEra:
    kind: str  # "dynasty" | "drought"
    start_season: int
    end_season: int
    seasons: tuple[int, ...]
    titles: int
    summary: str


@dataclass(frozen=True, slots=True)
class ManagerCareer:
    manager_key: str
    display_name: str
    seasons_played: int
    wins: int
    losses: int
    ties: int
    win_pct: float
    points_for: float
    points_against: float
    titles: int
    runner_ups: int
    playoff_appearances: int
    best_finish: int | None
    worst_finish: int | None
    best_finish_season: int | None
    most_points_season: int | None
    avg_rating: float | None
    season_lines: tuple[CareerSeasonLine, ...]
    eras: tuple[CareerEra, ...]


def manager_careers(
    standings: tuple[SeasonStandings, ...],
    managers: dict[str, ManagerIdentity],
    season_rating: dict[tuple[str, int], float],
    career_rating: dict[str, float],
    included_seasons: tuple[int, ...],
) -> tuple[ManagerCareer, ...]:
    included = set(included_seasons)
    size_by_season = {season.season: len(season.standings) for season in standings}
    by_manager: dict[str, list[TeamStanding]] = {}
    for season in standings:
        if season.season not in included:
            continue
        for row in season.standings:
            if row.manager_key.startswith("unresolved:"):
                continue
            by_manager.setdefault(row.manager_key, []).append(row)
    careers = [
        _career(manager_key, rows, managers, season_rating, career_rating, size_by_season)
        for manager_key, rows in sorted(by_manager.items())
    ]
    return tuple(careers)


def _career(
    manager_key: str,
    rows: list[TeamStanding],
    managers: dict[str, ManagerIdentity],
    season_rating: dict[tuple[str, int], float],
    career_rating: dict[str, float],
    size_by_season: dict[int, int],
) -> ManagerCareer:
    ordered = sorted(rows, key=lambda row: row.season)
    manager = managers.get(manager_key)
    display_name = manager.display_name if manager else manager_key
    season_lines = tuple(_season_line(row, season_rating) for row in ordered)
    wins = sum(row.wins for row in ordered)
    losses = sum(row.losses for row in ordered)
    ties = sum(row.ties for row in ordered)
    games = wins + losses + ties
    finishes = [row.rank_final for row in ordered if row.rank_final > 0]
    best_row = min(ordered, key=lambda row: row.rank_final or 999, default=None)
    most_points_row = max(ordered, key=lambda row: row.points_for, default=None)
    return ManagerCareer(
        manager_key=manager_key,
        display_name=display_name,
        seasons_played=len(ordered),
        wins=wins,
        losses=losses,
        ties=ties,
        win_pct=round((wins + (ties / 2)) / games * 100, 4) if games else 0.0,
        points_for=round(sum(row.points_for for row in ordered), 4),
        points_against=round(sum(row.points_against for row in ordered), 4),
        titles=sum(1 for row in ordered if row.is_champion),
        runner_ups=sum(1 for row in ordered if row.is_runner_up),
        playoff_appearances=sum(1 for row in ordered if row.made_playoffs),
        best_finish=min(finishes) if finishes else None,
        worst_finish=max(finishes) if finishes else None,
        best_finish_season=best_row.season if best_row and best_row.rank_final > 0 else None,
        most_points_season=most_points_row.season if most_points_row else None,
        avg_rating=_rounded(career_rating.get(manager_key)),
        season_lines=season_lines,
        eras=_eras(ordered, size_by_season),
    )


def _season_line(
    row: TeamStanding,
    season_rating: dict[tuple[str, int], float],
) -> CareerSeasonLine:
    return CareerSeasonLine(
        season=row.season,
        team_name=row.team_name,
        rank_final=row.rank_final,
        made_playoffs=row.made_playoffs,
        is_champion=row.is_champion,
        wins=row.wins,
        losses=row.losses,
        ties=row.ties,
        points_for=round(row.points_for, 4),
        rating_score=_rounded(season_rating.get((row.manager_key, row.season))),
    )


def _eras(ordered: list[TeamStanding], size_by_season: dict[int, int]) -> tuple[CareerEra, ...]:
    eras: list[CareerEra] = []
    eras.extend(_runs(ordered, kind="dynasty", predicate=_is_top_tier))
    eras.extend(
        _runs(
            ordered,
            kind="drought",
            predicate=lambda row: _is_bottom_tier(row, size_by_season),
        )
    )
    return tuple(sorted(eras, key=lambda era: era.start_season))


def _runs(
    ordered: list[TeamStanding],
    *,
    kind: str,
    predicate: Callable[[TeamStanding], bool],
) -> list[CareerEra]:
    runs: list[CareerEra] = []
    current: list[TeamStanding] = []
    for row in ordered:
        qualifies = predicate(row)
        consecutive = bool(current) and row.season == current[-1].season + 1
        if qualifies and (not current or consecutive):
            current.append(row)
        elif qualifies:
            _flush(runs, current, kind)
            current = [row]
        else:
            _flush(runs, current, kind)
            current = []
    _flush(runs, current, kind)
    return runs


def _flush(runs: list[CareerEra], current: list[TeamStanding], kind: str) -> None:
    if len(current) < 2:
        return
    seasons = tuple(row.season for row in current)
    titles = sum(1 for row in current if row.is_champion)
    runs.append(
        CareerEra(
            kind=kind,
            start_season=seasons[0],
            end_season=seasons[-1],
            seasons=seasons,
            titles=titles,
            summary=_era_summary(kind, seasons, titles),
        )
    )


def _era_summary(kind: str, seasons: tuple[int, ...], titles: int) -> str:
    span = f"{seasons[0]}-{seasons[-1]}"
    if kind == "dynasty":
        title_text = f", {titles} title{'s' if titles != 1 else ''}" if titles else ""
        return f"Top-3 finishes {span}{title_text}"
    return f"Bottom-third finishes {span}"


def _is_top_tier(row: TeamStanding) -> bool:
    return row.rank_final in {1, 2, 3}


def _is_bottom_tier(row: TeamStanding, size_by_season: dict[int, int]) -> bool:
    size = size_by_season.get(row.season, 10)
    cutoff = size - (size // 3) + 1  # bottom third: e.g. 10 teams -> ranks 8-10
    return row.rank_final > 0 and row.rank_final >= cutoff


def _rounded(value: float | None) -> float | None:
    return round(value, 4) if value is not None else None
