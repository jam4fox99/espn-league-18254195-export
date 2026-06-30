#!/usr/bin/env python3
"""Vendor NFL injury-report history as static, league-agnostic per-season files.

Source: nflverse-data `injuries_<season>.csv`
(https://github.com/nflverse/nflverse-data), the official weekly NFL injury
reports. For each season we keep only an aggregate per player — how many weeks
they were listed Out / Doubtful / Questionable — which is the factual signal the
worker needs for the "Injury Risk" player badge. Names are the join key (the ESPN
export has no gsis ids), matched by the same normalization the ADP join uses.

The data is NFL-wide, so the vendored files are league-agnostic and refreshed
manually each new season.

Run once (needs network):
    python3 scripts/fetch_nfl_injuries.py
"""

from __future__ import annotations

import csv
import io
import json
import re
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "services" / "worker" / "mygm_worker" / "data" / "nfl"
SOURCE = "nflverse-data injuries"
URL = "https://github.com/nflverse/nflverse-data/releases/download/injuries/injuries_{season}.csv"
SEASONS = range(2020, 2027)
_SUFFIXES = frozenset({"jr", "sr", "ii", "iii", "iv", "v"})
# Keep only fantasy skill positions. The worker joins injuries to skill players by
# name; dropping non-skill rows here removes cross-position name collisions (e.g.
# QB Josh Allen vs LB Josh Allen) before they can merge into one burden.
_SKILL_POSITIONS = frozenset({"QB", "RB", "WR", "TE", "FB"})


def normalize_name(name: str) -> str:
    tokens = re.sub(r"[^a-z0-9 ]", "", name.lower()).split()
    return "".join(token for token in tokens if token not in _SUFFIXES)


def fetch_season(season: int) -> list[dict[str, str]]:
    request = urllib.request.Request(  # noqa: S310 - fixed https host
        URL.format(season=season), headers={"User-Agent": "Mozilla/5.0 (MyGM injury vendor)"}
    )
    with urllib.request.urlopen(request, timeout=60) as response:  # noqa: S310
        return list(csv.DictReader(io.StringIO(response.read().decode("utf-8"))))


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    index: dict[str, int] = {}
    for season in SEASONS:
        try:
            rows = fetch_season(season)
        except Exception as error:  # noqa: BLE001 - best-effort vendor step
            print(f"{season}: fetch failed ({error}); skipping")
            continue
        # normalized name -> per-status week counts (one row == one player-week listing).
        players: dict[str, dict[str, int]] = {}
        for row in rows:
            name = normalize_name(row.get("full_name", ""))
            status = row.get("report_status", "")
            if row.get("position", "") not in _SKILL_POSITIONS:
                continue
            if not name or status not in ("Out", "Doubtful", "Questionable"):
                continue
            bucket = players.setdefault(name, {"out": 0, "doubtful": 0, "questionable": 0})
            bucket[status.lower()] += 1
        if not players:
            print(f"{season}: no injury rows; skipping")
            continue
        out_path = OUT_DIR / f"injuries_{season}.json"
        out_path.write_text(
            json.dumps({"source": SOURCE, "season": season, "players": players}, indent=0) + "\n",
            encoding="utf-8",
        )
        index[str(season)] = len(players)
        print(f"{season}: vendored {len(players)} players -> {out_path.relative_to(ROOT)}")
    (OUT_DIR / "INJURIES_INDEX.json").write_text(
        json.dumps({"source": SOURCE, "seasons": index}, indent=2) + "\n", encoding="utf-8"
    )
    missing = [s for s in SEASONS if str(s) not in index]
    print(f"Vendored {len(index)}/{len(list(SEASONS))} configured seasons.")
    if missing:
        print(f"WARNING: no injuries for seasons {missing}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
