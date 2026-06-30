"""Historical fantasy ADP, vendored as static per-season files.

The files under ``mygm_worker/data/adp/adp_<season>.json`` are real PPR 12-team
ADP fetched once from Fantasy Football Calculator (see ``scripts/fetch_adp.py``)
and committed so builds are reproducible with no runtime network dependency. They
are league-agnostic: keyed by player name + season, joined to a league's drafted
players by normalized name at analysis time.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from mygm_worker.analytics.json_tools import (
    as_object,
    float_value,
    int_value,
    objects,
    read_json,
    string_value,
)

_DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "adp"
_SUFFIXES = frozenset({"jr", "sr", "ii", "iii", "iv", "v"})


def normalize_name(name: str | None) -> str:
    """Lowercase, drop punctuation + generational suffixes for a robust join."""
    tokens = re.sub(r"[^a-z0-9 ]", "", (name or "").lower()).split()
    kept = [token for token in tokens if token not in _SUFFIXES]
    return "".join(kept)


@dataclass(frozen=True, slots=True)
class AdpIndex:
    """Normalized-name → ADP, per season."""

    by_season: dict[int, dict[str, float]]

    def has_season(self, season: int) -> bool:
        return season in self.by_season

    def adp(self, season: int, player_name: str | None) -> float | None:
        table = self.by_season.get(season)
        if not table:
            return None
        return table.get(normalize_name(player_name))

    @property
    def seasons(self) -> tuple[int, ...]:
        return tuple(sorted(self.by_season))


def load_adp_index(data_dir: Path | None = None) -> AdpIndex:
    """Load every vendored ``adp_<season>.json`` into a name→ADP index."""
    directory = data_dir or _DATA_DIR
    by_season: dict[int, dict[str, float]] = {}
    if not directory.is_dir():
        return AdpIndex(by_season={})
    for path in sorted(directory.glob("adp_*.json")):
        table: dict[str, float] = {}
        season = 0
        # Guard the whole parse so one malformed vendored file is skipped, not fatal
        # to the snapshot build (read_json / objects raise ValueError on bad shapes).
        try:
            payload = as_object(read_json(path), str(path))
            season = int_value(payload.get("season"), 0)
            if season > 0:
                for player in objects(payload.get("players"), "players"):
                    name = normalize_name(string_value(player.get("name")))
                    adp = float_value(player.get("adp"), 0.0)
                    # Lowest ADP wins a normalized-name collision — order-independent,
                    # so it doesn't rely on the vendored file being pre-sorted.
                    if name and adp > 0 and (name not in table or adp < table[name]):
                        table[name] = adp
        except (OSError, ValueError):
            continue
        if season > 0 and table:
            by_season[season] = table
    return AdpIndex(by_season=by_season)
