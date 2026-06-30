from __future__ import annotations

from collections import Counter, defaultdict
from typing import TYPE_CHECKING, Final

from mygm_worker.analytics.models import (
    AcquisitionAnalytics,
    Confidence,
    JsonObject,
    JsonValue,
    ManagerRating,
    TeamSeason,
    TradeAnalytics,
)

if TYPE_CHECKING:
    from mygm_worker.analytics.lineup_efficiency import LineupSeasonRow
    from mygm_worker.analytics.manager_value import ManagerSeasonValue

FORMULA_VERSION = "mygm-retrospective-v1"
RATING_WEIGHTS: Final[dict[str, float]] = {
    "tradePerformance": 0.35,
    "waiverPerformance": 0.35,
    "recordAndPoints": 0.20,
    "luckAdjusted": 0.10,
}

FORMULA_VERSION_V2 = "mygm-historian-v2"
RATING_WEIGHTS_V2: Final[dict[str, float]] = {
    "tradeValue": 0.25,
    "waiverValue": 0.25,
    "lineupEfficiency": 0.15,
    "recordAndPoints": 0.35,
}
RATING_V2_CAVEAT = "Retrospective value, not ex-ante decision quality; luck is excluded."

FORMULA_VERSION_V3 = "mygm-historian-v3"
RATING_WEIGHTS_V3: Final[dict[str, float]] = {
    "tradeValue": 0.20,
    "waiverValue": 0.20,
    "lineupEfficiency": 0.15,
    "recordAndPoints": 0.20,
    "draftValue": 0.15,
    "luck": 0.10,
}
RATING_V3_CAVEAT = (
    "Trade, waiver, and draft value are measured in Value Over Replacement; "
    "retrospective, not ex-ante decision quality."
)


def gm_ratings(
    *,
    team_seasons: list[TeamSeason],
    included_seasons: tuple[int, ...],
    trade_summary: TradeAnalytics,
    acquisition_summary: AcquisitionAnalytics,
) -> tuple[ManagerRating, ...]:
    rows = [
        row
        for row in team_seasons
        if row.season in set(included_seasons) and not row.manager_key.startswith("unresolved:")
    ]
    season_ratings = [
        _season_rating(row, rows, trade_summary, acquisition_summary) for row in rows
    ]
    career_ratings = _career_ratings(rows, season_ratings)
    return tuple(season_ratings + career_ratings)


def manager_rating_rows(
    *,
    team_seasons: list[TeamSeason],
    ratings: tuple[ManagerRating, ...],
) -> list[JsonObject]:
    aliases = _team_aliases(team_seasons)
    return [
        _rating_row(rating, aliases.get(rating.manager_key, []))
        for rating in sorted(
            ratings,
            key=lambda item: (
                item.season is None,
                item.season if item.season is not None else 0,
                -item.final_score,
                item.manager_key,
            ),
        )
    ]


def confidence(
    trade_summary: TradeAnalytics,
    acquisition_summary: AcquisitionAnalytics,
) -> Confidence:
    if trade_summary.graded_rows == 0 and acquisition_summary.counted_rows == 0:
        return "no_grade"
    if trade_summary.ungraded_rows > 0 or acquisition_summary.excluded_rows > 0:
        return "medium"
    return "high"


def rating_warnings(
    trade_summary: TradeAnalytics,
    acquisition_summary: AcquisitionAnalytics,
) -> tuple[str, ...]:
    warnings = [
        "retrospective value captured, not ex-ante decision quality",
        acquisition_summary.faab_warning,
    ]
    if trade_summary.ungraded_rows:
        warnings.append(f"{trade_summary.ungraded_rows} ungraded executed trade accepts visible")
    if acquisition_summary.excluded_rows:
        count = acquisition_summary.excluded_rows
        warnings.append(f"{count} acquisition rows excluded with reason")
    return tuple(warnings)


def _season_rating(
    team_season: TeamSeason,
    all_team_seasons: list[TeamSeason],
    trade_summary: TradeAnalytics,
    acquisition_summary: AcquisitionAnalytics,
) -> ManagerRating:
    season_rows = [row for row in all_team_seasons if row.season == team_season.season]
    win_pct = _win_pct(team_season)
    points_rank = _percentile_rank(team_season.points_for, [row.points_for for row in season_rows])
    record_and_points = round((points_rank * 0.60) + (win_pct * 100 * 0.40), 4)
    trade_score = _ratio_score(trade_summary.graded_rows, trade_summary.completed_trade_accept_rows)
    waiver_score = _ratio_score(acquisition_summary.counted_rows, acquisition_summary.total_rows)
    luck_adjusted = _percentile_rank(
        team_season.points_for - team_season.points_against,
        [row.points_for - row.points_against for row in season_rows],
    )
    raw = {
        "tradePerformance": trade_score,
        "waiverPerformance": waiver_score,
        "recordAndPoints": record_and_points,
        "luckAdjusted": luck_adjusted,
    }
    return ManagerRating(
        manager_key=team_season.manager_key,
        season=team_season.season,
        raw_components=raw,
        normalized_components={key: _clamp(value) for key, value in raw.items()},
        weights=RATING_WEIGHTS,
        final_score=round(sum(raw[key] * RATING_WEIGHTS[key] for key in RATING_WEIGHTS), 4),
        confidence=confidence(trade_summary, acquisition_summary),
        formula_version=FORMULA_VERSION,
        warnings=rating_warnings(trade_summary, acquisition_summary),
    )


def _career_ratings(
    team_seasons: list[TeamSeason],
    season_ratings: list[ManagerRating],
) -> list[ManagerRating]:
    by_manager: defaultdict[str, list[ManagerRating]] = defaultdict(list)
    season_count: Counter[str] = Counter()
    for row in team_seasons:
        season_count[row.manager_key] += 1
    for rating in season_ratings:
        by_manager[rating.manager_key].append(rating)
    return [
        _career_rating(manager_key, ratings, season_count[manager_key])
        for manager_key, ratings in sorted(by_manager.items())
    ]


def _career_rating(
    manager_key: str,
    ratings: list[ManagerRating],
    season_count: int,
) -> ManagerRating:
    raw = _average_components([rating.raw_components for rating in ratings])
    return ManagerRating(
        manager_key=manager_key,
        season=None,
        raw_components=raw,
        normalized_components={key: _clamp(value) for key, value in raw.items()},
        weights=RATING_WEIGHTS,
        final_score=round(sum(rating.final_score for rating in ratings) / len(ratings), 4),
        confidence="medium" if season_count >= 2 else "low",
        formula_version=FORMULA_VERSION,
        warnings=("2026 excluded from career ratings by default",),
    )


def _win_pct(row: TeamSeason) -> float:
    games = row.wins + row.losses + row.ties
    if games == 0:
        return 0.0
    return (row.wins + (0.5 * row.ties)) / games


def _percentile_rank(value: float, values: list[float]) -> float:
    if not values:
        return 50.0
    if len(values) == 1:
        return 100.0
    lower_or_equal = sum(1 for candidate in values if candidate <= value)
    return round(((lower_or_equal - 1) / (len(values) - 1)) * 100, 4)


def _ratio_score(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 50.0
    return round((numerator / denominator) * 100, 4)


def _average_components(components: list[dict[str, float]]) -> dict[str, float]:
    return {
        key: round(sum(row[key] for row in components) / len(components), 4)
        for key in RATING_WEIGHTS
    }


def _clamp(value: float) -> float:
    return max(0.0, min(100.0, round(value, 4)))


def _rating_row(rating: ManagerRating, aliases: list[JsonValue]) -> JsonObject:
    return {
        "managerKey": rating.manager_key,
        "season": rating.season,
        "ratingScope": "allTime" if rating.season is None else "season",
        "score": rating.final_score,
        "scoreEligible": True,
        "confidence": rating.confidence,
        "formulaVersion": rating.formula_version,
        "rawComponents": dict(rating.raw_components),
        "normalizedComponents": dict(rating.normalized_components),
        "weights": dict(rating.weights),
        "aliases": aliases,
        "caveats": list(rating.warnings),
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


# --- v2 rating: mygm-historian-v2 (luck removed; real per-manager components) ----


def gm_ratings_v2(
    *,
    team_seasons: list[TeamSeason],
    included_seasons: tuple[int, ...],
    season_values: tuple[ManagerSeasonValue, ...],
    lineup_rows: tuple[LineupSeasonRow, ...],
) -> tuple[ManagerRating, ...]:
    included = set(included_seasons)
    rows = [
        row
        for row in team_seasons
        if row.season in included and not row.manager_key.startswith("unresolved:")
    ]
    trade_by_key = {
        (value.manager_key, value.season): value.trade_net_points for value in season_values
    }
    waiver_by_key = {
        (value.manager_key, value.season): value.waiver_net_points for value in season_values
    }
    lineup_by_key = {(row.manager_key, row.season): row.avg_efficiency for row in lineup_rows}
    season_ratings = [
        _season_rating_v2(row, rows, trade_by_key, waiver_by_key, lineup_by_key) for row in rows
    ]
    career_ratings = _career_ratings_v2(rows, season_ratings)
    return tuple(season_ratings + career_ratings)


def _season_rating_v2(
    team_season: TeamSeason,
    all_rows: list[TeamSeason],
    trade_by_key: dict[tuple[str, int], float],
    waiver_by_key: dict[tuple[str, int], float],
    lineup_by_key: dict[tuple[str, int], float],
) -> ManagerRating:
    season_rows = [row for row in all_rows if row.season == team_season.season]
    keys = [(row.manager_key, row.season) for row in season_rows]
    trade_values = [trade_by_key.get(key, 0.0) for key in keys]
    waiver_values = [waiver_by_key.get(key, 0.0) for key in keys]
    lineup_values = [lineup_by_key.get(key, 0.0) for key in keys]
    own = (team_season.manager_key, team_season.season)
    win_pct = _win_pct(team_season)
    points_rank = _percentile_rank(team_season.points_for, [row.points_for for row in season_rows])
    raw = {
        "tradeValue": _percentile_rank(trade_by_key.get(own, 0.0), trade_values),
        "waiverValue": _percentile_rank(waiver_by_key.get(own, 0.0), waiver_values),
        "lineupEfficiency": _percentile_rank(lineup_by_key.get(own, 0.0), lineup_values),
        "recordAndPoints": round((points_rank * 0.60) + (win_pct * 100 * 0.40), 4),
    }
    return ManagerRating(
        manager_key=team_season.manager_key,
        season=team_season.season,
        raw_components=raw,
        normalized_components={key: _clamp(value) for key, value in raw.items()},
        weights=RATING_WEIGHTS_V2,
        final_score=round(sum(raw[key] * RATING_WEIGHTS_V2[key] for key in RATING_WEIGHTS_V2), 4),
        confidence="high",
        formula_version=FORMULA_VERSION_V2,
        warnings=(RATING_V2_CAVEAT,),
    )


def _career_ratings_v2(
    team_seasons: list[TeamSeason],
    season_ratings: list[ManagerRating],
) -> list[ManagerRating]:
    by_manager: defaultdict[str, list[ManagerRating]] = defaultdict(list)
    season_count: Counter[str] = Counter()
    for row in team_seasons:
        season_count[row.manager_key] += 1
    for rating in season_ratings:
        by_manager[rating.manager_key].append(rating)
    return [
        _career_rating_v2(manager_key, ratings, season_count[manager_key])
        for manager_key, ratings in sorted(by_manager.items())
    ]


def _career_rating_v2(
    manager_key: str,
    ratings: list[ManagerRating],
    season_count: int,
) -> ManagerRating:
    raw = {
        key: round(sum(rating.raw_components[key] for rating in ratings) / len(ratings), 4)
        for key in RATING_WEIGHTS_V2
    }
    return ManagerRating(
        manager_key=manager_key,
        season=None,
        raw_components=raw,
        normalized_components={key: _clamp(value) for key, value in raw.items()},
        weights=RATING_WEIGHTS_V2,
        final_score=round(sum(rating.final_score for rating in ratings) / len(ratings), 4),
        confidence="medium" if season_count >= 2 else "low",
        formula_version=FORMULA_VERSION_V2,
        warnings=(RATING_V2_CAVEAT, "2026 excluded from career ratings by default"),
    )


# --- v3 rating: mygm-historian-v3 (VOR trade/waiver, draft surplus, luck restored) ----


def gm_ratings_v3(
    *,
    team_seasons: list[TeamSeason],
    included_seasons: tuple[int, ...],
    season_values: tuple[ManagerSeasonValue, ...],
    lineup_rows: tuple[LineupSeasonRow, ...],
    draft_surplus: dict[tuple[str, int], float],
) -> tuple[ManagerRating, ...]:
    included = set(included_seasons)
    rows = [
        row
        for row in team_seasons
        if row.season in included and not row.manager_key.startswith("unresolved:")
    ]
    trade_by_key = {
        (value.manager_key, value.season): value.trade_net_points for value in season_values
    }
    waiver_by_key = {
        (value.manager_key, value.season): value.waiver_net_points for value in season_values
    }
    lineup_by_key = {(row.manager_key, row.season): row.avg_efficiency for row in lineup_rows}
    season_ratings = [
        _season_rating_v3(row, rows, trade_by_key, waiver_by_key, lineup_by_key, draft_surplus)
        for row in rows
    ]
    career_ratings = _career_ratings_v3(rows, season_ratings)
    return tuple(season_ratings + career_ratings)


def _season_rating_v3(
    team_season: TeamSeason,
    all_rows: list[TeamSeason],
    trade_by_key: dict[tuple[str, int], float],
    waiver_by_key: dict[tuple[str, int], float],
    lineup_by_key: dict[tuple[str, int], float],
    draft_surplus: dict[tuple[str, int], float],
) -> ManagerRating:
    season_rows = [row for row in all_rows if row.season == team_season.season]
    keys = [(row.manager_key, row.season) for row in season_rows]
    own = (team_season.manager_key, team_season.season)
    win_pct = _win_pct(team_season)
    points_rank = _percentile_rank(team_season.points_for, [row.points_for for row in season_rows])
    differentials = [row.points_for - row.points_against for row in season_rows]
    raw = {
        "tradeValue": _percentile_rank(
            trade_by_key.get(own, 0.0), [trade_by_key.get(key, 0.0) for key in keys]
        ),
        "waiverValue": _percentile_rank(
            waiver_by_key.get(own, 0.0), [waiver_by_key.get(key, 0.0) for key in keys]
        ),
        "lineupEfficiency": _percentile_rank(
            lineup_by_key.get(own, 0.0), [lineup_by_key.get(key, 0.0) for key in keys]
        ),
        "recordAndPoints": round((points_rank * 0.60) + (win_pct * 100 * 0.40), 4),
        "draftValue": _percentile_rank(
            draft_surplus.get(own, 0.0), [draft_surplus.get(key, 0.0) for key in keys]
        ),
        "luck": _percentile_rank(
            team_season.points_for - team_season.points_against, differentials
        ),
    }
    return ManagerRating(
        manager_key=team_season.manager_key,
        season=team_season.season,
        raw_components=raw,
        normalized_components={key: _clamp(value) for key, value in raw.items()},
        weights=RATING_WEIGHTS_V3,
        final_score=round(sum(raw[key] * RATING_WEIGHTS_V3[key] for key in RATING_WEIGHTS_V3), 4),
        confidence="high",
        formula_version=FORMULA_VERSION_V3,
        warnings=(RATING_V3_CAVEAT,),
    )


def _career_ratings_v3(
    team_seasons: list[TeamSeason],
    season_ratings: list[ManagerRating],
) -> list[ManagerRating]:
    by_manager: defaultdict[str, list[ManagerRating]] = defaultdict(list)
    season_count: Counter[str] = Counter()
    for row in team_seasons:
        season_count[row.manager_key] += 1
    for rating in season_ratings:
        by_manager[rating.manager_key].append(rating)
    return [
        _career_rating_v3(manager_key, ratings, season_count[manager_key])
        for manager_key, ratings in sorted(by_manager.items())
    ]


def _career_rating_v3(
    manager_key: str,
    ratings: list[ManagerRating],
    season_count: int,
) -> ManagerRating:
    raw = {
        key: round(sum(rating.raw_components[key] for rating in ratings) / len(ratings), 4)
        for key in RATING_WEIGHTS_V3
    }
    return ManagerRating(
        manager_key=manager_key,
        season=None,
        raw_components=raw,
        normalized_components={key: _clamp(value) for key, value in raw.items()},
        weights=RATING_WEIGHTS_V3,
        final_score=round(sum(rating.final_score for rating in ratings) / len(ratings), 4),
        confidence="medium" if season_count >= 2 else "low",
        formula_version=FORMULA_VERSION_V3,
        warnings=(RATING_V3_CAVEAT, "2026 excluded from career ratings by default"),
    )
