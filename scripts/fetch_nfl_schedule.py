#!/usr/bin/env python3
"""Vendor NFL game schedules as static, league-agnostic per-season files.

Source: nflverse/nfldata `games.csv` (https://github.com/nflverse/nfldata),
a community dataset of factual NFL game results. We persist only the matchup
facts we need — season, week, and the two teams — keyed by season. Who-played-whom
is factual data (not copyrightable expression); we redistribute a minimal subset
and record the source.

The worker uses these to find each player's weekly opponent (player NFL team ->
opponent that week) so it can derive defense-vs-position strength and the
"Matchup Based" player badge. The schedule is NFL-wide, so the vendored data is
league-agnostic and refreshed manually each new season.

Run once (needs network):
    python3 scripts/fetch_nfl_schedule.py
"""

from __future__ import annotations

import csv
import io
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "services" / "worker" / "mygm_worker" / "data" / "nfl"
SOURCE = "nflverse/nfldata games.csv"
URL = "https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv"
SEASONS = range(2020, 2027)


def fetch_rows() -> list[dict[str, str]]:
    request = urllib.request.Request(  # noqa: S310 - fixed https host
        URL, headers={"User-Agent": "Mozilla/5.0 (MyGM schedule vendor)"}
    )
    with urllib.request.urlopen(request, timeout=60) as response:  # noqa: S310
        text = response.read().decode("utf-8")
    return list(csv.DictReader(io.StringIO(text)))


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = fetch_rows()
    index: dict[str, int] = {}
    for season in SEASONS:
        # team -> {week -> opponent}, both directions of each game.
        by_team: dict[str, dict[str, str]] = {}
        for row in rows:
            try:
                row_season = int(row.get("season", ""))
                week = int(row.get("week", ""))
            except ValueError:
                continue
            if row_season != season:
                continue
            home, away = row.get("home_team", ""), row.get("away_team", "")
            if not home or not away:
                continue
            by_team.setdefault(home, {})[str(week)] = away
            by_team.setdefault(away, {})[str(week)] = home
        if not by_team:
            print(f"{season}: no games; skipping")
            continue
        out_path = OUT_DIR / f"schedule_{season}.json"
        out_path.write_text(
            json.dumps({"source": SOURCE, "season": season, "byTeam": by_team}, indent=0) + "\n",
            encoding="utf-8",
        )
        index[str(season)] = len(by_team)
        print(f"{season}: vendored {len(by_team)} teams -> {out_path.relative_to(ROOT)}")
    (OUT_DIR / "INDEX.json").write_text(
        json.dumps({"source": SOURCE, "seasons": index}, indent=2) + "\n", encoding="utf-8"
    )
    missing = [s for s in SEASONS if str(s) not in index]
    print(f"Vendored {len(index)}/{len(list(SEASONS))} configured seasons.")
    if missing:
        print(f"WARNING: no schedule for seasons {missing}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
