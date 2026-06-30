from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, Literal

from mygm_worker.analytics.json_tools import (
    as_object,
    float_value,
    int_value,
    object_field,
    read_json,
    string_value,
)

if TYPE_CHECKING:
    from pathlib import Path

    from mygm_worker.analytics.models import JsonValue, TeamSeason
    from mygm_worker.analytics.reader import FixtureReader

type MatchupResult = Literal["A", "B", "TIE"]

PLAYOFF_TIERS: Final = frozenset(
    {
        "WINNERS_BRACKET",
        "WINNERS_CONSOLATION_LADDER",
        "LOSERS_CONSOLATION_LADDER",
    }
)


@dataclass(frozen=True, slots=True)
class MatchupRow:
    season: int
    week: int
    team_a_id: int
    team_b_id: int
    team_a_score: float
    team_b_score: float
    result: MatchupResult
    is_playoff: bool


@dataclass(frozen=True, slots=True)
class HeadToHeadPair:
    pair_id: str
    manager_a_key: str
    manager_b_key: str
    matchups: tuple[MatchupRow, ...]
    wins_a: int
    wins_b: int
    ties: int
    average_score_a: float
    average_score_b: float
    biggest_win_margin: float
    current_streak: str
    playoff_wins_a: int
    playoff_wins_b: int
    playoff_ties: int
    caveats: tuple[str, ...]


def head_to_head_pairs(
    reader: FixtureReader,
    team_seasons: list[TeamSeason],
    included_seasons: tuple[int, ...],
) -> tuple[HeadToHeadPair, ...]:
    team_lookup = _team_lookup(team_seasons)
    grouped: dict[tuple[str, str], list[MatchupRow]] = {}
    for matchup in matchup_rows(reader, included_seasons):
        team_a = team_lookup.get((matchup.season, matchup.team_a_id))
        team_b = team_lookup.get((matchup.season, matchup.team_b_id))
        if team_a is None or team_b is None:
            continue
        manager_a, manager_b = sorted((team_a.manager_key, team_b.manager_key))
        grouped.setdefault((manager_a, manager_b), []).append(matchup)
    return tuple(
        _pair(manager_a, manager_b, tuple(sorted(rows, key=_matchup_order)))
        for (manager_a, manager_b), rows in sorted(grouped.items())
    )


def matchup_rows(
    reader: FixtureReader,
    included_seasons: tuple[int, ...],
) -> tuple[MatchupRow, ...]:
    return tuple(
        row
        for row in _all_matchup_rows(reader.root, included_seasons)
        if row.team_a_id != row.team_b_id
    )


def _pair(
    manager_a_key: str,
    manager_b_key: str,
    matchups: tuple[MatchupRow, ...],
) -> HeadToHeadPair:
    wins_a = sum(1 for row in matchups if row.result == "A")
    wins_b = sum(1 for row in matchups if row.result == "B")
    ties = sum(1 for row in matchups if row.result == "TIE")
    playoff_rows = tuple(row for row in matchups if row.is_playoff)
    return HeadToHeadPair(
        pair_id=f"{manager_a_key}:{manager_b_key}",
        manager_a_key=manager_a_key,
        manager_b_key=manager_b_key,
        matchups=matchups,
        wins_a=wins_a,
        wins_b=wins_b,
        ties=ties,
        average_score_a=round(_average(row.team_a_score for row in matchups), 4),
        average_score_b=round(_average(row.team_b_score for row in matchups), 4),
        biggest_win_margin=round(max(_margin(row) for row in matchups), 4),
        current_streak=_current_streak(matchups),
        playoff_wins_a=sum(1 for row in playoff_rows if row.result == "A"),
        playoff_wins_b=sum(1 for row in playoff_rows if row.result == "B"),
        playoff_ties=sum(1 for row in playoff_rows if row.result == "TIE"),
        caveats=(),
    )


def _all_matchup_rows(root: Path, included_seasons: tuple[int, ...]) -> Iterator[MatchupRow]:
    for season in sorted(included_seasons):
        season_dir = root / f"season_{season}"
        if not season_dir.is_dir():
            continue
        for week_path in sorted((season_dir / "box_scores").glob("week_*.json")):
            payload = as_object(read_json(week_path), str(week_path))
            data = object_field(payload, "data")
            schedules = data.get("schedule")
            if not isinstance(schedules, list):
                continue
            for raw_matchup in schedules:
                yield from _matchup_from_json(season, raw_matchup)


def _matchup_from_json(season: int, raw_matchup: JsonValue) -> Iterator[MatchupRow]:
    if not isinstance(raw_matchup, dict):
        return
    matchup = as_object(raw_matchup, "matchup")
    home = matchup.get("home")
    away = matchup.get("away")
    if not isinstance(home, dict) or not isinstance(away, dict):
        return
    home_score = float_value(home.get("totalPoints"))
    away_score = float_value(away.get("totalPoints"))
    home_id = int_value(home.get("teamId"))
    away_id = int_value(away.get("teamId"))
    if home_id == 0 or away_id == 0:
        return
    winner = string_value(matchup.get("winner"))
    yield MatchupRow(
        season=season,
        week=int_value(matchup.get("matchupPeriodId")),
        team_a_id=min(home_id, away_id),
        team_b_id=max(home_id, away_id),
        team_a_score=home_score if home_id < away_id else away_score,
        team_b_score=away_score if home_id < away_id else home_score,
        result=_result_for_sorted_ids(home_id, away_id, winner),
        is_playoff=string_value(matchup.get("playoffTierType")) in PLAYOFF_TIERS,
    )


def _team_lookup(team_seasons: list[TeamSeason]) -> dict[tuple[int, int], TeamSeason]:
    return {(team.season, team.team_id): team for team in team_seasons}


def _matchup_order(row: MatchupRow) -> tuple[int, int]:
    return row.season, row.week


def _average(values: Iterator[float]) -> float:
    rows = tuple(values)
    return sum(rows) / len(rows) if rows else 0.0


def _margin(row: MatchupRow) -> float:
    return abs(row.team_a_score - row.team_b_score)


def _current_streak(matchups: tuple[MatchupRow, ...]) -> str:
    if not matchups:
        return "none"
    latest = matchups[-1].result
    length = 0
    for row in reversed(matchups):
        if row.result != latest:
            break
        length += 1
    return f"{latest}:{length}"


def _result_for_sorted_ids(home_id: int, away_id: int, winner: str) -> MatchupResult:
    if winner == "TIE":
        return "TIE"
    if winner == "HOME":
        return "A" if home_id < away_id else "B"
    return "A" if away_id < home_id else "B"
