from __future__ import annotations

from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from mygm_worker.analytics.draft import DraftPick, SeasonDraft
    from mygm_worker.analytics.models import JsonObject

HEADSHOT_TEMPLATE: Final = "https://a.espncdn.com/i/headshots/nfl/players/full/{player_id}.png"


def headshot_url(player_id: int) -> str:
    return HEADSHOT_TEMPLATE.format(player_id=player_id)


def build_signature_players(drafts: tuple[SeasonDraft, ...]) -> dict[str, JsonObject]:
    """Pick each GM's signature player: the highest single-season point total they drafted.

    Keyed on managerKey. A GM who never drafted a player that scored points is absent, so
    callers should treat a missing key as a ``null`` signature.
    """
    best: dict[str, DraftPick] = {}
    for draft in drafts:
        for pick in draft.picks:
            if pick.season_points <= 0.0:
                continue
            current = best.get(pick.manager_key)
            if current is None or pick.season_points > current.season_points:
                best[pick.manager_key] = pick
    return {manager_key: _signature_json(pick) for manager_key, pick in best.items()}


def _signature_json(pick: DraftPick) -> JsonObject:
    return {
        "name": pick.player_name,
        "playerId": pick.player_id,
        "season": pick.season,
        "points": pick.season_points,
        "headshot": headshot_url(pick.player_id),
    }
