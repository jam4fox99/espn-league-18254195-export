from __future__ import annotations

from pathlib import Path

from mygm_worker.analytics.draft import DraftPick, SeasonDraft, season_drafts
from mygm_worker.analytics.identity import load_team_seasons
from mygm_worker.analytics.reader import FixtureReader
from mygm_worker.analytics.signature_player import build_signature_players, headshot_url

FIXTURE_ROOT = Path(__file__).parents[4] / "espn_exports" / "league_18254195"


def _pick(
    *,
    manager_key: str,
    player_id: int,
    player_name: str,
    season: int,
    season_points: float,
) -> DraftPick:
    return DraftPick(
        season=season,
        overall_pick=1,
        round_id=1,
        round_pick=1,
        player_id=player_id,
        player_name=player_name,
        team_id=1,
        manager_key=manager_key,
        display_name=manager_key,
        keeper=False,
        season_points=season_points,
        points_rank=1,
        steal_value=0,
    )


def _draft(season: int, picks: tuple[DraftPick, ...]) -> SeasonDraft:
    return SeasonDraft(
        season=season,
        is_partial=False,
        pick_count=len(picks),
        picks=picks,
        best_steal=None,
        biggest_bust=None,
    )


# --- Pure unit tests --------------------------------------------------------


def test_signature_player_is_max_single_season_drafted_points() -> None:
    drafts = (
        _draft(
            2021,
            (
                _pick(
                    manager_key="espn-owner:a",
                    player_id=10,
                    player_name="Low",
                    season=2021,
                    season_points=120.0,
                ),
            ),
        ),
        _draft(
            2022,
            (
                _pick(
                    manager_key="espn-owner:a",
                    player_id=11,
                    player_name="High",
                    season=2022,
                    season_points=440.8,
                ),
            ),
        ),
    )

    signatures = build_signature_players(drafts)

    assert signatures["espn-owner:a"] == {
        "name": "High",
        "playerId": 11,
        "season": 2022,
        "points": 440.8,
        "headshot": "https://a.espncdn.com/i/headshots/nfl/players/full/11.png",
    }


def test_signature_player_skips_managers_without_scored_picks() -> None:
    drafts = (
        _draft(
            2021,
            (
                _pick(
                    manager_key="espn-owner:scoreless",
                    player_id=5,
                    player_name="Never Played",
                    season=2021,
                    season_points=0.0,
                ),
            ),
        ),
    )

    assert build_signature_players(drafts) == {}


def test_headshot_url_uses_player_id() -> None:
    assert headshot_url(3918298) == (
        "https://a.espncdn.com/i/headshots/nfl/players/full/3918298.png"
    )


# --- Fixture-backed invariants ----------------------------------------------


def test_signature_players_match_each_managers_best_drafted_season() -> None:
    reader = FixtureReader(FIXTURE_ROOT)
    managers, team_seasons = load_team_seasons(reader)
    drafts = season_drafts(reader, managers, team_seasons)

    signatures = build_signature_players(drafts)
    assert signatures  # a real league always has at least one signature player.

    best_points: dict[str, float] = {}
    for draft in drafts:
        for pick in draft.picks:
            if pick.season_points <= 0.0:
                continue
            best_points[pick.manager_key] = max(
                best_points.get(pick.manager_key, 0.0),
                pick.season_points,
            )

    for manager_key, signature in signatures.items():
        player_id = signature["playerId"]
        assert isinstance(player_id, int)
        assert signature["headshot"] == headshot_url(player_id)
        points = signature["points"]
        assert isinstance(points, float)
        assert points > 0.0
        assert points == best_points[manager_key]
