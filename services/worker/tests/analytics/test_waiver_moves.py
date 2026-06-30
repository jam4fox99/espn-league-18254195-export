from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import TYPE_CHECKING

from mygm_worker.analytics.identity import load_team_seasons
from mygm_worker.analytics.json_tools import (
    as_array,
    as_object,
    float_value,
    int_value,
    string_value,
)
from mygm_worker.analytics.reader import FixtureReader
from mygm_worker.analytics.waiver_moves import (
    manager_waiver_scores,
    waiver_move_rows,
    waiver_superlatives,
)

if TYPE_CHECKING:
    from mygm_worker.analytics.models import JsonValue

FIXTURE_ROOT = Path(__file__).parents[4] / "espn_exports" / "league_18254195"


def test_acquisition_rows_include_add_drop_impact_from_fixture() -> None:
    # Given: the ESPN fixture contains executed waiver and free-agent acquisitions.
    rows = waiver_move_rows(FixtureReader(FIXTURE_ROOT))

    # When: eligible add/drop acquisition rows are selected.
    eligible_rows = _eligible_rows(rows)
    add_drop_rows = tuple(row for row in eligible_rows if row["droppedPlayers"])
    scores = manager_waiver_scores(rows)

    # Then: every scored row exposes actual add/drop impact without fabricated values.
    assert rows
    assert eligible_rows
    assert add_drop_rows
    assert scores
    first = add_drop_rows[0]
    assert first["transactionType"] in {"WAIVER", "FREEAGENT"}
    assert first["status"] == "EXECUTED"
    assert int_value(first["season"]) >= 2020
    assert int_value(first["week"]) >= 1
    assert int_value(first["teamId"]) >= 1
    assert first["managerKey"]
    assert first["teamName"]
    assert first["sourceTransactionId"]
    assert first["sourceFile"]
    assert int_value(first["sourceIndex"]) >= 0
    assert first["faabCaveat"] == "FAAB context unavailable: bidAmount is always 0"
    assert first["exclusionReason"] == ""
    assert first["addedPlayers"]
    assert first["addedRestOfSeasonPoints"] == _player_total(first["addedPlayers"])
    assert first["droppedRestOfSeasonPoints"] == _player_total(first["droppedPlayers"])
    assert first["dropRegret"] == first["droppedRestOfSeasonPoints"]
    assert float_value(first["netPoints"]) == (
        float_value(first["addedRestOfSeasonPoints"])
        - float_value(first["droppedRestOfSeasonPoints"])
    )
    sort_keys = as_object(first["sortKeys"], "sortKeys")
    assert sort_keys["bestPickup"] == first["addedRestOfSeasonPoints"]
    assert sort_keys["worstDrop"] == first["droppedRestOfSeasonPoints"]


def test_transaction_without_add_is_visible_and_excluded(tmp_path: Path) -> None:
    # Given: a fixture has an executed acquisition transaction with only DROP items.
    fixture_root = _write_minimal_fixture(tmp_path)

    # When: waiver move rows and manager scores are derived.
    rows = waiver_move_rows(FixtureReader(fixture_root))
    scores = manager_waiver_scores(rows)

    # Then: the transaction remains visible but cannot affect manager scoring.
    assert len(rows) == 1
    row = rows[0]
    assert row["transactionType"] == "WAIVER"
    assert row["status"] == "EXECUTED"
    assert row["addedPlayers"] == []
    assert row["droppedPlayers"]
    assert row["scoreEligible"] is False
    assert row["exclusionReason"] == "executed_without_add"
    assert row["addedRestOfSeasonPoints"] == 0.0
    assert row["droppedRestOfSeasonPoints"] == 0.0
    assert row["netPoints"] == 0.0
    assert scores == {}


def test_waiver_superlatives_resolve_four_cards_per_season() -> None:
    # Given: the eligible waiver/FA moves and the manager display names.
    reader = FixtureReader(FIXTURE_ROOT)
    managers, _ = load_team_seasons(reader)
    names = {key: manager.display_name for key, manager in managers.items()}
    rows = waiver_move_rows(reader)

    # When: per-season superlatives are derived.
    superlatives = waiver_superlatives(rows, names=names)

    # Then: 2025 resolves all four award cards, each scoped to that season.
    assert 2025 in superlatives
    season_2025 = as_object(superlatives[2025], "superlatives[2025]")
    assert int_value(season_2025["season"]) == 2025
    for card_key in ("bestPickup", "worstDrop", "bestWireValue", "mostActive"):
        card = as_object(season_2025[card_key], card_key)
        assert string_value(card["managerKey"])
        assert string_value(card["displayName"])
        assert int_value(card["season"]) == 2025
        assert string_value(card["detail"])
    # The pickup/drop cards name an actual player; most-active reports a move count.
    assert string_value(as_object(season_2025["bestPickup"], "bestPickup")["player"])
    assert int_value(as_object(season_2025["mostActive"], "mostActive")["count"]) > 0


def _eligible_rows(rows: Iterable[dict[str, JsonValue]]) -> tuple[dict[str, JsonValue], ...]:
    return tuple(row for row in rows if row["scoreEligible"] is True)


def _player_total(players: JsonValue) -> float:
    total = 0.0
    for player in as_array(players, "players"):
        total += float_value(as_object(player, "player")["restOfSeasonPoints"])
    return round(total, 4)


def _write_minimal_fixture(tmp_path: Path) -> Path:
    root = tmp_path / "fixture"
    season = root / "season_2025"
    transactions = season / "transactions"
    (root / "player_lookup").mkdir(parents=True)
    transactions.mkdir(parents=True)
    _ = (root / "export_manifest.json").write_text("{}", encoding="utf-8")
    _ = (root / "player_lookup" / "player_weekly_points.json").write_text(
        '{"players":{"1":{"name":"Dropped Player","weekly_points":{"2025":{"2":7}}}}}',
        encoding="utf-8",
    )
    _ = (season / "_season_summary.json").write_text(
        '{"transactions_total":1,"schedule_items":0,"final_scoring_period":17}',
        encoding="utf-8",
    )
    _ = (season / "core.json").write_text(
        (
            '{"data":{"members":[{"id":"owner-1","displayName":"Manager One"}],'
            '"teams":[{"id":3,"name":"Drop Team","primaryOwner":"owner-1",'
            '"record":{"overall":{"wins":0,"losses":0,"ties":0,'
            '"pointsFor":0,"pointsAgainst":0}}}]}}'
        ),
        encoding="utf-8",
    )
    _ = (transactions / "period_01.json").write_text(
        (
            '{"data":{"transactions":[{"id":"drop-only","type":"WAIVER",'
            '"status":"EXECUTED","bidAmount":0,"teamId":3,"scoringPeriodId":1,'
            '"processDate":1755328258483,"items":[{"type":"DROP","playerId":1,'
            '"fromTeamId":3,"toTeamId":0}]}]}}'
        ),
        encoding="utf-8",
    )
    return root
