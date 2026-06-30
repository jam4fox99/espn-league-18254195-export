"""Front-page trade highlights derived from the VOR trade grades.

* **Best** and **Worst** are forced to be *different* underlying trades, so the feed
  shows one team's heist and a separate team's blunder rather than the two sides of a
  single lopsided deal.
* **Most Even / Fair** is the trade with the smallest VOR value gap, gated so both
  sides actually exchanged meaningful value, tie-broken toward *both sides filling a
  need*.
* A lightweight per-manager **fair-trader** stat (average value gap of their trades).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from mygm_worker.analytics.json_tools import as_array, int_value, string_value
from mygm_worker.analytics.trade_grades import GRADE_ORDER

if TYPE_CHECKING:
    from mygm_worker.analytics.models import JsonObject
    from mygm_worker.analytics.trade_grades import SideGrade, TradeGrade

# A trade only qualifies as "even/fair" if both sides moved at least this much VOR —
# it filters trivial nothing-for-nothing swaps that have a tiny gap by default.
_MIN_MEANINGFUL_VOR: Final = 20.0


@dataclass(frozen=True, slots=True)
class TradeHighlights:
    best: JsonObject | None
    worst: JsonObject | None
    most_even: JsonObject | None
    fair_trader_by_manager: dict[str, JsonObject]


def trade_highlights(
    graded: list[tuple[JsonObject, TradeGrade]],
    names: dict[str, str],
) -> TradeHighlights:
    ranked = sorted(
        graded,
        key=lambda item: max(side.composite for side in item[1].sides),
        reverse=True,
    )
    best = _best_side_highlight(ranked, names)
    best_trade_id = string_value(best.get("tradeId")) if best else None
    worst = _worst_side_highlight(ranked, names, exclude_trade=best_trade_id)
    most_even = _most_even_highlight(graded, names)
    return TradeHighlights(
        best=best,
        worst=worst,
        most_even=most_even,
        fair_trader_by_manager=_fair_traders(graded, names),
    )


def _best_side_highlight(
    ranked: list[tuple[JsonObject, TradeGrade]],
    names: dict[str, str],
) -> JsonObject | None:
    best_pair: tuple[JsonObject, TradeGrade, SideGrade] | None = None
    for row, grade in ranked:
        winner = max(grade.sides, key=lambda side: side.composite)
        if best_pair is None or winner.composite > best_pair[2].composite:
            best_pair = (row, grade, winner)
    if best_pair is None:
        return None
    row, grade, side = best_pair
    return _side_highlight("Best trade", row, grade, side, names)


def _worst_side_highlight(
    ranked: list[tuple[JsonObject, TradeGrade]],
    names: dict[str, str],
    *,
    exclude_trade: str | None,
) -> JsonObject | None:
    worst_pair: tuple[JsonObject, TradeGrade, SideGrade] | None = None
    for row, grade in ranked:
        if grade.trade_id == exclude_trade:
            continue
        loser = min(grade.sides, key=lambda side: side.composite)
        if worst_pair is None or loser.composite < worst_pair[2].composite:
            worst_pair = (row, grade, loser)
    if worst_pair is None:
        return None
    row, grade, side = worst_pair
    return _side_highlight("Worst trade", row, grade, side, names)


def _most_even_highlight(
    graded: list[tuple[JsonObject, TradeGrade]],
    names: dict[str, str],
) -> JsonObject | None:
    candidates = [
        (row, grade)
        for row, grade in graded
        if len(grade.sides) == 2
        and all(abs(side.received_vor) >= _MIN_MEANINGFUL_VOR for side in grade.sides)
    ]
    if not candidates:
        return None
    # Smallest value gap wins; ties broken toward both sides filling a need.
    row, grade = min(
        candidates,
        key=lambda item: (item[1].value_gap, 0 if item[1].both_fill_need else 1),
    )
    summary = " ↔ ".join(
        f"{names.get(side.manager_key, side.manager_key)} got {_side_assets(row, side.team_id)}"
        for side in grade.sides
    )
    return {
        "tradeId": grade.trade_id,
        "label": "Most even trade",
        "season": grade.season,
        "valueGap": grade.value_gap,
        "bothFillNeed": grade.both_fill_need,
        "managerKeys": [side.manager_key for side in grade.sides],
        "managerNames": [names.get(side.manager_key, side.manager_key) for side in grade.sides],
        "detail": summary,
    }


def _side_highlight(
    label: str,
    row: JsonObject,
    grade: TradeGrade,
    side: SideGrade,
    names: dict[str, str],
) -> JsonObject:
    other = next((s for s in grade.sides if s.team_id != side.team_id), None)
    return {
        "tradeId": grade.trade_id,
        "label": label,
        "season": grade.season,
        "managerKey": side.manager_key,
        "displayName": names.get(side.manager_key, side.manager_key),
        "grade": side.grade,
        "netVor": side.net_vor,
        "composite": side.composite,
        "counterpartyKey": other.manager_key if other else None,
        "counterpartyName": names.get(other.manager_key, "") if other else None,
        "received": _side_assets(row, side.team_id),
        "detail": (
            f"{names.get(side.manager_key, side.manager_key)} acquired "
            f"{_side_assets(row, side.team_id)} ({side.net_vor:+.1f} net VOR)"
        ),
    }


def _fair_traders(
    graded: list[tuple[JsonObject, TradeGrade]],
    names: dict[str, str],
) -> dict[str, JsonObject]:
    gaps: defaultdict[str, list[float]] = defaultdict(list)
    for _row, grade in graded:
        for side in grade.sides:
            gaps[side.manager_key].append(grade.value_gap)
    result: dict[str, JsonObject] = {}
    for manager_key, values in gaps.items():
        result[manager_key] = {
            "managerKey": manager_key,
            "displayName": names.get(manager_key, manager_key),
            "tradeCount": len(values),
            # Lower average gap = fairer trader.
            "averageValueGap": round(sum(values) / len(values), 4) if values else 0.0,
        }
    return result


def _side_assets(row: JsonObject, team_id: int) -> str:
    for side in as_array(row.get("sides"), "sides"):
        if not isinstance(side, dict) or int_value(side.get("teamId")) != team_id:
            continue
        names = [
            string_value(asset.get("name"), "a player")
            for asset in as_array(side.get("receivedAssets"), "receivedAssets")
            if isinstance(asset, dict)
        ]
        if names:
            return ", ".join(names[:4])
    return "assets"


def grade_rank(grade: str) -> int:
    """Index of ``grade`` in the A+..F ladder (lower = better); len for unknown."""
    return GRADE_ORDER.index(grade) if grade in GRADE_ORDER else len(GRADE_ORDER)
