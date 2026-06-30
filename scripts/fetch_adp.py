#!/usr/bin/env python3
"""Vendor historical fantasy ADP as static, league-agnostic per-season files.

Source: Fantasy Football Calculator public mock-draft ADP API
(https://fantasyfootballcalculator.com/api/v1/adp/ppr). We persist only the
factual fields we use — player name, position, team, and the numeric ADP — keyed
by season. ADP values are facts derived from aggregated mock drafts (not
copyrightable expression); we redistribute a minimal subset and record the source
so the vendored dataset stays reproducible and shareable.

The worker joins these files to a league's drafted players by normalized name at
analysis time (see analytics/adp.py), so the vendored data is league-agnostic and
refreshed manually each new season.

Run once (needs network):
    python3 scripts/fetch_adp.py
"""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "services" / "worker" / "mygm_worker" / "data" / "adp"
SOURCE = "fantasyfootballcalculator.com PPR 12-team mock-draft ADP"
SEASONS = (2020, 2021, 2022, 2023, 2024, 2025, 2026)


def fetch_season(season: int) -> list[dict[str, object]]:
    url = f"https://fantasyfootballcalculator.com/api/v1/adp/ppr?teams=12&year={season}"
    request = urllib.request.Request(  # noqa: S310 - fixed https host
        url, headers={"User-Agent": "Mozilla/5.0 (MyGM ADP vendor)"}
    )
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
        payload = json.loads(response.read().decode("utf-8"))
    players = payload.get("players") or []
    rows: list[dict[str, object]] = []
    for player in players:
        name = player.get("name")
        adp = player.get("adp")
        if not name or adp is None:
            continue
        rows.append(
            {
                "name": name,
                "position": player.get("position", ""),
                "team": player.get("team", ""),
                "adp": float(adp),
            }
        )
    return rows


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    index: dict[str, int] = {}
    for season in SEASONS:
        try:
            rows = fetch_season(season)
        except Exception as error:  # noqa: BLE001 - best-effort vendor step
            print(f"{season}: fetch failed ({error}); skipping")
            continue
        if not rows:
            print(f"{season}: no ADP rows available; skipping")
            continue
        out_path = OUT_DIR / f"adp_{season}.json"
        out_path.write_text(
            json.dumps({"source": SOURCE, "season": season, "players": rows}, indent=2) + "\n",
            encoding="utf-8",
        )
        index[str(season)] = len(rows)
        print(f"{season}: vendored {len(rows)} players -> {out_path.relative_to(ROOT)}")
    (OUT_DIR / "INDEX.json").write_text(
        json.dumps({"source": SOURCE, "seasons": index}, indent=2) + "\n", encoding="utf-8"
    )
    missing = [season for season in SEASONS if str(season) not in index]
    print(f"Vendored {len(index)}/{len(SEASONS)} configured seasons.")
    if missing:
        # Surface gaps loudly — the worker degrades gracefully (those seasons'
        # picks score 0 reach), but a silent drop would hide a transient failure.
        print(f"WARNING: no ADP for seasons {missing} (source had no data or fetch failed).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
