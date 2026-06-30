"""VOR-based trade re-grading.

Each completed trade is graded per side from three ingredients:

* **value** — net Value Over Replacement (received VOR - given-up VOR), run through a
  saturating (logistic) transform so a +200 and a +80 net both land near the top
  instead of racing to extremes. This alone kills the old bimodal A+/F distribution.
* **fit** — how well the acquired players hit the team's positional needs at the time
  of the trade (see analytics/roster_fit.py). Fit can *rescue* a points-loss: a
  genuine need-fill lifts the grade rather than only tempering a win.
* **composite** = 0.65 * value + 0.35 * fit, mapped to a full-granularity letter grade
  through **fixed, absolute cutoffs** calibrated once to the league's real spread, so
  grades are permanent (a trade's grade never moves because of other trades) and the
  distribution is bell-shaped with A+/F genuinely rare.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from mygm_worker.analytics.json_tools import as_array, int_value, string_value
from mygm_worker.analytics.roster_fit import FIT_POSITIONS

if TYPE_CHECKING:
    from mygm_worker.analytics.models import JsonObject
    from mygm_worker.analytics.roster_fit import FitIndex
    from mygm_worker.analytics.vor import VorModel

COMPOSITE_VALUE_WEIGHT: Final = 0.65
COMPOSITE_FIT_WEIGHT: Final = 0.35

# Logistic scale on net VOR: a side ~VALUE_SCALE VOR ahead reads as a clear win
# (~0.73), a blowout saturates, and small edges stay near the 0.5 midpoint.
VALUE_SCALE: Final = 45.0

# Descending absolute cutoffs on the composite [0,1]; first whose threshold the
# composite meets wins. Calibrated to league 18254195 so A+/F are rare (~3-5%) and the
# B/C middle is fat (~55-60%). See tests/analytics/test_trade_grades.py for the gate.
GRADE_CUTOFFS: Final[tuple[tuple[float, str], ...]] = (
    (0.869, "A+"),
    (0.783, "A"),
    (0.710, "A-"),
    (0.645, "B+"),
    (0.564, "B"),
    (0.512, "B-"),
    (0.470, "C+"),
    (0.397, "C"),
    (0.332, "C-"),
    (0.271, "D+"),
    (0.215, "D"),
    (0.162, "D-"),
)
_LOWEST_GRADE: Final = "F"

GRADE_ORDER: Final[tuple[str, ...]] = (
    *(grade for _, grade in GRADE_CUTOFFS),
    _LOWEST_GRADE,
)


@dataclass(frozen=True, slots=True)
class SideGrade:
    manager_key: str
    team_id: int
    received_vor: float
    given_up_vor: float
    net_vor: float
    value_score: float
    fit_score: float
    composite: float
    grade: str
    needs_filled: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class TradeGrade:
    trade_id: str
    season: int
    week: int
    sides: tuple[SideGrade, ...]
    value_gap: float
    winner_manager_key: str | None
    both_fill_need: bool


def grade_trade_event(
    row: JsonObject,
    *,
    vor_model: VorModel,
    position_by_player: dict[int, str],
    fit_index: FitIndex,
    team_lookup: dict[tuple[int, int], str],
) -> TradeGrade | None:
    """Grade a single ``trade_event_rows`` row, or ``None`` when it is not score-eligible."""
    if row.get("scoreEligible") is not True:
        return None
    season = int_value(row.get("season"))
    week = int_value(row.get("week"))
    sides = [side for side in as_array(row.get("sides"), "sides") if isinstance(side, dict)]
    if len(sides) != 2:
        return None
    received = [
        _side_received_vor(side, season, vor_model, position_by_player) for side in sides
    ]
    side_grades: list[SideGrade] = []
    for index, side in enumerate(sides):
        received_vor = received[index][0]
        given_up_vor = received[1 - index][0]
        side_grades.append(
            _side_grade(
                side,
                season=season,
                week=week,
                received_vor=received_vor,
                given_up_vor=given_up_vor,
                received_positions=received[index][1],
                fit_index=fit_index,
                team_lookup=team_lookup,
            )
        )
    value_gap = round(abs(received[0][0] - received[1][0]), 4)
    winner = _winner(side_grades)
    both_fill_need = all(side.needs_filled for side in side_grades)
    return TradeGrade(
        trade_id=string_value(row.get("tradeId")),
        season=season,
        week=week,
        sides=tuple(side_grades),
        value_gap=value_gap,
        winner_manager_key=winner,
        both_fill_need=both_fill_need,
    )


_NEED_FILL_THRESHOLD: Final = 0.45


def value_score(net_vor: float) -> float:
    """Saturating transform of net VOR into [0, 1]; 0.5 at an even trade."""
    return round(1.0 / (1.0 + math.exp(-net_vor / VALUE_SCALE)), 4)


def grade_for_composite(composite: float) -> str:
    for threshold, grade in GRADE_CUTOFFS:
        if composite >= threshold:
            return grade
    return _LOWEST_GRADE


def _side_received_vor(
    side: JsonObject,
    season: int,
    vor_model: VorModel,
    position_by_player: dict[int, str],
) -> tuple[float, dict[str, float]]:
    total = 0.0
    by_position: dict[str, float] = {}
    for asset in as_array(side.get("receivedAssets"), "receivedAssets"):
        if not isinstance(asset, dict):
            continue
        player_id = int_value(asset.get("playerId"))
        position = position_by_player.get(player_id, "")
        weekly = asset.get("weeklyPoints")
        if not isinstance(weekly, dict):
            continue
        asset_vor, _ = vor_model.value_for_weeks(season, position, weekly)
        total += asset_vor
        if position:
            by_position[position] = by_position.get(position, 0.0) + asset_vor
    return round(total, 4), by_position


def _side_grade(
    side: JsonObject,
    *,
    season: int,
    week: int,
    received_vor: float,
    given_up_vor: float,
    received_positions: dict[str, float],
    fit_index: FitIndex,
    team_lookup: dict[tuple[int, int], str],
) -> SideGrade:
    team_id = int_value(side.get("teamId"))
    manager_key = team_lookup.get((season, team_id), f"unresolved:{season}:{team_id}")
    net_vor = round(received_vor - given_up_vor, 4)
    fit, needs = _fit_score(
        season, week, manager_key, received_positions, fit_index
    )
    value = value_score(net_vor)
    composite = round(COMPOSITE_VALUE_WEIGHT * value + COMPOSITE_FIT_WEIGHT * fit, 4)
    return SideGrade(
        manager_key=manager_key,
        team_id=team_id,
        received_vor=received_vor,
        given_up_vor=given_up_vor,
        net_vor=net_vor,
        value_score=value,
        fit_score=fit,
        composite=composite,
        grade=grade_for_composite(composite),
        needs_filled=needs,
    )


def _fit_score(
    season: int,
    week: int,
    manager_key: str,
    received_positions: dict[str, float],
    fit_index: FitIndex,
) -> tuple[float, tuple[str, ...]]:
    relevant = {
        position: value
        for position, value in received_positions.items()
        if position in FIT_POSITIONS
    }
    if not relevant:
        return 0.5, ()
    weighted_total = 0.0
    weight_sum = 0.0
    needs_filled: list[str] = []
    for position, asset_vor in relevant.items():
        fit = fit_index.fit_value(season, manager_key, week, position)
        weight = max(asset_vor, 0.0)
        weighted_total += fit * weight
        weight_sum += weight
        if fit_index.need(season, manager_key, week, position) >= _NEED_FILL_THRESHOLD:
            needs_filled.append(position)
    if weight_sum <= 0.0:
        # Only negative-value acquisitions: average their positions' centered fit.
        average = sum(
            fit_index.fit_value(season, manager_key, week, position) for position in relevant
        ) / len(relevant)
        return round(average, 4), tuple(sorted(needs_filled))
    return round(weighted_total / weight_sum, 4), tuple(sorted(needs_filled))


def _winner(side_grades: list[SideGrade]) -> str | None:
    ranked = sorted(side_grades, key=lambda side: side.net_vor, reverse=True)
    if len(ranked) < 2 or ranked[0].net_vor <= ranked[1].net_vor:
        return None
    return ranked[0].manager_key
