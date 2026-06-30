from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

type JsonValue = None | bool | int | float | str | list[JsonValue] | dict[str, JsonValue]
type JsonObject = dict[str, JsonValue]


@runtime_checkable
class _TradeEventsModule(Protocol):
    def trade_event_rows(self, reader: _RowsReader) -> tuple[JsonObject, ...]: ...

    def filter_trade_events(
        self,
        rows: tuple[JsonObject, ...],
        *,
        season: int | None = None,
        manager_key: str | None = None,
        mine_only: bool = False,
        sort: str = "chronological",
    ) -> tuple[JsonObject, ...]: ...


def _load_trade_events_module() -> _TradeEventsModule:
    module_path = (
        Path(__file__).parents[2] / "mygm_worker" / "analytics" / "trade_events.py"
    )
    spec = importlib.util.spec_from_file_location("trade_events_under_test", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    assert isinstance(module, _TradeEventsModule)
    return module


@dataclass(frozen=True, slots=True)
class _RowsReader:
    rows: tuple[JsonObject, ...]

    def trade_grade_rows(self) -> list[JsonObject]:
        return [dict(row) for row in self.rows]


def test_trade_event_rows_normalize_graded_trade_for_browsing() -> None:
    # Given: a graded duplicate-group trade row from the ESPN trade grade output.
    reader = _RowsReader(
        rows=(
            {
                "trade_id": "101",
                "related_transaction_id": "100",
                "canonical_trade_key": "canonical:2024:week5:teams1-2",
                "canonical_group_size": 2,
                "canonical_group_trade_ids": ["100", "101"],
                "season": 2024,
                "week": 5,
                "score_start_week": 6,
                "score_end_week": 17,
                "trade_date_utc": "2024-10-08T13:00:00+00:00",
                "team_a_id": 1,
                "team_a_name": "North Stars",
                "team_a_points": 82.25,
                "team_a_grade": "A",
                "team_a_players": [
                    {
                        "playerId": 11,
                        "name": "Alpha RB",
                        "fromTeamId": 2,
                        "toTeamId": 1,
                        "post_trade_points": 82.25,
                        "weekly_points": {"6": 12.25, "7": 10.0},
                    },
                ],
                "team_b_id": 2,
                "team_b_name": "South Sails",
                "team_b_points": 50.0,
                "team_b_grade": "C",
                "team_b_players": [
                    {
                        "playerId": 22,
                        "name": "Beta WR",
                        "fromTeamId": 1,
                        "toTeamId": 2,
                        "post_trade_points": 50.0,
                        "weekly_points": {"6": 9.0},
                    },
                ],
                "net_difference": 32.25,
                "winner_team_id": 1,
                "winner_team_name": "North Stars",
                "grade_status": "graded",
                "ungraded_reason": None,
                "trade_item_source": "related_transaction",
                "trade_item_source_transaction_id": "100",
                "trade_item_source_type": "TRADE_PROPOSAL",
                "trade_item_source_status": "EXECUTED",
            },
        ),
    )

    # When: trade grade output is normalized into browsable event rows.
    rows = _load_trade_events_module().trade_event_rows(reader)

    # Then: the row carries stable keys, filter fields, objective score fields, and sides.
    assert len(rows) == 1
    row = rows[0]
    assert row["tradeId"] == "canonical:2024:week5:teams1-2"
    assert row["sourceTradeId"] == "101"
    assert row["season"] == 2024
    assert row["week"] == 5
    assert row["date"] == "2024-10-08T13:00:00+00:00"
    assert row["scoreEligible"] is True
    assert row["postTradePoints"] == {"teamA": 82.25, "teamB": 50.0}
    assert row["netPoints"] == 32.25
    assert row["objectiveWinner"] == {
        "side": "teamA",
        "teamId": 1,
        "teamName": "North Stars",
        "managerKey": "team:1",
    }
    assert row["managerKeys"] == ["team:1", "team:2"]
    assert row["sourceTransactionIds"] == ["101", "100"]
    assert row["sortKeys"] == {"bestTrade": 32.25, "worstTrade": -32.25}

    sides = row["sides"]
    assert isinstance(sides, list)
    assert sides[0] == {
        "side": "teamA",
        "teamId": 1,
        "teamName": "North Stars",
        "managerKey": "team:1",
        "receivedAssets": [
            {
                "playerId": 11,
                "name": "Alpha RB",
                "fromTeamId": 2,
                "toTeamId": 1,
                "postTradePoints": 82.25,
                "weeklyPoints": {"6": 12.25, "7": 10.0},
            },
        ],
        "postTradePoints": 82.25,
        "grade": "A",
        "netPoints": 32.25,
        "isObjectiveWinner": True,
    }


def test_trade_event_rows_keep_ungraded_trade_visible_with_caveat() -> None:
    # Given: an ungraded trade accept row where player points could not be resolved.
    reader = _RowsReader(
        rows=(
            {
                "trade_id": "200",
                "related_transaction_id": None,
                "canonical_trade_key": None,
                "season": 2025,
                "week": 2,
                "score_start_week": 3,
                "score_end_week": 17,
                "trade_date_utc": None,
                "team_a_id": None,
                "team_a_name": None,
                "team_a_points": None,
                "team_a_grade": None,
                "team_a_players": [],
                "team_b_id": None,
                "team_b_name": None,
                "team_b_points": None,
                "team_b_grade": None,
                "team_b_players": [],
                "net_difference": None,
                "winner_team_id": None,
                "winner_team_name": None,
                "grade_status": "ungraded",
                "ungraded_reason": "expected 2 receiving teams, found 1 from 1 TRADE items",
                "trade_item_source": "accept_transaction",
                "trade_item_source_transaction_id": "200",
                "trade_item_source_type": "TRADE_ACCEPT",
                "trade_item_source_status": "EXECUTED",
            },
        ),
    )

    # When: ungraded grade rows are normalized.
    rows = _load_trade_events_module().trade_event_rows(reader)

    # Then: visibility is independent from grade/scoring eligibility.
    assert len(rows) == 1
    row = rows[0]
    assert row["tradeId"] == "trade:2025:200"
    assert row["sourceTradeId"] == "200"
    assert row["season"] == 2025
    assert row["week"] == 2
    assert row["scoreEligible"] is False
    assert row["ungradedReason"] == "expected 2 receiving teams, found 1 from 1 TRADE items"
    ungraded_caveat = (
        "Trade is visible but excluded from scoring: "
        "expected 2 receiving teams, found 1 from 1 TRADE items"
    )
    assert row["caveats"] == [ungraded_caveat]
    assert row["postTradePoints"] == {"teamA": None, "teamB": None}
    assert row["netPoints"] is None
    assert row["objectiveWinner"] is None
    assert row["sortKeys"] == {"bestTrade": None, "worstTrade": None}


def test_filter_trade_events_supports_season_manager_mine_and_best_trade_views() -> None:
    # Given: normalized rows with enough data for dashboard filtering.
    module = _load_trade_events_module()
    rows: tuple[JsonObject, ...] = (
        {
            "tradeId": "low",
            "season": 2024,
            "week": 2,
            "managerKeys": ["team:1"],
            "sortKeys": {"bestTrade": 10.0, "worstTrade": -10.0},
        },
        {
            "tradeId": "high",
            "season": 2024,
            "week": 3,
            "managerKeys": ["team:2"],
            "sortKeys": {"bestTrade": 40.0, "worstTrade": -40.0},
        },
        {
            "tradeId": "unscored",
            "season": 2025,
            "week": 1,
            "managerKeys": ["team:1"],
            "sortKeys": {"bestTrade": None, "worstTrade": None},
        },
    )

    # When: dashboard-style filters are applied from row data alone.
    season_rows = module.filter_trade_events(rows, season=2024)
    mine_rows = module.filter_trade_events(rows, manager_key="team:1", mine_only=True)
    best_rows = module.filter_trade_events(rows, season=2024, sort="best")

    # Then: season, my-trades, and best-trades views need no source-row lookup.
    assert [row["tradeId"] for row in season_rows] == ["low", "high"]
    assert [row["tradeId"] for row in mine_rows] == ["low", "unscored"]
    assert [row["tradeId"] for row in best_rows] == ["high", "low"]
