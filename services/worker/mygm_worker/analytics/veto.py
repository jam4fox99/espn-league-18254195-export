"""Veto-likelihood model — "does this trade look fair *right now*?"

This is a distinct lens from the trade grade. The grade asks what a trade returned
(realized VOR, hindsight). Veto asks whether the deal made sense at the moment it was
made, from each team's roster and the players' **rest-of-season potential** —
preseason draft capital (ADP) plus season-to-date trajectory. It must never depend on
ADP being present: League News targets the most-recent season, which has no vendored
preseason ADP, so potential falls back to season-to-date production + prior-season
finish, with ADP only nudging when available.

Three weighted signals, calibrated so ordinary trades sit under ~20% and a lopsided +
need-less + repeat-pattern deal climbs past ~70%:

1. **value imbalance** (primary) — gap in projected potential between the sides.
2. **one-sided need** — the team that gave up the better projection got nothing it
   needed (spikes); both sides filling needs (drops).
3. **collusion pattern** — repeated one-directional value flow between the same pair.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from mygm_worker.analytics.json_tools import as_array, float_value, int_value, string_value
from mygm_worker.analytics.roster_fit import FIT_POSITIONS

if TYPE_CHECKING:
    from mygm_worker.analytics.adp import AdpIndex
    from mygm_worker.analytics.models import JsonObject
    from mygm_worker.analytics.roster_fit import FitIndex
    from mygm_worker.analytics.trade_grades import TradeGrade
    from mygm_worker.analytics.vor import VorModel

# ADP at which the draft-capital nudge is neutral; better picks lift potential, later
# picks trim it, bounded to +/-30%.
_BASELINE_ADP: Final = 80.0
_FORM_MIN_WEEKS: Final = 2
_PRIOR_MIN_WEEKS: Final = 4
_NEED_THRESHOLD: Final = 0.45

# Value imbalance is the primary driver; collusion pattern adds on top. Filling a real
# need *relieves* the imbalance sting (a lopsided-looking deal that fills a genuine hole
# is more defensible) rather than adding a separate spike.
_WEIGHT_IMBALANCE: Final = 0.80
_WEIGHT_COLLUSION: Final = 0.20
_NEED_RELIEF: Final = 0.45


@dataclass(frozen=True, slots=True)
class VetoResult:
    trade_id: str
    percent: float
    band: str
    signals: dict[str, float]
    rationale_by_manager: dict[str, str]


@dataclass(frozen=True, slots=True)
class _SidePotential:
    manager_key: str
    team_id: int
    potential: float
    top_asset: str
    need: float
    need_position: str


def veto_likelihoods(
    graded: list[tuple[JsonObject, TradeGrade]],
    *,
    players: JsonObject,
    fit_index: FitIndex,
    adp_index: AdpIndex,
    vor_model: VorModel,
    position_by_player: dict[int, str],
) -> dict[str, VetoResult]:
    """Veto likelihood for every two-sided graded trade, keyed by trade id."""
    side_potentials: dict[str, tuple[_SidePotential, _SidePotential]] = {}
    pair_flow: defaultdict[tuple[str, str], list[float]] = defaultdict(list)
    for row, grade in graded:
        if len(grade.sides) != 2:
            continue
        sides = tuple(
            _side_potential(
                row,
                grade,
                side_index,
                players,
                adp_index,
                vor_model,
                position_by_player,
                fit_index,
            )
            for side_index in (0, 1)
        )
        side_potentials[grade.trade_id] = (sides[0], sides[1])
        _record_flow(pair_flow, sides[0], sides[1])
    collusion = _collusion_strength(pair_flow)
    return {
        trade_id: _veto_result(trade_id, side_a, side_b, collusion)
        for trade_id, (side_a, side_b) in side_potentials.items()
    }


def _side_potential(
    row: JsonObject,
    grade: TradeGrade,
    side_index: int,
    players: JsonObject,
    adp_index: AdpIndex,
    vor_model: VorModel,
    position_by_player: dict[int, str],
    fit_index: FitIndex,
) -> _SidePotential:
    side = grade.sides[side_index]
    raw_side = _raw_side(row, side.team_id)
    total = 0.0
    top_asset = ""
    top_value = float("-inf")
    best_need = 0.0
    best_need_pos = ""
    for asset in as_array(raw_side.get("receivedAssets"), "receivedAssets"):
        if not isinstance(asset, dict):
            continue
        player_id = int_value(asset.get("playerId"))
        name = string_value(asset.get("name"), "a player")
        position = position_by_player.get(player_id, "")
        potential = _asset_potential(
            player_id, name, position, grade.season, grade.week, players, adp_index, vor_model
        )
        total += potential
        if potential > top_value:
            top_value = potential
            top_asset = name
        if position in FIT_POSITIONS:
            need = fit_index.need(grade.season, side.manager_key, grade.week, position)
            if need > best_need:
                best_need = need
                best_need_pos = position
    return _SidePotential(
        manager_key=side.manager_key,
        team_id=side.team_id,
        potential=round(total, 4),
        top_asset=top_asset,
        need=best_need,
        need_position=best_need_pos,
    )


def _asset_potential(
    player_id: int,
    name: str,
    position: str,
    season: int,
    trade_week: int,
    players: JsonObject,
    adp_index: AdpIndex,
    vor_model: VorModel,
) -> float:
    player = players.get(str(player_id))
    weekly = player.get("weekly_points") if isinstance(player, dict) else None
    weekly = weekly if isinstance(weekly, dict) else {}
    form = _ppg(
        [
            float_value(points)
            for week_text, points in _season_weeks(weekly, season).items()
            if int_value(week_text) < trade_week
        ],
        _FORM_MIN_WEEKS,
    )
    prior = _ppg(
        [float_value(points) for points in _season_weeks(weekly, season - 1).values()],
        _PRIOR_MIN_WEEKS,
    )
    if form is not None and prior is not None:
        base = 0.6 * form + 0.4 * prior
    elif form is not None:
        base = form
    elif prior is not None:
        base = prior
    else:
        # No production signal at all: lean on the position's replacement baseline so an
        # unknown asset is treated as roughly replacement-level rather than zero.
        base = vor_model.replacement(season, position)
    adp = adp_index.adp(season, name)
    if adp is not None:
        factor = min(1.3, max(0.7, 1.0 + (_BASELINE_ADP - adp) / _BASELINE_ADP * 0.3))
        base *= factor
    return max(base, 0.0)


def _veto_result(
    trade_id: str,
    side_a: _SidePotential,
    side_b: _SidePotential,
    collusion: dict[tuple[str, str], float],
) -> VetoResult:
    total = side_a.potential + side_b.potential
    gap = abs(side_a.potential - side_b.potential)
    imbalance = min(1.0, gap / total) if total > 0 else 0.0
    fleeced = side_a if side_a.potential <= side_b.potential else side_b
    winner = side_b if fleeced is side_a else side_a
    # The fleeced team filling a genuine need relieves the imbalance sting.
    imbalance_term = imbalance * (1.0 - _NEED_RELIEF * fleeced.need)
    pair = _pair_key(side_a.manager_key, side_b.manager_key)
    collusion_signal = collusion.get(pair, 0.0)
    raw = _WEIGHT_IMBALANCE * imbalance_term + _WEIGHT_COLLUSION * collusion_signal
    percent = round(min(100.0, max(0.0, raw * 100.0)), 1)
    return VetoResult(
        trade_id=trade_id,
        percent=percent,
        band=_band(percent),
        signals={
            "imbalance": round(imbalance, 4),
            "oneSidedNeed": round(max(0.0, 1.0 - fleeced.need), 4),
            "collusion": round(collusion_signal, 4),
        },
        rationale_by_manager={
            winner.manager_key: _winner_rationale(winner),
            fleeced.manager_key: _fleeced_rationale(fleeced),
        },
    )


def _winner_rationale(side: _SidePotential) -> str:
    asset = side.top_asset or "the better assets"
    return f"Lands {asset} and the higher projected return."


def _fleeced_rationale(side: _SidePotential) -> str:
    if side.need >= _NEED_THRESHOLD and side.need_position:
        return f"Gives up the better projection but fills a real need at {side.need_position}."
    return "Sends out the better projection without filling an obvious need."


def _band(percent: float) -> str:
    if percent >= 60:
        return "Collusion risk"
    if percent >= 25:
        return "Lean veto"
    return "Looks fair"


def _record_flow(
    pair_flow: defaultdict[tuple[str, str], list[float]],
    side_a: _SidePotential,
    side_b: _SidePotential,
) -> None:
    pair = _pair_key(side_a.manager_key, side_b.manager_key)
    low, _high = sorted((side_a.manager_key, side_b.manager_key))
    # Signed toward the alphabetically-first manager so flows are comparable across trades.
    signed = side_a.potential - side_b.potential
    if side_a.manager_key != low:
        signed = -signed
    pair_flow[pair].append(signed)


def _collusion_strength(
    pair_flow: defaultdict[tuple[str, str], list[float]],
) -> dict[tuple[str, str], float]:
    strength: dict[tuple[str, str], float] = {}
    for pair, flows in pair_flow.items():
        total = sum(abs(flow) for flow in flows)
        net = abs(sum(flows))
        directionality = net / total if total > 0 else 0.0
        # Collusion is rare by construction: it needs a *repeated* (3+ trades) and
        # *dominantly* one-directional value flow between the same pair.
        volume = min(1.0, max(0, len(flows) - 2) / 3.0)
        strength[pair] = round(directionality * volume, 4) if directionality > 0.5 else 0.0
    return strength


def _pair_key(manager_a: str, manager_b: str) -> tuple[str, str]:
    return (manager_a, manager_b) if manager_a <= manager_b else (manager_b, manager_a)


def _raw_side(row: JsonObject, team_id: int) -> JsonObject:
    for side in as_array(row.get("sides"), "sides"):
        if isinstance(side, dict) and int_value(side.get("teamId")) == team_id:
            return side
    return {}


def _season_weeks(weekly: JsonObject, season: int) -> JsonObject:
    value = weekly.get(str(season))
    return value if isinstance(value, dict) else {}


def _ppg(points: list[float], minimum: int) -> float | None:
    if len(points) < minimum:
        return None
    return sum(points) / len(points)
