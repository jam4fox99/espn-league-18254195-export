"""Value Over Replacement (VOR) engine.

A player's value is measured *over the last starter at his position* rather than in
raw fantasy points, which is what kills QB inflation: in a one-QB league only a
handful of QBs ever start, so the replacement bar sits high (~QB10-13, ≈18 PPG) and
even a strong QB clears it by little, while a stud RB/WR towers over a much deeper
replacement pool.

Replacement levels are computed **per season, per position** from the *whole* NFL
player pool in the export (the objective startable pool, not just league-rostered
players). The replacement rank is the league's own starter demand — dedicated lineup
slots times team count, plus flex demand distributed across the flex-eligible
positions — read from each season's settings, so the engine is league-agnostic.

A player's value over a window is::

    Σ over the weeks he was active in the window of (week_points - replacement_ppw)

where ``replacement_ppw`` is the per-week baseline for his position that season. DNP
weeks (empty ``appliedStats`` + 0 points) are skipped, matching the badge math — they
are simply absent from ``weekly_points`` in this export.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from mygm_worker.analytics.json_tools import float_value, int_value
from mygm_worker.analytics.player_directory import POSITIONS

if TYPE_CHECKING:
    from collections.abc import Mapping

    from mygm_worker.analytics.models import JsonObject, JsonValue
    from mygm_worker.analytics.reader import FixtureReader

# Positions that carry a VOR baseline. K/D-ST are included (their tiny value still
# counts) but are excluded from roster-fit need (see analytics/roster_fit.py).
VOR_POSITIONS: Final = frozenset({"QB", "RB", "WR", "TE", "K", "D/ST"})

# Lineup slot id -> the single position it dedicates a starter to.
_DEDICATED_SLOT_POSITION: Final[dict[int, str]] = {
    0: "QB",
    2: "RB",
    4: "WR",
    6: "TE",
    17: "K",
    16: "D/ST",
}
# Flex-type lineup slots -> the positions eligible to fill them.
_FLEX_SLOT_POSITIONS: Final[dict[int, frozenset[str]]] = {
    3: frozenset({"RB", "WR"}),
    5: frozenset({"WR", "TE"}),
    23: frozenset({"RB", "WR", "TE"}),
    7: frozenset({"QB", "RB", "WR", "TE"}),
}

# A "startable regular" must have been active for at least this share of a season's
# weeks to enter the replacement pool. This filters one-week wonders and the
# games-missed PPG inflation that would otherwise distort the baseline (e.g. a player
# ranked at the replacement slot by total points but who only played 9 games).
REPLACEMENT_MIN_GAMES_FRACTION: Final = 0.45
REPLACEMENT_MIN_GAMES_FLOOR: Final = 4

# Per-position multiplier on the starter-demand replacement rank. >1 pushes the
# baseline deeper (an easier bar); <1 raises it. The QB entry is the documented
# tuning knob: a one-QB league's demand already lands the baseline at ~QB(team count)
# ≈18 PPG, validated against league 18254195; lower QB below 1.0 to raise the bar
# toward QB10/~20 PPG if good QBs still inflate. Default (absent) = 1.0.
REPLACEMENT_RANK_SCALE: Final[dict[str, float]] = {}

_DEFAULT_SEASON_WEEKS: Final = 17


@dataclass(frozen=True, slots=True)
class VorModel:
    """Per-(season, position) replacement baselines and the starter demand behind them."""

    replacement_per_week: dict[tuple[int, str], float]
    starter_demand: dict[tuple[int, str], int]

    def replacement(self, season: int, position: str) -> float:
        """Replacement points-per-week for ``position`` in ``season`` (0 when unknown)."""
        return self.replacement_per_week.get((season, position), 0.0)

    def value_for_weeks(
        self,
        season: int,
        position: str,
        weekly_points: Mapping[str, JsonValue],
    ) -> tuple[float, int]:
        """VOR for an already-windowed ``{week: points}`` map: (vor, weeks_counted).

        Every recorded week is charged the replacement baseline — a played-but-scoreless
        week (real 0 with stats) correctly reads as negative VOR; DNP weeks are absent.
        """
        replacement = self.replacement(season, position)
        total = 0.0
        weeks = 0
        for points in weekly_points.values():
            total += float_value(points) - replacement
            weeks += 1
        return round(total, 4), weeks

    def window_value(
        self,
        season: int,
        position: str,
        weekly_points: Mapping[str, JsonValue],
        start_week: int,
        end_week: int,
    ) -> float:
        """VOR over the inclusive ``[start_week, end_week]`` slice of ``weekly_points``."""
        replacement = self.replacement(season, position)
        total = 0.0
        for week_text, points in weekly_points.items():
            week = int_value(week_text)
            if start_week <= week <= end_week:
                total += float_value(points) - replacement
        return round(total, 4)


def build_vor_model(reader: FixtureReader) -> VorModel:
    """Compute replacement baselines for every (season, position) in the export."""
    demand = _starter_demand(reader)
    season_weeks = {season.season: season.final_week for season in reader.seasons()}
    pools = _position_pools(reader)
    replacement: dict[tuple[int, str], float] = {}
    for (season, position), per_game in pools.items():
        weeks = season_weeks.get(season, _DEFAULT_SEASON_WEEKS)
        min_games = max(REPLACEMENT_MIN_GAMES_FLOOR, round(weeks * REPLACEMENT_MIN_GAMES_FRACTION))
        qualified = sorted(
            (ppg for ppg, games in per_game if games >= min_games), reverse=True
        )
        if not qualified:
            qualified = sorted((ppg for ppg, _ in per_game), reverse=True)
        if not qualified:
            continue
        rank = demand.get((season, position), len(qualified))
        rank = max(1, round(rank * REPLACEMENT_RANK_SCALE.get(position, 1.0)))
        index = min(rank, len(qualified)) - 1
        replacement[(season, position)] = round(qualified[index], 4)
    return VorModel(replacement_per_week=replacement, starter_demand=demand)


def position_for_lookup_entry(player: JsonObject) -> str:
    """Fantasy position for a ``player_lookup`` record from its ``defaultPositionId``."""
    return POSITIONS.get(int_value(player.get("defaultPositionId")), "")


def _position_pools(reader: FixtureReader) -> dict[tuple[int, str], list[tuple[float, int]]]:
    pools: defaultdict[tuple[int, str], list[tuple[float, int]]] = defaultdict(list)
    for player in reader.player_lookup().values():
        if not isinstance(player, dict):
            continue
        position = position_for_lookup_entry(player)
        if position not in VOR_POSITIONS:
            continue
        details = player.get("weekly_details")
        if not isinstance(details, dict):
            continue
        for season_text, weeks in details.items():
            if not isinstance(weeks, dict):
                continue
            points = _active_week_points(weeks)
            if points:
                pools[(int_value(season_text), position)].append(
                    (sum(points) / len(points), len(points))
                )
    return dict(pools)


def _active_week_points(weeks: JsonObject) -> list[float]:
    points: list[float] = []
    for detail in weeks.values():
        if not isinstance(detail, dict):
            continue
        value = float_value(detail.get("points"))
        applied = detail.get("appliedStats")
        # DNP marker: empty appliedStats + 0 points. Skip so means/games stay honest.
        if value == 0 and not (isinstance(applied, dict) and applied):
            continue
        points.append(value)
    return points


def _starter_demand(reader: FixtureReader) -> dict[tuple[int, str], int]:
    demand: dict[tuple[int, str], int] = {}
    for season in reader.seasons():
        slots = _lineup_slot_counts(reader, season.season)
        teams = _team_count(reader, season.season)
        if not slots or teams == 0:
            continue
        base: defaultdict[str, float] = defaultdict(float)
        flex: list[tuple[frozenset[str], float]] = []
        for slot_id, count in slots.items():
            slot_demand = float(count * teams)
            position = _DEDICATED_SLOT_POSITION.get(slot_id)
            if position is not None:
                base[position] += slot_demand
                continue
            eligible = _FLEX_SLOT_POSITIONS.get(slot_id)
            if eligible is not None:
                flex.append((eligible, slot_demand))
        resolved = dict(base)
        for eligible, slot_demand in flex:
            weights = {position: base.get(position, 0.0) for position in eligible}
            total = sum(weights.values())
            for position in eligible:
                share = weights[position] / total if total > 0 else 1.0 / len(eligible)
                resolved[position] = resolved.get(position, 0.0) + slot_demand * share
        for position, value in resolved.items():
            demand[(season.season, position)] = max(1, round(value))
    return demand


def _lineup_slot_counts(reader: FixtureReader, season: int) -> dict[int, int]:
    core = reader.core(season)
    settings = core.get("settings")
    if not isinstance(settings, dict):
        return {}
    roster_settings = settings.get("rosterSettings")
    if not isinstance(roster_settings, dict):
        return {}
    counts = roster_settings.get("lineupSlotCounts")
    if not isinstance(counts, dict):
        return {}
    return {
        int_value(slot): int_value(count)
        for slot, count in counts.items()
        if int_value(count) > 0
    }


def _team_count(reader: FixtureReader, season: int) -> int:
    teams = reader.core(season).get("teams")
    return len(teams) if isinstance(teams, list) else 0
