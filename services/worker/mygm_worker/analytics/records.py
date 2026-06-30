from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass
from typing import TYPE_CHECKING

from mygm_worker.analytics.head_to_head import MatchupRow, matchup_rows
from mygm_worker.analytics.models import AllTimeRecords, JsonObject, TeamSeason

if TYPE_CHECKING:
    from mygm_worker.analytics.draft import SeasonDraft
    from mygm_worker.analytics.lineup_efficiency import LineupSeasonRow
    from mygm_worker.analytics.manager_value import ManagerTradeLedger, ManagerWaiverLedger
    from mygm_worker.analytics.reader import FixtureReader

type WeeklyScoreRow = tuple[int, int, int, float]

# Lineup-efficiency records only consider seasons with a full slate of weeks played.
MIN_EFFICIENCY_WEEKS = 8

# A manager needs at least this many career games for a per-game record to be meaningful.
MIN_CAREER_GAMES = 16


@dataclass(frozen=True, slots=True)
class CareerScoring:
    manager_key: str
    points: float
    games: int
    ppg: float


def career_scoring(
    team_seasons: list[TeamSeason],
    included_seasons: tuple[int, ...],
) -> tuple[CareerScoring, ...]:
    """Per-manager career points + games + PPG across counted seasons (reg + playoffs)."""
    included = set(included_seasons)
    points: defaultdict[str, float] = defaultdict(float)
    games: defaultdict[str, int] = defaultdict(int)
    for row in team_seasons:
        if row.season not in included or row.manager_key.startswith("unresolved:"):
            continue
        points[row.manager_key] += row.points_for
        games[row.manager_key] += row.wins + row.losses + row.ties
    rows = [
        CareerScoring(
            manager_key=manager_key,
            points=round(points[manager_key], 4),
            games=games[manager_key],
            ppg=round(points[manager_key] / games[manager_key], 4) if games[manager_key] else 0.0,
        )
        for manager_key in points
    ]
    return tuple(sorted(rows, key=lambda row: -row.points))


@dataclass(frozen=True, slots=True)
class Superlative:
    key: str
    label: str
    manager_key: str | None
    display_name: str | None
    value: float
    season: int | None
    detail: str
    player_id: int | None = None
    player_name: str | None = None


@dataclass(frozen=True, slots=True)
class RecordRow:
    category: str
    value: float
    manager_key: str | None
    season: int | None
    team_id: int | None


@dataclass(frozen=True, slots=True)
class LuckStrengthRow:
    manager_key: str
    season: int
    team_id: int
    actual_wins: float
    all_play_wins: float
    all_play_ties: float
    possible_games: int
    luck_wins: float
    schedule_strength: float
    caveats: tuple[str, ...]


def records(
    reader: FixtureReader,
    team_seasons: list[TeamSeason],
    included_seasons: tuple[int, ...],
) -> AllTimeRecords:
    included = set(included_seasons)
    counted_team_seasons = [row for row in team_seasons if row.season in included]
    weekly_scores = [
        score
        for season, _week, _team_id, score in reader.weekly_scores()
        if season in included
    ]
    return AllTimeRecords(
        seasons_counted=len(included),
        total_wins=sum(row.wins for row in counted_team_seasons),
        total_losses=sum(row.losses for row in counted_team_seasons),
        total_ties=sum(row.ties for row in counted_team_seasons),
        highest_weekly_score=round(max(weekly_scores, default=0.0), 4),
        lowest_weekly_score=round(min(weekly_scores, default=0.0), 4),
    )


def record_rows(
    reader: FixtureReader,
    team_seasons: list[TeamSeason],
    included_seasons: tuple[int, ...],
) -> tuple[RecordRow, ...]:
    included = set(included_seasons)
    team_lookup = _team_lookup(team_seasons)
    rows = [
        *_weekly_score_records(reader, team_lookup, included),
        *_matchup_records(reader, team_lookup, included),
        *_season_records(team_seasons, included),
        *_career_scoring_records(team_seasons, included_seasons),
    ]
    return tuple(row for row in rows if row is not None)


def _career_scoring_records(
    team_seasons: list[TeamSeason],
    included_seasons: tuple[int, ...],
) -> Iterator[RecordRow | None]:
    scoring = career_scoring(team_seasons, included_seasons)
    if not scoring:
        return
    most_points = max(scoring, key=lambda row: row.points)
    yield RecordRow(
        category="most_career_points",
        value=most_points.points,
        manager_key=most_points.manager_key,
        season=None,
        team_id=None,
    )
    eligible = [row for row in scoring if row.games >= MIN_CAREER_GAMES]
    if eligible:
        best_ppg = max(eligible, key=lambda row: row.ppg)
        yield RecordRow(
            category="highest_career_ppg",
            value=best_ppg.ppg,
            manager_key=best_ppg.manager_key,
            season=None,
            team_id=None,
        )


def luck_strength_rows(
    reader: FixtureReader,
    team_seasons: list[TeamSeason],
    included_seasons: tuple[int, ...],
) -> tuple[LuckStrengthRow, ...]:
    included = set(included_seasons)
    partial_seasons = _partial_seasons(reader, included)
    score_maps = {
        season: _weekly_scores_by_team(reader, season) for season in sorted(included)
    }
    rows: list[LuckStrengthRow] = []
    for team in team_seasons:
        if team.season not in included:
            continue
        team_scores = score_maps.get(team.season, {})
        actual_games = max(team.wins + team.losses + team.ties, 1)
        all_play_wins, all_play_ties, possible_games = _all_play_record(
            team.team_id,
            team_scores,
        )
        actual_wins = float(team.wins) + (float(team.ties) / 2)
        all_play_win_pct = (
            (all_play_wins + (all_play_ties / 2)) / possible_games
            if possible_games
            else 0.0
        )
        expected_wins = all_play_win_pct * actual_games
        caveats = (
            (f"{team.season} is a partial season; luck and SOS may move.",)
            if team.season in partial_seasons
            else ()
        )
        rows.append(
            LuckStrengthRow(
                manager_key=team.manager_key,
                season=team.season,
                team_id=team.team_id,
                actual_wins=round(actual_wins, 4),
                all_play_wins=round(all_play_wins, 4),
                all_play_ties=round(all_play_ties, 4),
                possible_games=possible_games,
                luck_wins=round(actual_wins - expected_wins, 4),
                schedule_strength=round(_schedule_strength(team.team_id, team_scores), 4),
                caveats=caveats,
            )
        )
    return tuple(rows)


def _weekly_score_records(
    reader: FixtureReader,
    team_lookup: dict[tuple[int, int], TeamSeason],
    included: set[int],
) -> Iterator[RecordRow | None]:
    scores = [
        (season, week, team_id, score)
        for season, week, team_id, score in reader.weekly_scores()
        if season in included
    ]
    if not scores:
        return
    highest = max(scores, key=_weekly_score_value)
    lowest = min(scores, key=_weekly_score_value)
    yield _weekly_score_record("highest_weekly_score", highest, team_lookup)
    yield _weekly_score_record("lowest_weekly_score", lowest, team_lookup)


def _weekly_score_record(
    category: str,
    score_row: WeeklyScoreRow,
    team_lookup: dict[tuple[int, int], TeamSeason],
) -> RecordRow:
    season, _week, team_id, score = score_row
    team = team_lookup.get((season, team_id))
    return RecordRow(
        category=category,
        value=round(score, 4),
        manager_key=team.manager_key if team else None,
        season=season,
        team_id=team_id,
    )


def _matchup_records(
    reader: FixtureReader,
    team_lookup: dict[tuple[int, int], TeamSeason],
    included: set[int],
) -> Iterator[RecordRow | None]:
    rows = [row for row in matchup_rows(reader, tuple(included)) if row.season in included]
    if not rows:
        return
    yield _matchup_record("closest_matchup", min(rows, key=_matchup_margin), team_lookup)
    yield _matchup_record("largest_matchup", max(rows, key=_matchup_margin), team_lookup)


def _matchup_record(
    category: str,
    matchup: MatchupRow,
    team_lookup: dict[tuple[int, int], TeamSeason],
) -> RecordRow:
    winner_id = _winner_id(matchup)
    team = team_lookup.get((matchup.season, winner_id))
    return RecordRow(
        category=category,
        value=round(abs(matchup.team_a_score - matchup.team_b_score), 4),
        manager_key=team.manager_key if team else None,
        season=matchup.season,
        team_id=winner_id,
    )


def _season_records(
    team_seasons: list[TeamSeason],
    included: set[int],
) -> Iterator[RecordRow | None]:
    rows = [row for row in team_seasons if row.season in included]
    if not rows:
        return
    best = max(rows, key=_win_pct)
    worst = min(rows, key=_win_pct)
    most_points = max(rows, key=_points_for)
    yield _season_record("best_season_record", best, _win_pct(best))
    yield _season_record("worst_season_record", worst, _win_pct(worst))
    yield _season_record("most_season_points", most_points, _points_for(most_points))


def _season_record(
    category: str,
    team: TeamSeason,
    score: float,
) -> RecordRow:
    return RecordRow(
        category=category,
        value=round(score, 4),
        manager_key=team.manager_key,
        season=team.season,
        team_id=team.team_id,
    )


def _weekly_scores_by_team(reader: FixtureReader, season: int) -> dict[int, dict[int, float]]:
    weeks: dict[int, dict[int, float]] = {}
    for row_season, week, team_id, score in reader.weekly_scores():
        if row_season == season:
            weeks.setdefault(week, {})[team_id] = score
    return weeks


def _all_play_record(
    team_id: int,
    weekly_scores: dict[int, dict[int, float]],
) -> tuple[float, float, int]:
    wins = 0.0
    ties = 0.0
    possible_games = 0
    for scores in weekly_scores.values():
        own_score = scores.get(team_id)
        if own_score is None:
            continue
        for opponent_id, opponent_score in scores.items():
            if opponent_id == team_id:
                continue
            possible_games += 1
            if own_score > opponent_score:
                wins += 1
            elif own_score == opponent_score:
                ties += 1
    return wins, ties, possible_games


def _schedule_strength(team_id: int, weekly_scores: dict[int, dict[int, float]]) -> float:
    margins: list[float] = []
    for scores in weekly_scores.values():
        own_score = scores.get(team_id)
        if own_score is None:
            continue
        opponents = [score for opponent_id, score in scores.items() if opponent_id != team_id]
        if not opponents:
            continue
        average_possible_opponent = sum(opponents) / len(opponents)
        margins.append(average_possible_opponent - own_score)
    return sum(margins) / len(margins) if margins else 0.0


def _team_lookup(team_seasons: list[TeamSeason]) -> dict[tuple[int, int], TeamSeason]:
    return {(team.season, team.team_id): team for team in team_seasons}


def _win_pct(team: TeamSeason) -> float:
    games = team.wins + team.losses + team.ties
    return (team.wins + (team.ties / 2)) / games if games else 0.0


def _points_for(team: TeamSeason) -> float:
    return team.points_for


def _weekly_score_value(row: WeeklyScoreRow) -> float:
    return row[3]


def _matchup_margin(row: MatchupRow) -> float:
    return abs(row.team_a_score - row.team_b_score)


def _winner_id(matchup: MatchupRow) -> int:
    match matchup.result:
        case "A":
            return matchup.team_a_id
        case "B":
            return matchup.team_b_id
        case "TIE":
            return matchup.team_a_id


def _partial_seasons(reader: FixtureReader, included: set[int]) -> set[int]:
    return {
        season.season
        for season in reader.seasons()
        if season.season in included and season.is_partial
    }


def superlatives(
    *,
    lineup_rows: tuple[LineupSeasonRow, ...],
    trade_ledgers: tuple[ManagerTradeLedger, ...],
    waiver_ledgers: tuple[ManagerWaiverLedger, ...],
    season_drafts: tuple[SeasonDraft, ...],
    included_seasons: tuple[int, ...],
) -> tuple[Superlative, ...]:
    included = set(included_seasons)
    rows: list[Superlative | None] = [
        _draft_steal_superlative(season_drafts, included),
        _draft_bust_superlative(season_drafts, included),
        _best_trade_superlative(trade_ledgers),
        _worst_trade_superlative(trade_ledgers),
        _waiver_value_superlative(waiver_ledgers),
        _best_pickup_superlative(waiver_ledgers),
        _bench_points_superlative(lineup_rows, included),
        _efficiency_superlative(lineup_rows, included),
    ]
    return tuple(row for row in rows if row is not None)


def _draft_steal_superlative(
    season_drafts: tuple[SeasonDraft, ...],
    included: set[int],
) -> Superlative | None:
    steals = [
        draft.best_steal
        for draft in season_drafts
        if draft.season in included and not draft.is_partial and draft.best_steal is not None
    ]
    if not steals:
        return None
    best = max(steals, key=lambda pick: pick.steal_value)
    return Superlative(
        key="draft_steal",
        label="Draft Steal of the Year",
        manager_key=best.manager_key,
        display_name=best.display_name,
        value=float(best.steal_value),
        season=best.season,
        detail=(
            f"{best.player_name} drafted #{best.overall_pick} ({best.season}), "
            f"finished #{best.points_rank} in points"
        ),
        player_id=best.player_id,
        player_name=best.player_name,
    )


def _draft_bust_superlative(
    season_drafts: tuple[SeasonDraft, ...],
    included: set[int],
) -> Superlative | None:
    busts = [
        draft.biggest_bust
        for draft in season_drafts
        if draft.season in included and not draft.is_partial and draft.biggest_bust is not None
    ]
    if not busts:
        return None
    worst = min(busts, key=lambda pick: pick.steal_value)
    return Superlative(
        key="draft_bust",
        label="Draft Bust of the Year",
        manager_key=worst.manager_key,
        display_name=worst.display_name,
        value=float(worst.steal_value),
        season=worst.season,
        detail=(
            f"{worst.player_name} drafted #{worst.overall_pick} ({worst.season}), "
            f"finished #{worst.points_rank} in points"
        ),
        player_id=worst.player_id,
        player_name=worst.player_name,
    )


def _best_trade_superlative(
    trade_ledgers: tuple[ManagerTradeLedger, ...],
) -> Superlative | None:
    candidates = [
        (ledger, ledger.best_trade)
        for ledger in trade_ledgers
        if ledger.best_trade is not None
    ]
    if not candidates:
        return None
    ledger, trade = max(candidates, key=lambda item: _trade_net(item[1]))
    return Superlative(
        key="best_trade",
        label="Best Trade",
        manager_key=ledger.manager_key,
        display_name=ledger.display_name,
        value=_trade_net(trade),
        season=_trade_season(trade),
        detail=_trade_detail(ledger, trade),
    )


def _worst_trade_superlative(
    trade_ledgers: tuple[ManagerTradeLedger, ...],
) -> Superlative | None:
    candidates = [
        (ledger, ledger.worst_trade)
        for ledger in trade_ledgers
        if ledger.worst_trade is not None
    ]
    if not candidates:
        return None
    ledger, trade = min(candidates, key=lambda item: _trade_net(item[1]))
    return Superlative(
        key="worst_trade",
        label="Worst Trade",
        manager_key=ledger.manager_key,
        display_name=ledger.display_name,
        value=_trade_net(trade),
        season=_trade_season(trade),
        detail=_trade_detail(ledger, trade),
    )


def _waiver_value_superlative(
    waiver_ledgers: tuple[ManagerWaiverLedger, ...],
) -> Superlative | None:
    eligible = [ledger for ledger in waiver_ledgers if ledger.eligible_moves > 0]
    if not eligible:
        return None
    leader = max(eligible, key=lambda ledger: ledger.net_points)
    return Superlative(
        key="waiver_value_leader",
        label="Waiver Value Leader",
        manager_key=leader.manager_key,
        display_name=leader.display_name,
        value=leader.net_points,
        season=None,
        detail=(
            f"{leader.net_points:.1f} net points across {leader.eligible_moves} scored moves"
        ),
    )


def _best_pickup_superlative(
    waiver_ledgers: tuple[ManagerWaiverLedger, ...],
) -> Superlative | None:
    candidates = [
        (ledger, ledger.best_pickup)
        for ledger in waiver_ledgers
        if ledger.best_pickup is not None
    ]
    if not candidates:
        return None
    ledger, pickup = max(candidates, key=lambda item: _pickup_points(item[1]))
    return Superlative(
        key="best_pickup",
        label="Best Pickup",
        manager_key=ledger.manager_key,
        display_name=ledger.display_name,
        value=_pickup_points(pickup),
        season=_pickup_season(pickup),
        detail=_pickup_detail(pickup),
    )


def _bench_points_superlative(
    lineup_rows: tuple[LineupSeasonRow, ...],
    included: set[int],
) -> Superlative | None:
    eligible = [
        row
        for row in lineup_rows
        if row.season in included and row.weeks_counted >= MIN_EFFICIENCY_WEEKS
    ]
    if not eligible:
        return None
    leader = max(eligible, key=lambda row: row.bench_points)
    return Superlative(
        key="bench_points_leader",
        label="Most Points Left on the Bench",
        manager_key=leader.manager_key,
        display_name=leader.display_name,
        value=leader.bench_points,
        season=leader.season,
        detail=(
            f"{leader.bench_points:.1f} points benched in {leader.season} "
            f"({leader.avg_efficiency:.0f}% lineup efficiency)"
        ),
    )


def _efficiency_superlative(
    lineup_rows: tuple[LineupSeasonRow, ...],
    included: set[int],
) -> Superlative | None:
    eligible = [
        row
        for row in lineup_rows
        if row.season in included and row.weeks_counted >= MIN_EFFICIENCY_WEEKS
    ]
    if not eligible:
        return None
    leader = max(eligible, key=lambda row: row.avg_efficiency)
    return Superlative(
        key="lineup_efficiency_leader",
        label="Best Lineup Efficiency",
        manager_key=leader.manager_key,
        display_name=leader.display_name,
        value=leader.avg_efficiency,
        season=leader.season,
        detail=(
            f"{leader.avg_efficiency:.1f}% of optimal points started in {leader.season}"
        ),
    )


def _trade_net(trade: JsonObject | None) -> float:
    if trade is None:
        return 0.0
    value = trade.get("netPoints")
    return float(value) if isinstance(value, int | float) else 0.0


def _trade_season(trade: JsonObject | None) -> int | None:
    if trade is None:
        return None
    value = trade.get("season")
    return value if isinstance(value, int) else None


def _trade_detail(ledger: ManagerTradeLedger, trade: JsonObject | None) -> str:
    summary = ""
    if trade is not None:
        raw = trade.get("summary")
        summary = raw if isinstance(raw, str) else ""
    net = _trade_net(trade)
    return f"{ledger.display_name} {summary} ({net:+.1f} net points)"


def _pickup_points(pickup: JsonObject | None) -> float:
    if pickup is None:
        return 0.0
    value = pickup.get("points")
    return float(value) if isinstance(value, int | float) else 0.0


def _pickup_season(pickup: JsonObject | None) -> int | None:
    if pickup is None:
        return None
    value = pickup.get("season")
    return value if isinstance(value, int) else None


def _pickup_detail(pickup: JsonObject | None) -> str:
    if pickup is None:
        return ""
    raw = pickup.get("summary")
    summary = raw if isinstance(raw, str) else ""
    return f"{summary} ({_pickup_points(pickup):.1f} rest-of-season points)"
