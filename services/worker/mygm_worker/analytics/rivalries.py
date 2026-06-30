from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from mygm_worker.analytics.head_to_head import head_to_head_pairs
from mygm_worker.analytics.identity import load_team_seasons

if TYPE_CHECKING:
    from mygm_worker.analytics.head_to_head import HeadToHeadPair
    from mygm_worker.analytics.models import ManagerIdentity, TeamSeason
    from mygm_worker.analytics.reader import FixtureReader

# Minimum meetings before a pairing can be called a nemesis or favorite opponent.
MIN_RIVALRY_GAMES: Final = 3


@dataclass(frozen=True, slots=True)
class RivalryEdge:
    manager_key: str
    opponent_key: str
    display_name: str
    opponent_display_name: str
    wins: int
    losses: int
    ties: int
    games: int
    win_pct: float
    average_points_for: float
    average_points_against: float
    playoff_wins: int
    playoff_losses: int
    current_streak: str


@dataclass(frozen=True, slots=True)
class ManagerRivalry:
    manager_key: str
    display_name: str
    nemesis: RivalryEdge | None
    favorite: RivalryEdge | None
    edges: tuple[RivalryEdge, ...]


@dataclass(frozen=True, slots=True)
class RivalryMatrix:
    managers: tuple[tuple[str, str], ...]
    edges: tuple[RivalryEdge, ...]
    summaries: tuple[ManagerRivalry, ...]


def rivalry_matrix(
    reader: FixtureReader,
    managers: dict[str, ManagerIdentity],
    team_seasons: list[TeamSeason],
    included_seasons: tuple[int, ...],
) -> RivalryMatrix:
    names = {key: manager.display_name for key, manager in managers.items()}
    pairs = head_to_head_pairs(reader, team_seasons, included_seasons)
    edges: list[RivalryEdge] = []
    for pair in pairs:
        if pair.manager_a_key.startswith("unresolved:") or pair.manager_b_key.startswith(
            "unresolved:"
        ):
            continue
        edges.append(_edge(pair, names, forward=True))
        edges.append(_edge(pair, names, forward=False))
    edges.sort(key=lambda edge: (edge.manager_key, edge.opponent_key))
    axis = _axis(edges, names)
    summaries = tuple(
        _summary(manager_key, display_name, edges) for manager_key, display_name in axis
    )
    return RivalryMatrix(managers=axis, edges=tuple(edges), summaries=summaries)


def _edge(pair: HeadToHeadPair, names: dict[str, str], *, forward: bool) -> RivalryEdge:
    if forward:
        manager_key, opponent_key = pair.manager_a_key, pair.manager_b_key
        wins, losses = pair.wins_a, pair.wins_b
        points_for, points_against = pair.average_score_a, pair.average_score_b
        playoff_wins, playoff_losses = pair.playoff_wins_a, pair.playoff_wins_b
    else:
        manager_key, opponent_key = pair.manager_b_key, pair.manager_a_key
        wins, losses = pair.wins_b, pair.wins_a
        points_for, points_against = pair.average_score_b, pair.average_score_a
        playoff_wins, playoff_losses = pair.playoff_wins_b, pair.playoff_wins_a
    games = wins + losses + pair.ties
    win_pct = round((wins + (pair.ties / 2)) / games * 100, 4) if games else 0.0
    return RivalryEdge(
        manager_key=manager_key,
        opponent_key=opponent_key,
        display_name=names.get(manager_key, manager_key),
        opponent_display_name=names.get(opponent_key, opponent_key),
        wins=wins,
        losses=losses,
        ties=pair.ties,
        games=games,
        win_pct=win_pct,
        average_points_for=points_for,
        average_points_against=points_against,
        playoff_wins=playoff_wins,
        playoff_losses=playoff_losses,
        current_streak=_streak_for(pair, forward=forward),
    )


def _streak_for(pair: HeadToHeadPair, *, forward: bool) -> str:
    # pair.current_streak is "A:n" / "B:n" / "TIE:n" from manager_a's frame.
    side, _, length = pair.current_streak.partition(":")
    if side == "TIE":
        return pair.current_streak
    winning_side = "A" if forward else "B"
    outcome = "W" if side == winning_side else "L"
    return f"{outcome}:{length}"


def _axis(edges: list[RivalryEdge], names: dict[str, str]) -> tuple[tuple[str, str], ...]:
    keys = sorted({edge.manager_key for edge in edges})
    return tuple((key, names.get(key, key)) for key in keys)


def _summary(
    manager_key: str,
    display_name: str,
    edges: list[RivalryEdge],
) -> ManagerRivalry:
    own = tuple(edge for edge in edges if edge.manager_key == manager_key)
    qualified = [edge for edge in own if edge.games >= MIN_RIVALRY_GAMES]
    nemesis = min(
        qualified,
        key=lambda edge: (edge.win_pct, -edge.games, -edge.losses),
        default=None,
    )
    favorite = max(
        qualified,
        key=lambda edge: (edge.win_pct, edge.games, edge.wins),
        default=None,
    )
    return ManagerRivalry(
        manager_key=manager_key,
        display_name=display_name,
        nemesis=nemesis,
        favorite=favorite,
        edges=own,
    )


def rivalry_matrix_for_fixture(
    reader: FixtureReader,
    included_seasons: tuple[int, ...],
) -> RivalryMatrix:
    managers, team_seasons = load_team_seasons(reader)
    return rivalry_matrix(reader, managers, team_seasons, included_seasons)
