from __future__ import annotations

# pyright: reportAny=false, reportArgumentType=false, reportAttributeAccessIssue=false, reportCallIssue=false, reportExplicitAny=false, reportImplicitStringConcatenation=false, reportImportCycles=false, reportOperatorIssue=false, reportUnannotatedClassAttribute=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnnecessaryIsInstance=false, reportUnusedCallResult=false
import json
import os
import time
import urllib.parse
from collections import defaultdict
from pathlib import Path
from typing import Any

from mygm_worker.espn.export_client import EspnExporter
from mygm_worker.espn.export_common import load_dotenv
from mygm_worker.espn.lookup_common import (
    clean_points,
    merge_player_meta,
    read_json,
    set_weekly_point,
)


def collect_season_player_ids(
    players: dict[str, dict[str, Any]],
) -> dict[int, set[str]]:
    by_season: dict[int, set[str]] = defaultdict(set)
    for player_id, record in players.items():
        for season in record["weekly_points"]:
            by_season[int(season)].add(player_id)
        for context in record["trade_contexts"]:
            by_season[int(context["season"])].add(player_id)
    return by_season


def player_card_url(league_id: str, year: int) -> str:
    params = urllib.parse.urlencode([("view", "kona_playercard")])
    return (
        "https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/"
        f"seasons/{year}/segments/0/leagues/{league_id}?{params}"
    )


def fetch_player_cards(
    exporter: EspnExporter,
    year: int,
    player_ids: list[str],
    final_scoring_period: int,
    batch_size: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    players: list[dict[str, Any]] = []
    summary = {"requests": 0, "successes": 0, "players_returned": 0, "errors": []}
    url = player_card_url(exporter.league_id, year)

    for start in range(0, len(player_ids), batch_size):
        batch = [int(player_id) for player_id in player_ids[start : start + batch_size]]
        filters = {
            "players": {
                "filterIds": {"value": batch},
                "filterStatsForTopScoringPeriodIds": {
                    "value": final_scoring_period,
                    "additionalValue": [f"00{year}", f"10{year}"],
                },
            }
        }
        headers = {"x-fantasy-filter": json.dumps(filters, separators=(",", ":"))}
        status, data, error = exporter.request_json(url, headers)
        summary["requests"] += 1
        if status == 200 and isinstance(data, dict):
            batch_players = data.get("players") or []
            players.extend(batch_players)
            summary["successes"] += 1
            summary["players_returned"] += len(batch_players)
        else:
            summary["errors"].append(
                {
                    "year": year,
                    "batch_start": start,
                    "batch_size": len(batch),
                    "status": status,
                    "error": error,
                }
            )

    return players, summary


def enrich_from_player_cards(
    players: dict[str, dict[str, Any]],
    export_root: Path,
    env_file: Path,
    batch_size: int,
    delay: float,
) -> dict[str, Any]:
    load_dotenv(env_file)
    league_id = os.environ.get("ESPN_LEAGUE_ID")
    swid = os.environ.get("ESPN_SWID")
    espn_s2 = os.environ.get("ESPN_S2")
    if not league_id or not swid or not espn_s2:
        return {"enabled": False, "reason": "Missing ESPN_LEAGUE_ID, ESPN_SWID, or ESPN_S2"}

    exporter = EspnExporter(league_id, swid, espn_s2, export_root, delay)
    season_summaries: dict[str, Any] = {}
    for season, ids in sorted(collect_season_player_ids(players).items()):
        final_scoring_period = season_final_scoring_period(export_root, season)
        cards, request_summary = fetch_player_cards(
            exporter=exporter,
            year=season,
            player_ids=sorted(ids, key=int),
            final_scoring_period=final_scoring_period,
            batch_size=batch_size,
        )
        actual_stat_rows = merge_player_cards(players, cards, season, final_scoring_period)
        season_summaries[str(season)] = {
            **request_summary,
            "discovered_player_ids": len(ids),
            "actual_stat_rows_merged": actual_stat_rows,
        }
        time.sleep(delay)

    return {"enabled": True, "season_summaries": season_summaries}


def season_final_scoring_period(export_root: Path, season: int) -> int:
    summary_path = export_root / f"season_{season}" / "_season_summary.json"
    if not summary_path.exists():
        return 17
    return int(read_json(summary_path).get("final_scoring_period") or 17)


def merge_player_cards(
    players: dict[str, dict[str, Any]],
    cards: list[dict[str, Any]],
    season: int,
    final_scoring_period: int,
) -> int:
    actual_stat_rows = 0
    for raw_player in cards:
        player = raw_player.get("player") if isinstance(raw_player, dict) else None
        if not player:
            player = raw_player
        if not isinstance(player, dict) or player.get("id") is None:
            continue
        record = merge_player_meta(players, int(player["id"]), player, "player_card")
        for stat in player.get("stats") or []:
            if stat.get("seasonId") != season or stat.get("statSourceId") != 0:
                continue
            if stat.get("statSplitTypeId") != 1:
                continue
            week = stat.get("scoringPeriodId")
            if not isinstance(week, int) or week < 1 or week > final_scoring_period:
                continue
            set_weekly_point(
                record,
                season,
                week,
                clean_points(stat.get("appliedTotal")),
                "player_card_actual",
                {
                    "proTeamId": stat.get("proTeamId"),
                    "appliedStats": stat.get("appliedStats") or {},
                },
            )
            actual_stat_rows += 1
    return actual_stat_rows
