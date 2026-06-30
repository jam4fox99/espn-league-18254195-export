from __future__ import annotations

from pathlib import Path

from mygm_worker.analytics.player_directory import (
    POSITIONS,
    PRO_TEAM_ABBREV,
    PlayerDirectoryEntry,
    build_player_directory,
    enrich_player_row,
    player_directory_json,
)
from mygm_worker.analytics.reader import FixtureReader

FIXTURE_ROOT = Path(__file__).parents[4] / "espn_exports" / "league_18254195"


def _entry(
    player_id: int,
    *,
    position: str = "WR",
    abbrev: str = "SEA",
    is_dst: bool = False,
) -> PlayerDirectoryEntry:
    return PlayerDirectoryEntry(
        player_id=player_id,
        name=f"Player {player_id}",
        position=position,
        pro_team_abbrev=abbrev,
        latest_season=2025,
        is_dst=is_dst,
    )


# --- Pure unit tests --------------------------------------------------------


def test_pro_team_map_uses_espn_ids() -> None:
    # A spot-check of the canonical ESPN proTeamId -> abbrev mapping.
    assert PRO_TEAM_ABBREV[1] == "ATL"
    assert PRO_TEAM_ABBREV[26] == "SEA"
    assert PRO_TEAM_ABBREV[34] == "HOU"
    assert PRO_TEAM_ABBREV[0] == ""  # 0 means free agent / none.


def test_position_map_covers_core_slots() -> None:
    assert POSITIONS == {1: "QB", 2: "RB", 3: "WR", 4: "TE", 5: "K", 16: "D/ST"}


def test_enrich_player_row_adds_team_position_and_dst_flag() -> None:
    directory = {4430878: _entry(4430878, position="WR", abbrev="SEA")}
    row = enrich_player_row({"playerId": 4430878, "name": "JSN"}, directory)
    assert row["proTeamAbbrev"] == "SEA"
    assert row["isDST"] is False
    assert row["position"] == "WR"


def test_enrich_player_row_preserves_existing_position() -> None:
    directory = {1: _entry(1, position="WR")}
    row = enrich_player_row({"playerId": 1, "position": "RB"}, directory)
    assert row["position"] == "RB"  # existing value is not overwritten.


def test_enrich_player_row_derives_dst_flag_for_negative_id_when_absent() -> None:
    row = enrich_player_row({"playerId": -16034}, {})
    assert row["isDST"] is True
    assert row["proTeamAbbrev"] == ""
    assert row["position"] == ""


def test_player_directory_json_keys_on_player_id_string() -> None:
    directory = {-16034: _entry(-16034, position="D/ST", abbrev="HOU", is_dst=True)}
    payload = player_directory_json(directory)
    assert set(payload) == {"-16034"}
    entry = payload["-16034"]
    assert entry == {
        "playerId": -16034,
        "name": "Player -16034",
        "position": "D/ST",
        "proTeamAbbrev": "HOU",
        "latestSeason": 2025,
        "isDST": True,
    }


# --- Fixture-backed structural invariants -----------------------------------


def test_build_player_directory_is_populated_and_well_formed() -> None:
    reader = FixtureReader(FIXTURE_ROOT)
    directory = build_player_directory(reader)

    assert directory  # the dimension table is never empty for a real league.
    for player_id, entry in directory.items():
        assert isinstance(player_id, int)
        assert entry.player_id == player_id
        assert entry.name
        assert entry.is_dst == (player_id < 0)
        assert isinstance(entry.latest_season, int)


def test_build_player_directory_resolves_known_skill_player_and_defense() -> None:
    reader = FixtureReader(FIXTURE_ROOT)
    directory = build_player_directory(reader)

    # Bijan Robinson (ESPN id 4430807) is an Atlanta running back.
    bijan = directory[4430807]
    assert bijan.position == "RB"
    assert bijan.pro_team_abbrev == "ATL"
    assert bijan.is_dst is False

    # Negative ids are team defenses; the abbrev is derivable from the encoded proTeamId.
    texans_dst = directory[-16034]
    assert texans_dst.is_dst is True
    assert texans_dst.position == "D/ST"
    assert texans_dst.pro_team_abbrev == "HOU"
