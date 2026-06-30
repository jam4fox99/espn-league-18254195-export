"""NFL injury-report history, vendored as static per-season files.

The files under ``mygm_worker/data/nfl/injuries_<season>.json`` are aggregated
weekly NFL injury reports (how many weeks each player was Out / Doubtful /
Questionable), fetched once from nflverse (see ``scripts/fetch_nfl_injuries.py``)
and committed for reproducible offline builds. The worker joins them to league
players by normalized name to grade the "Injury Risk" player badge. NFL-wide, so
league-agnostic.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from mygm_worker.analytics.adp import normalize_name
from mygm_worker.analytics.json_tools import as_object, int_value, read_json

_DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "nfl"

# Weeks listed Out are near-certain absences; Doubtful usually misses; Questionable
# often plays. Weight them by how reliably each signals a real availability problem.
_OUT_WEIGHT = 1.0
_DOUBTFUL_WEIGHT = 0.7
_QUESTIONABLE_WEIGHT = 0.25


@dataclass(frozen=True, slots=True)
class InjuryIndex:
    """Normalized name -> {season -> weighted injury-report burden (weeks listed)}."""

    burden_by_name: dict[str, dict[int, float]]
    # Seasons that actually have vendored injury data, so the badge normalizes only
    # over seasons it could observe (the current, not-yet-played season has a
    # schedule but no injury reports).
    covered_seasons: frozenset[int]

    def burden(self, name: str | None, seasons: set[int]) -> float:
        """Total injury burden over the player's own (and injury-covered) seasons.

        Scoping the numerator to the seasons a player was actually active keeps a
        late arrival's rate from being inflated by injury weeks he accrued elsewhere
        before joining this league.
        """
        per_season = self.burden_by_name.get(normalize_name(name), {})
        return sum(
            value for season, value in per_season.items() if season in seasons
        )

    def covered_count(self, seasons: set[int]) -> int:
        return sum(1 for season in seasons if season in self.covered_seasons)


def load_injury_index(data_dir: Path | None = None) -> InjuryIndex:
    """Load every vendored ``injuries_<season>.json`` into a per-season burden per name."""
    directory = data_dir or _DATA_DIR
    burden: dict[str, dict[int, float]] = {}
    covered: set[int] = set()
    if not directory.is_dir():
        return InjuryIndex(burden_by_name={}, covered_seasons=frozenset())
    for path in sorted(directory.glob("injuries_*.json")):
        # Guard the whole parse so one malformed vendored file or player entry is
        # skipped, not fatal to the snapshot build.
        # Build the season's burden in a local dict and commit it atomically only
        # after the whole file parses, so a malformed entry mid-file can never leave
        # `burden` populated for a season that `covered_seasons` omits (which would
        # let the numerator count a season the denominator doesn't).
        try:
            payload = as_object(read_json(path), str(path))
            season = int_value(payload.get("season"), 0)
            if season <= 0:
                continue
            season_burden: dict[str, float] = {}
            for name, raw_counts in as_object(payload.get("players"), "players").items():
                counts = as_object(raw_counts, name)
                weighted = (
                    int_value(counts.get("out")) * _OUT_WEIGHT
                    + int_value(counts.get("doubtful")) * _DOUBTFUL_WEIGHT
                    + int_value(counts.get("questionable")) * _QUESTIONABLE_WEIGHT
                )
                if weighted:
                    season_burden[name] = weighted
        except (OSError, ValueError):
            continue
        for name, weighted in season_burden.items():
            burden.setdefault(name, {})[season] = weighted
        covered.add(season)
    return InjuryIndex(burden_by_name=burden, covered_seasons=frozenset(covered))
