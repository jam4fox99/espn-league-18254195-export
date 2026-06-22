#!/usr/bin/env python3
"""Build playerId -> player name + weekly fantasy points lookup JSON.

Inputs are the raw ESPN export files created by export_espn_league.py. When
credentials are available in .env, this script enriches discovered player IDs
with ESPN's player-card endpoint so traded players can be graded even if they
do not appear in a league box score every week.
"""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.parse
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from export_espn_league import EspnExporter, load_dotenv, write_json


POSITION_MAP = {
    0: "QB",
    2: "RB",
    4: "WR",
    6: "TE",
    16: "D/ST",
    17: "K",
}

LINEUP_SLOT_MAP = {
    0: "QB",
    2: "RB",
    4: "WR",
    6: "TE",
    16: "D/ST",
    17: "K",
    20: "BE",
    21: "IR",
    23: "FLEX",
}

STARTING_LINEUP_SLOTS = {0, 2, 4, 6, 16, 17, 23}
TRADE_TRANSACTION_TYPES = {
    "TRADE_ACCEPT",
    "TRADE_DECLINE",
    "TRADE_ERROR",
    "TRADE_PROPOSAL",
    "TRADE_UPHOLD",
    "TRADE_VETO",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def season_from_dir(path: Path) -> int:
    return int(path.name.split("_", 1)[1])


def week_from_file(path: Path) -> int:
    return int(path.stem.split("_", 1)[1])


def player_name(player: dict[str, Any]) -> str | None:
    full = player.get("fullName")
    if full:
        return str(full)
    first = player.get("firstName")
    last = player.get("lastName")
    if first or last:
        return " ".join(part for part in [first, last] if part)
    return None


def clean_points(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return round(float(value), 4)
    except (TypeError, ValueError):
        return None


def pick_stat(
    stats: list[dict[str, Any]],
    season: int,
    week: int,
    stat_source_id: int,
) -> dict[str, Any] | None:
    for stat in stats:
        if (
            stat.get("seasonId") == season
            and stat.get("scoringPeriodId") == week
            and stat.get("statSourceId") == stat_source_id
            and stat.get("statSplitTypeId") == 1
        ):
            return stat
    return None


def empty_player(player_id: int) -> dict[str, Any]:
    return {
        "playerId": player_id,
        "name": None,
        "firstName": None,
        "lastName": None,
        "defaultPositionId": None,
        "defaultPosition": None,
        "proTeamIds": [],
        "name_sources": [],
        "weekly_points": {},
        "weekly_details": {},
        "box_score_appearances": [],
        "trade_contexts": [],
        "sources": [],
    }


def append_unique(values: list[Any], value: Any) -> None:
    if value is not None and value not in values:
        values.append(value)


def merge_player_meta(
    players: dict[str, dict[str, Any]],
    player_id: int,
    player: dict[str, Any],
    source: str,
) -> dict[str, Any]:
    record = players.setdefault(str(player_id), empty_player(player_id))
    name = player_name(player)
    if name and not record["name"]:
        record["name"] = name
    if player.get("firstName") and not record["firstName"]:
        record["firstName"] = player.get("firstName")
    if player.get("lastName") and not record["lastName"]:
        record["lastName"] = player.get("lastName")
    if player.get("defaultPositionId") is not None:
        record["defaultPositionId"] = player.get("defaultPositionId")
        record["defaultPosition"] = POSITION_MAP.get(player.get("defaultPositionId"))
    append_unique(record["proTeamIds"], player.get("proTeamId"))
    append_unique(record["name_sources"], source if name else None)
    append_unique(record["sources"], source)
    return record


def set_weekly_point(
    player_record: dict[str, Any],
    season: int,
    week: int,
    points: float | None,
    source: str,
    detail_updates: dict[str, Any] | None = None,
) -> None:
    if points is None:
        return

    season_key = str(season)
    week_key = str(week)
    player_record["weekly_points"].setdefault(season_key, {})
    player_record["weekly_details"].setdefault(season_key, {})

    detail = player_record["weekly_details"][season_key].setdefault(
        week_key,
        {
            "points": points,
            "source": source,
            "sources": [],
        },
    )

    old_points = detail.get("points")
    if old_points is None or source == "player_card_actual":
        detail["points"] = points
        detail["source"] = source
    elif old_points != points:
        conflicts = detail.setdefault("point_conflicts", [])
        conflict = {"source": source, "points": points}
        if conflict not in conflicts:
            conflicts.append(conflict)

    append_unique(detail["sources"], source)
    if detail_updates:
        for key, value in detail_updates.items():
            if key == "appearances":
                detail.setdefault("appearances", [])
                detail["appearances"].extend(value)
            elif value is not None:
                detail[key] = value

    player_record["weekly_points"][season_key][week_key] = detail["points"]


def extract_box_scores(
    export_root: Path,
    players: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    summary = {
        "box_score_files": 0,
        "box_score_player_entries": 0,
        "box_score_player_ids": set(),
    }

    for season_dir in sorted(export_root.glob("season_*")):
        if not season_dir.is_dir():
            continue
        season = season_from_dir(season_dir)
        for week_path in sorted((season_dir / "box_scores").glob("week_*.json")):
            summary["box_score_files"] += 1
            week = week_from_file(week_path)
            payload = read_json(week_path)
            data = payload.get("data") or {}
            for matchup in data.get("schedule") or []:
                matchup_id = matchup.get("id")
                matchup_period = matchup.get("matchupPeriodId")
                for side in ("home", "away"):
                    team_data = matchup.get(side) or {}
                    team_id = team_data.get("teamId")
                    roster = team_data.get("rosterForCurrentScoringPeriod") or {}
                    for entry in roster.get("entries") or []:
                        player_id = entry.get("playerId")
                        if player_id is None:
                            continue

                        summary["box_score_player_entries"] += 1
                        summary["box_score_player_ids"].add(str(player_id))

                        ppe = entry.get("playerPoolEntry") or {}
                        player = ppe.get("player") or {}
                        record = merge_player_meta(
                            players,
                            int(player_id),
                            player,
                            "box_score",
                        )

                        stats = player.get("stats") or []
                        actual = pick_stat(stats, season, week, 0)
                        projected = pick_stat(stats, season, week, 1)
                        points = clean_points(
                            actual.get("appliedTotal") if actual else ppe.get("appliedStatTotal")
                        )
                        projected_points = clean_points(
                            projected.get("appliedTotal") if projected else None
                        )
                        lineup_slot_id = entry.get("lineupSlotId")
                        appearance = {
                            "season": season,
                            "week": week,
                            "teamId": team_id,
                            "matchupId": matchup_id,
                            "matchupPeriodId": matchup_period,
                            "side": side,
                            "lineupSlotId": lineup_slot_id,
                            "lineupSlot": LINEUP_SLOT_MAP.get(lineup_slot_id),
                            "isStarter": lineup_slot_id in STARTING_LINEUP_SLOTS,
                            "entryStatus": entry.get("status"),
                            "injuryStatus": entry.get("injuryStatus"),
                        }
                        record["box_score_appearances"].append(appearance)
                        set_weekly_point(
                            record,
                            season,
                            week,
                            points,
                            "box_score_actual" if actual else "box_score_entry_total",
                            {
                                "projected_points": projected_points,
                                "appearances": [appearance],
                            },
                        )

    summary["box_score_player_ids"] = len(summary["box_score_player_ids"])
    return summary


def extract_trade_contexts(
    export_root: Path,
    players: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    summary = {
        "trade_transactions": 0,
        "trade_items": 0,
        "trade_player_ids": set(),
        "trade_type_counts": Counter(),
        "trade_status_counts": Counter(),
    }

    for season_dir in sorted(export_root.glob("season_*")):
        if not season_dir.is_dir():
            continue
        season = season_from_dir(season_dir)
        trades_path = season_dir / "transactions" / "_trades.json"
        if not trades_path.exists():
            continue
        for index, tx in enumerate(read_json(trades_path)):
            summary["trade_transactions"] += 1
            summary["trade_type_counts"][tx.get("type") or "UNKNOWN"] += 1
            summary["trade_status_counts"][tx.get("status") or "UNKNOWN"] += 1
            for item in tx.get("items") or []:
                player_id = item.get("playerId")
                if player_id is None:
                    continue
                summary["trade_items"] += 1
                summary["trade_player_ids"].add(str(player_id))
                record = players.setdefault(str(player_id), empty_player(int(player_id)))
                append_unique(record["sources"], "trade_item")
                record["trade_contexts"].append(
                    {
                        "season": season,
                        "transactionIndex": index,
                        "transactionType": tx.get("type"),
                        "transactionStatus": tx.get("status"),
                        "scoringPeriodId": tx.get("scoringPeriodId"),
                        "date": tx.get("date"),
                        "itemType": item.get("type"),
                        "fromTeamId": item.get("fromTeamId"),
                        "toTeamId": item.get("toTeamId"),
                        "fromLineupSlotId": item.get("fromLineupSlotId"),
                        "toLineupSlotId": item.get("toLineupSlotId"),
                    }
                )

    return {
        "trade_transactions": summary["trade_transactions"],
        "trade_items": summary["trade_items"],
        "trade_player_ids": len(summary["trade_player_ids"]),
        "trade_type_counts": dict(summary["trade_type_counts"]),
        "trade_status_counts": dict(summary["trade_status_counts"]),
    }


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
    summary = {
        "requests": 0,
        "successes": 0,
        "players_returned": 0,
        "errors": [],
    }
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
        headers = {
            "x-fantasy-filter": json.dumps(filters, separators=(",", ":")),
        }
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
        return {
            "enabled": False,
            "reason": "Missing ESPN_LEAGUE_ID, ESPN_SWID, or ESPN_S2",
        }

    exporter = EspnExporter(
        league_id=league_id,
        swid=swid,
        espn_s2=espn_s2,
        out_dir=export_root,
        delay_seconds=delay,
    )
    season_ids = collect_season_player_ids(players)
    season_summaries: dict[str, Any] = {}

    for season, ids in sorted(season_ids.items()):
        summary_path = export_root / f"season_{season}" / "_season_summary.json"
        if summary_path.exists():
            season_summary = read_json(summary_path)
            final_scoring_period = int(season_summary.get("final_scoring_period") or 17)
        else:
            final_scoring_period = 17

        cards, request_summary = fetch_player_cards(
            exporter=exporter,
            year=season,
            player_ids=sorted(ids, key=lambda value: int(value)),
            final_scoring_period=final_scoring_period,
            batch_size=batch_size,
        )

        actual_stat_rows = 0
        for raw_player in cards:
            player = raw_player.get("player") if isinstance(raw_player, dict) else None
            if not player:
                player = raw_player
            if not isinstance(player, dict) or player.get("id") is None:
                continue
            player_id = int(player["id"])
            record = merge_player_meta(
                players,
                player_id,
                player,
                "player_card",
            )
            for stat in player.get("stats") or []:
                if (
                    stat.get("seasonId") != season
                    or stat.get("statSourceId") != 0
                    or stat.get("statSplitTypeId") != 1
                ):
                    continue
                week = stat.get("scoringPeriodId")
                if not isinstance(week, int):
                    continue
                if week < 1 or week > final_scoring_period:
                    continue
                points = clean_points(stat.get("appliedTotal"))
                set_weekly_point(
                    record,
                    season,
                    week,
                    points,
                    "player_card_actual",
                    {
                        "proTeamId": stat.get("proTeamId"),
                        "appliedStats": stat.get("appliedStats") or {},
                    },
                )
                actual_stat_rows += 1

        season_summaries[str(season)] = {
            **request_summary,
            "discovered_player_ids": len(ids),
            "actual_stat_rows_merged": actual_stat_rows,
        }
        time.sleep(delay)

    return {
        "enabled": True,
        "season_summaries": season_summaries,
    }


def sorted_weekly_points(record: dict[str, Any]) -> None:
    record["proTeamIds"] = sorted(record["proTeamIds"], key=lambda value: str(value))
    record["sources"] = sorted(record["sources"])
    record["name_sources"] = sorted(record["name_sources"])

    record["weekly_points"] = {
        season: {
            week: weeks[week]
            for week in sorted(weeks, key=lambda value: int(value))
        }
        for season, weeks in sorted(
            record["weekly_points"].items(),
            key=lambda item: int(item[0]),
        )
    }
    record["weekly_details"] = {
        season: {
            week: weeks[week]
            for week in sorted(weeks, key=lambda value: int(value))
        }
        for season, weeks in sorted(
            record["weekly_details"].items(),
            key=lambda item: int(item[0]),
        )
    }


def build_flat_rows(players: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for player_id, record in sorted(players.items(), key=lambda item: int(item[0])):
        for season, weeks in record["weekly_points"].items():
            for week, points in weeks.items():
                details = record["weekly_details"].get(season, {}).get(week, {})
                rows.append(
                    {
                        "playerId": int(player_id),
                        "name": record.get("name"),
                        "season": int(season),
                        "week": int(week),
                        "points": points,
                        "source": details.get("source"),
                        "defaultPosition": record.get("defaultPosition"),
                        "defaultPositionId": record.get("defaultPositionId"),
                    }
                )
    return sorted(rows, key=lambda row: (row["season"], row["week"], row["playerId"]))


def build_trade_coverage(players: dict[str, dict[str, Any]]) -> dict[str, Any]:
    trade_player_ids = {
        player_id for player_id, record in players.items() if record["trade_contexts"]
    }
    unresolved_names = sorted(
        [
            int(player_id)
            for player_id in trade_player_ids
            if not players[player_id].get("name")
        ]
    )
    no_weekly_points = sorted(
        [
            int(player_id)
            for player_id in trade_player_ids
            if not players[player_id].get("weekly_points")
        ]
    )
    executed_trade_accept_ids = {
        player_id
        for player_id, record in players.items()
        for context in record["trade_contexts"]
        if context["transactionType"] == "TRADE_ACCEPT"
        and context["transactionStatus"] == "EXECUTED"
        and context["itemType"] == "TRADE"
    }
    executed_without_points = sorted(
        [
            int(player_id)
            for player_id in executed_trade_accept_ids
            if not players[player_id].get("weekly_points")
        ]
    )
    return {
        "trade_player_ids": len(trade_player_ids),
        "trade_player_ids_with_names": len(trade_player_ids) - len(unresolved_names),
        "trade_player_ids_with_weekly_points": len(trade_player_ids) - len(no_weekly_points),
        "unresolved_name_player_ids": unresolved_names,
        "no_weekly_points_player_ids": no_weekly_points,
        "executed_trade_accept_player_ids": len(executed_trade_accept_ids),
        "executed_trade_accept_player_ids_without_points": executed_without_points,
    }


def write_lookup_outputs(
    output_dir: Path,
    players: dict[str, dict[str, Any]],
    extraction_summary: dict[str, Any],
    enrichment_summary: dict[str, Any],
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    for record in players.values():
        sorted_weekly_points(record)

    sorted_players = {
        player_id: players[player_id]
        for player_id in sorted(players, key=lambda value: int(value))
    }
    flat_rows = build_flat_rows(sorted_players)
    trade_coverage = build_trade_coverage(sorted_players)
    summary = {
        "generated_at": now_iso(),
        "players_total": len(sorted_players),
        "players_with_names": sum(1 for p in sorted_players.values() if p.get("name")),
        "players_with_weekly_points": sum(
            1 for p in sorted_players.values() if p.get("weekly_points")
        ),
        "weekly_point_rows": len(flat_rows),
        "extraction": extraction_summary,
        "enrichment": enrichment_summary,
        "trade_coverage": trade_coverage,
        "outputs": {
            "player_weekly_points": str(output_dir / "player_weekly_points.json"),
            "player_weekly_points_flat": str(
                output_dir / "player_weekly_points_flat.json"
            ),
            "trade_player_coverage": str(output_dir / "trade_player_coverage.json"),
            "lookup_summary": str(output_dir / "lookup_summary.json"),
        },
    }

    write_json(
        output_dir / "player_weekly_points.json",
        {
            "_meta": {
                "generated_at": summary["generated_at"],
                "description": (
                    "Map of ESPN playerId to player name and weekly fantasy "
                    "points. weekly_points is season -> week -> points."
                ),
            },
            "players": sorted_players,
        },
    )
    write_json(output_dir / "player_weekly_points_flat.json", flat_rows)
    write_json(output_dir / "trade_player_coverage.json", trade_coverage)
    write_json(output_dir / "lookup_summary.json", summary)
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build playerId -> weekly points lookup from ESPN export JSON."
    )
    parser.add_argument(
        "--export-root",
        default="espn_exports/league_18254195",
        help="Path containing export_manifest.json and season_* directories.",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Defaults to <export-root>/player_lookup.",
    )
    parser.add_argument("--env-file", default=".env")
    parser.add_argument(
        "--no-enrich",
        action="store_true",
        help="Skip ESPN player-card enrichment and use box score data only.",
    )
    parser.add_argument("--batch-size", type=int, default=50)
    parser.add_argument("--delay", type=float, default=0.15)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    export_root = Path(args.export_root).resolve()
    if not (export_root / "export_manifest.json").exists():
        raise SystemExit(f"Missing export manifest under {export_root}")

    output_dir = Path(args.output_dir).resolve() if args.output_dir else export_root / "player_lookup"
    players: dict[str, dict[str, Any]] = {}

    box_summary = extract_box_scores(export_root, players)
    trade_summary = extract_trade_contexts(export_root, players)
    extraction_summary = {
        "box_scores": box_summary,
        "trades": trade_summary,
    }

    if args.no_enrich:
        enrichment_summary = {"enabled": False, "reason": "--no-enrich"}
    else:
        enrichment_summary = enrich_from_player_cards(
            players=players,
            export_root=export_root,
            env_file=Path(args.env_file),
            batch_size=args.batch_size,
            delay=args.delay,
        )

    summary = write_lookup_outputs(
        output_dir=output_dir,
        players=players,
        extraction_summary=extraction_summary,
        enrichment_summary=enrichment_summary,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

