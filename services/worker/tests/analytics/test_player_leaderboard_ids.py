from __future__ import annotations

from pathlib import Path

from mygm_worker.analytics.identity import load_team_seasons
from mygm_worker.analytics.player_leaderboards import (
    _resolve_player_id,  # pyright: ignore[reportPrivateUsage]
    player_leaderboards,
)
from mygm_worker.analytics.reader import FixtureReader

FIXTURE_ROOT = Path(__file__).parents[4] / "espn_exports" / "league_18254195"


def test_resolve_player_id_keeps_present_id_and_backfills_missing() -> None:
    backfill = {"Star Player": 4321}
    # A present id (including a negative D/ST id) is kept verbatim.
    assert _resolve_player_id(99, "Star Player", backfill) == 99
    assert _resolve_player_id(-16034, "Texans D/ST", backfill) == -16034
    # A missing id (0) is recovered from the name lookup.
    assert _resolve_player_id(0, "Star Player", backfill) == 4321
    assert _resolve_player_id(0, "Unknown", backfill) == 0


def test_player_leaderboards_rows_carry_player_ids() -> None:
    reader = FixtureReader(FIXTURE_ROOT)
    managers, team_seasons = load_team_seasons(reader)
    boards = player_leaderboards(reader, managers, team_seasons)

    assert boards.top_weeks
    assert boards.top_seasons
    for row in boards.top_weeks:
        assert isinstance(row.player_id, int)
        assert row.player_id != 0  # box-score ids are always present.
    for row in boards.top_seasons:
        assert isinstance(row.player_id, int)
        assert row.player_id != 0
