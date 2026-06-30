#!/usr/bin/env python3
"""Vendor NFL defense-vs-position (DvP) strength as static per-season files.

Source: nflverse-data weekly player stats `stats_player_week_<season>.csv`
(https://github.com/nflverse/nflverse-data). For each regular-season game we read
the PPR fantasy points each skill player scored against his opponent, aggregate by
(position, defense), and rank every defense within a position by how many points
it ALLOWED. We persist only those ranks (0..1, higher = weaker defense / easier
matchup).

This is the real, league-wide defense-vs-position signal the "Matchup Based"
player badge needs. Deriving DvP from a single 12-team fantasy league's own rosters
is both tiny-sample and self-referential (a player's own big games make his
opponent look weak), so the worker uses these vendored ranks instead. NFL-wide, so
league-agnostic.

Run once (needs network):
    python3 scripts/fetch_nfl_dvp.py
"""

from __future__ import annotations

import csv
import io
import json
import urllib.request
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "services" / "worker" / "mygm_worker" / "data" / "nfl"
SOURCE = "nflverse-data stats_player_week (PPR points allowed)"
URL = (
    "https://github.com/nflverse/nflverse-data/releases/download/"
    "stats_player/stats_player_week_{season}.csv"
)
SEASONS = range(2020, 2027)
_POSITIONS = frozenset({"QB", "RB", "WR", "TE"})


def fetch_season(season: int) -> list[dict[str, str]]:
    request = urllib.request.Request(  # noqa: S310 - fixed https host
        URL.format(season=season), headers={"User-Agent": "Mozilla/5.0 (MyGM DvP vendor)"}
    )
    with urllib.request.urlopen(request, timeout=90) as response:  # noqa: S310
        return list(csv.DictReader(io.StringIO(response.read().decode("utf-8"))))


def _percentiles(values: dict[str, float]) -> dict[str, float]:
    items = list(values.values())
    n = len(items)
    out: dict[str, float] = {}
    for key, value in values.items():
        less = sum(1 for other in items if other < value)
        equal = sum(1 for other in items if other == value)
        out[key] = round((less + 0.5 * equal) / n, 4)
    return out


def season_dvp(rows: list[dict[str, str]]) -> dict[str, dict[str, float]]:
    # position -> defense -> list of PPR points allowed (one entry per player-game).
    allowed: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        if row.get("season_type", "REG") != "REG":
            continue
        position = row.get("position", "")
        defense = row.get("opponent_team", "")
        if position not in _POSITIONS or not defense or defense in ("NA", ""):
            continue
        try:
            points = float(row.get("fantasy_points_ppr", "") or 0.0)
        except ValueError:
            continue
        allowed[position][defense].append(points)
    ranks: dict[str, dict[str, float]] = {}
    for position, defenses in allowed.items():
        means = {team: sum(pts) / len(pts) for team, pts in defenses.items() if len(pts) >= 4}
        if means:
            ranks[position] = _percentiles(means)
    return ranks


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    index: dict[str, int] = {}
    for season in SEASONS:
        try:
            rows = fetch_season(season)
        except Exception as error:  # noqa: BLE001 - best-effort vendor step
            print(f"{season}: fetch failed ({error}); skipping")
            continue
        ranks = season_dvp(rows)
        if not ranks:
            print(f"{season}: no DvP rows; skipping")
            continue
        out_path = OUT_DIR / f"dvp_{season}.json"
        out_path.write_text(
            json.dumps({"source": SOURCE, "season": season, "byPosition": ranks}, indent=0) + "\n",
            encoding="utf-8",
        )
        index[str(season)] = sum(len(v) for v in ranks.values())
        print(f"{season}: vendored DvP for {list(ranks)} -> {out_path.relative_to(ROOT)}")
    (OUT_DIR / "DVP_INDEX.json").write_text(
        json.dumps({"source": SOURCE, "seasons": index}, indent=2) + "\n", encoding="utf-8"
    )
    missing = [s for s in SEASONS if str(s) not in index]
    print(f"Vendored {len(index)}/{len(list(SEASONS))} configured seasons.")
    if missing:
        print(f"WARNING: no DvP for seasons {missing}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
