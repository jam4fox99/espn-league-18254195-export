"""NFL defense-vs-position (DvP) ranks, vendored as static per-season files.

The files under ``mygm_worker/data/nfl/dvp_<season>.json`` rank every NFL defense,
within each fantasy position, by how many PPR points it allowed across the whole
league that season (see ``scripts/fetch_nfl_dvp.py``). Ranks are 0..1, higher =
weaker defense / easier matchup. The worker joins them to a player's weekly
opponent (via the vendored schedule) to grade the "Matchup Based" badge. Using
league-wide DvP avoids the self-contamination of deriving it from one fantasy
league's own rosters. NFL-wide, so league-agnostic.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from mygm_worker.analytics.json_tools import (
    as_object,
    float_value,
    int_value,
    read_json,
)

_DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "nfl"


@dataclass(frozen=True, slots=True)
class DvpIndex:
    """(season -> position -> defense abbrev -> rank in [0,1], higher = weaker D)."""

    by_season: dict[int, dict[str, dict[str, float]]]

    def rank(self, season: int, position: str, defense: str) -> float | None:
        return self.by_season.get(season, {}).get(position, {}).get(defense)

    def has_season(self, season: int) -> bool:
        return season in self.by_season

    @property
    def seasons(self) -> tuple[int, ...]:
        return tuple(sorted(self.by_season))


def load_dvp_index(data_dir: Path | None = None) -> DvpIndex:
    """Load every vendored ``dvp_<season>.json`` into a rank index."""
    directory = data_dir or _DATA_DIR
    by_season: dict[int, dict[str, dict[str, float]]] = {}
    if not directory.is_dir():
        return DvpIndex(by_season={})
    for path in sorted(directory.glob("dvp_*.json")):
        # Guard the whole parse so one malformed vendored file is skipped, not fatal.
        try:
            payload = as_object(read_json(path), str(path))
            season = int_value(payload.get("season"), 0)
            if season <= 0:
                continue
            positions: dict[str, dict[str, float]] = {}
            for position, teams in as_object(payload.get("byPosition"), "byPosition").items():
                ranks = {
                    team: float_value(rank)
                    for team, rank in as_object(teams, position).items()
                }
                if ranks:
                    positions[position] = ranks
        except (OSError, ValueError):
            continue
        if positions:
            by_season[season] = positions
    return DvpIndex(by_season=by_season)
