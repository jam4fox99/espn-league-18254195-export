"""Career "player badges": one signature label per fantasy-relevant player.

Each skill player (QB/RB/WR/TE with enough career games) earns a single,
mutually-exclusive badge describing their defining trait over their whole career
in the league's data. Badges are assigned best-fit and position-relative: every
candidate badge gets a strength score measured against same-position peers and the
strongest wins, so the labels stay rare and meaningful instead of everyone being
"consistent".

Signals come from the per-player weekly detail in the player lookup — weekly
fantasy points plus the applied stat lines, converted back to raw counts with the
league's own scoring weights so the math is league-agnostic — plus the vendored
NFL schedule, which lets us grade each week's opponent defense for the matchup
badge.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from mygm_worker.analytics.json_tools import (
    float_value,
    int_value,
    objects,
    string_value,
)
from mygm_worker.analytics.player_directory import PRO_TEAM_ABBREV

if TYPE_CHECKING:
    from mygm_worker.analytics.dvp import DvpIndex
    from mygm_worker.analytics.injuries import InjuryIndex
    from mygm_worker.analytics.models import JsonObject, JsonValue
    from mygm_worker.analytics.nfl_schedule import ScheduleIndex
    from mygm_worker.analytics.player_directory import PlayerDirectoryEntry
    from mygm_worker.analytics.reader import FixtureReader

# Display order; also breaks exact-tie assignments (earlier wins).
BADGES: tuple[str, ...] = (
    "Elite Consistent",
    "High Floor",
    "Boom or Bust",
    "Explosive",
    "TD Dependent",
    "Screen Merchant",
    "Matchup Based",
    "Injury Risk",
)

# Short human-readable descriptions (UI tooltip text).
BADGE_BLURBS: dict[str, str] = {
    "Elite Consistent": "Elite weekly scorer who almost never busts.",
    "High Floor": "Dependable points every week — a safe, steady starter.",
    "Boom or Bust": "League-winner ceiling, season-killer floor — wild week to week.",
    "Explosive": "Big-play threat who turns touches into chunk yardage.",
    "TD Dependent": "Lives and dies by the end zone — value rides on touchdowns.",
    "Screen Merchant": "High-volume short-area target; lots of catches, few yards each.",
    "Matchup Based": "Feasts on weak defenses, disappears against strong ones.",
    "Injury Risk": "Frequently on the injury report — availability is the question.",
}

# ESPN stat ids recoverable from appliedStats (those with non-zero scoring weight).
_REC = 53
_REC_YDS = 42
_TD_STATS = (4, 25, 43)  # pass / rush / receiving touchdowns (already fantasy points)

_SCORING_POSITIONS = frozenset({"QB", "RB", "WR", "TE"})

_MIN_GAMES = 16  # roughly a full season of weeks — enough to read a trend
_MIN_REC_PER_GAME = 2.5  # gate for the reception-shape badges
_TD_FRACTION_GATE = 0.30
_INJURY_RATE_GATE = 1.5  # weighted injury-report weeks per season before it's a "risk"
_MATCHUP_SWING_GATE = 0.30  # easy weeks must out-score tough weeks by this fraction
_MATCHUP_MIN_SPLIT = 4  # need this many easy + tough games to read a matchup swing


@dataclass(slots=True)
class _PlayerStats:
    player_id: int
    name: str
    position: str
    seasons: set[int] = field(default_factory=set)
    points: list[float] = field(default_factory=list)
    receptions: float = 0.0
    rec_yards: float = 0.0
    td_points: float = 0.0
    total_points: float = 0.0
    appearances: int = 0
    # (week points, opponent defense-vs-position rank in [0,1]; higher = weaker D).
    matchup: list[tuple[float, float]] = field(default_factory=list)


def compute_player_badges(
    reader: FixtureReader,
    directory: dict[int, PlayerDirectoryEntry],
    schedule: ScheduleIndex,
    dvp: DvpIndex,
    injuries: InjuryIndex,
) -> dict[int, str]:
    """Map ``player_id -> badge`` for every eligible skill player."""
    weights = _scoring_weights(reader)
    records = _gather(reader, directory, schedule, dvp, weights)
    return _assign_badges(records, injuries)


# ----------------------------------------------------------------- gathering


def _gather(
    reader: FixtureReader,
    directory: dict[int, PlayerDirectoryEntry],
    schedule: ScheduleIndex,
    dvp: DvpIndex,
    weights: dict[int, float],
) -> dict[int, _PlayerStats]:
    records: dict[int, _PlayerStats] = {}
    for pid_str, raw_player in reader.player_lookup().items():
        player = _obj(raw_player)
        player_id = int_value(player.get("playerId")) or _safe_int(pid_str)
        if player_id == 0:
            continue
        entry = directory.get(player_id)
        position = (
            entry.position if entry is not None else string_value(player.get("defaultPosition"))
        )
        if position not in _SCORING_POSITIONS:
            continue
        name = entry.name if entry is not None else string_value(player.get("name"))
        stats = _PlayerStats(player_id=player_id, name=name, position=position)
        for season_str, raw_weeks_obj in _obj(player.get("weekly_details")).items():
            season = _safe_int(season_str)
            stats.seasons.add(season)
            for week_str, raw_detail in _obj(raw_weeks_obj).items():
                _absorb_week(
                    stats, _obj(raw_detail), season, _safe_int(week_str), schedule, dvp, weights
                )
        if stats.appearances:
            records[player_id] = stats
    return records


def _absorb_week(
    stats: _PlayerStats,
    detail: JsonObject,
    season: int,
    week: int,
    schedule: ScheduleIndex,
    dvp: DvpIndex,
    weights: dict[int, float],
) -> None:
    points = float_value(detail.get("points"))
    applied = _obj(detail.get("appliedStats"))
    if not applied and points == 0:
        # Empty appliedStats + 0 points == did-not-play (bye / inactive / injured /
        # future-season placeholder). In this export every 0-point week has empty
        # appliedStats, so this is an unambiguous DNP marker. Counting these as real
        # 0-point games would halve every mean, double every CV, inflate the games
        # count past _MIN_GAMES, and skew the matchup signal — so drop them before
        # they touch any aggregate.
        return
    stats.points.append(points)
    stats.total_points += points
    stats.receptions += _raw(applied, _REC, weights)
    stats.rec_yards += _raw(applied, _REC_YDS, weights)
    stats.td_points += sum(float_value(applied.get(str(stat))) for stat in _TD_STATS)
    stats.appearances += 1
    team_abbrev = PRO_TEAM_ABBREV.get(int_value(detail.get("proTeamId")), "")
    opponent = schedule.opponent(season, team_abbrev, week)
    # Grade this week's matchup off vendored, league-wide defense-vs-position ranks
    # (higher = weaker D). Built from all NFL players, so a player's own output never
    # influences how strong his own opponent looks.
    rank = dvp.rank(season, stats.position, opponent) if opponent else None
    if rank is not None:
        stats.matchup.append((points, rank))


def _scoring_weights(reader: FixtureReader) -> dict[int, float]:
    """statId -> fantasy points per unit, from the league's own scoring settings."""
    weights: dict[int, float] = {}
    for meta in reader.seasons():
        try:
            settings = _obj(reader.core(meta.season).get("settings"))
            scoring = _obj(settings.get("scoringSettings"))
            for item in objects(scoring.get("scoringItems"), "scoringItems"):
                points = float_value(item.get("points"))
                if points:
                    weights[int_value(item.get("statId"))] = points
        except (OSError, ValueError):
            continue
    return weights


# --------------------------------------------------------------- matchup


def _matchup_swing(pairs: list[tuple[float, float]]) -> float:
    """Relative scoring swing between easy (weak-D) and tough (strong-D) weeks."""
    easy = [pts for pts, rank in pairs if rank >= 0.6]
    tough = [pts for pts, rank in pairs if rank <= 0.4]
    if len(easy) < _MATCHUP_MIN_SPLIT or len(tough) < _MATCHUP_MIN_SPLIT:
        return 0.0
    overall = sum(pts for pts, _ in pairs) / len(pairs)
    if overall <= 0:
        return 0.0
    return (sum(easy) / len(easy) - sum(tough) / len(tough)) / overall


# --------------------------------------------------------------- assignment


def _assign_badges(records: dict[int, _PlayerStats], injuries: InjuryIndex) -> dict[int, str]:
    eligible = [stats for stats in records.values() if len(stats.points) >= _MIN_GAMES]
    result: dict[int, str] = {}
    # Score every badge against same-position peers so a stud TE isn't graded vs QBs.
    for group in _by_position(eligible):
        mean = {s.player_id: _mean(s.points) for s in group}
        cv = {s.player_id: _cv(s.points) for s in group}
        td = {s.player_id: _ratio(s.td_points, s.total_points) for s in group}
        # Injury-report weeks per season, joined from vendored NFL injury data. Both
        # numerator and denominator are scoped to the player's own injury-covered
        # seasons, so neither a late arrival's prior-team injuries nor the current
        # zero-data season skews the rate.
        injury = {
            s.player_id: injuries.burden(s.name, s.seasons)
            / max(injuries.covered_count(s.seasons), 1)
            for s in group
        }
        swing = {s.player_id: _matchup_swing(s.matchup) for s in group}
        catchers = [s for s in group if s.receptions > 0]
        ypr = {s.player_id: s.rec_yards / s.receptions for s in catchers}
        recpg = {s.player_id: s.receptions / len(s.points) for s in catchers}
        percentile = _Percentiles(
            mean=_percentiles(mean),
            cv=_percentiles(cv),
            td=_percentiles(td),
            injury=_percentiles(injury),
            swing=_percentiles(swing),
            ypr=_percentiles(ypr),
            recpg=_percentiles(recpg),
        )
        for stats in group:
            result[stats.player_id] = _pick_badge(
                stats, percentile, td=td, injury=injury, swing=swing, recpg=recpg
            )
    return result


@dataclass(frozen=True, slots=True)
class _Percentiles:
    mean: dict[int, float]
    cv: dict[int, float]
    td: dict[int, float]
    injury: dict[int, float]
    swing: dict[int, float]
    ypr: dict[int, float]
    recpg: dict[int, float]


def _badge_scores(
    stats: _PlayerStats,
    pct: _Percentiles,
    *,
    td: dict[int, float],
    injury: dict[int, float],
    swing: dict[int, float],
    recpg: dict[int, float],
) -> dict[str, float]:
    pid = stats.player_id
    p_mean = pct.mean.get(pid, 0.5)
    p_cv = pct.cv.get(pid, 0.5)
    scores: dict[str, float] = {}
    # Volatility spectrum, gated to the extremes so the middle is free for the
    # specialty badges below. "Elite" is reserved for genuinely top-tier scorers
    # (top quartile by mean at their position), so steady-but-mediocre players read
    # as High Floor instead.
    if p_cv >= 0.65:
        scores["Boom or Bust"] = p_cv
    if p_cv <= 0.40 and p_mean >= 0.75:
        scores["Elite Consistent"] = 0.5 * p_mean + 0.5 * (1 - p_cv)
    if p_cv <= 0.45 and p_mean < 0.75:
        scores["High Floor"] = 1 - p_cv
    # Touchdown-reliant. Skip QBs: every QB's scoring is TD-heavy, so the badge is
    # only distinctive for the RB/WR/TE whose value genuinely rides on touchdowns.
    if stats.position != "QB" and td.get(pid, 0.0) >= _TD_FRACTION_GATE:
        scores["TD Dependent"] = pct.td.get(pid, 0.0)
    # Reception-shape badges (pass-catchers with real volume only).
    if pid in pct.recpg and recpg.get(pid, 0.0) >= _MIN_REC_PER_GAME:
        p_ypr = pct.ypr.get(pid, 0.5)
        p_recpg = pct.recpg.get(pid, 0.5)
        if p_ypr >= 0.55:
            scores["Explosive"] = p_ypr
        if p_recpg >= 0.60 and p_ypr <= 0.45:
            scores["Screen Merchant"] = 0.5 * p_recpg + 0.5 * (1 - p_ypr)
    # Matchup-driven.
    if swing.get(pid, 0.0) > _MATCHUP_SWING_GATE:
        scores["Matchup Based"] = pct.swing.get(pid, 0.0)
    # Availability.
    if injury.get(pid, 0.0) >= _INJURY_RATE_GATE:
        scores["Injury Risk"] = pct.injury.get(pid, 0.0)
    return scores


def _pick_badge(
    stats: _PlayerStats,
    pct: _Percentiles,
    *,
    td: dict[int, float],
    injury: dict[int, float],
    swing: dict[int, float],
    recpg: dict[int, float],
) -> str:
    scores = _badge_scores(stats, pct, td=td, injury=injury, swing=swing, recpg=recpg)
    if scores:
        order = {badge: index for index, badge in enumerate(BADGES)}
        return max(scores, key=lambda badge: (scores[badge], -order[badge]))
    # No gate fired (a mid-volatility, unremarkable line). Fall back using both
    # output and volatility so every eligible player still gets a sensible label:
    # high volatility reads boom/bust, otherwise productive-vs-replacement splits
    # elite-ish from floor.
    p_mean = pct.mean.get(stats.player_id, 0.5)
    p_cv = pct.cv.get(stats.player_id, 0.5)
    if p_cv >= 0.55:
        return "Boom or Bust"
    if p_mean >= 0.60:
        return "Elite Consistent"
    return "High Floor"


# -------------------------------------------------------------------- helpers


def _by_position(players: list[_PlayerStats]) -> list[list[_PlayerStats]]:
    groups: dict[str, list[_PlayerStats]] = {}
    for stats in players:
        groups.setdefault(stats.position, []).append(stats)
    return list(groups.values())


def _percentiles[Key](values: dict[Key, float]) -> dict[Key, float]:
    """Midrank percentile in [0, 1]; ties share their average rank."""
    if not values:
        return {}
    items = list(values.values())
    n = len(items)
    out: dict[Key, float] = {}
    for key, value in values.items():
        less = sum(1 for other in items if other < value)
        equal = sum(1 for other in items if other == value)
        out[key] = (less + 0.5 * equal) / n
    return out


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _cv(values: list[float]) -> float:
    mean = _mean(values)
    if mean <= 0 or len(values) < 2:
        return 0.0
    variance = sum((value - mean) ** 2 for value in values) / (len(values) - 1)
    return math.sqrt(variance) / mean


def _ratio(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator > 0 else 0.0


def _raw(applied: JsonObject, stat: int, weights: dict[int, float]) -> float:
    weight = weights.get(stat, 0.0)
    return float_value(applied.get(str(stat))) / weight if weight else 0.0


def _obj(value: JsonValue) -> JsonObject:
    return value if isinstance(value, dict) else {}


def _safe_int(text: str) -> int:
    try:
        return int(text)
    except (TypeError, ValueError):
        return 0
