from __future__ import annotations

# pyright: reportAny=false, reportArgumentType=false, reportAttributeAccessIssue=false, reportCallIssue=false, reportExplicitAny=false, reportImplicitStringConcatenation=false, reportImportCycles=false, reportOperatorIssue=false, reportUnannotatedClassAttribute=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnnecessaryIsInstance=false, reportUnusedCallResult=false
from pathlib import Path
from typing import Any

from mygm_worker.espn.export_common import write_json
from mygm_worker.espn.lookup_common import now_iso


def sorted_weekly_points(record: dict[str, Any]) -> None:
    record["proTeamIds"] = sorted(record["proTeamIds"], key=str)
    record["sources"] = sorted(record["sources"])
    record["name_sources"] = sorted(record["name_sources"])
    record["weekly_points"] = {
        season: {week: weeks[week] for week in sorted(weeks, key=int)}
        for season, weeks in sorted(record["weekly_points"].items(), key=lambda item: int(item[0]))
    }
    record["weekly_details"] = {
        season: {week: weeks[week] for week in sorted(weeks, key=int)}
        for season, weeks in sorted(record["weekly_details"].items(), key=lambda item: int(item[0]))
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
        int(player_id) for player_id in trade_player_ids if not players[player_id].get("name")
    )
    no_weekly_points = sorted(
        int(player_id)
        for player_id in trade_player_ids
        if not players[player_id].get("weekly_points")
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
        int(player_id)
        for player_id in executed_trade_accept_ids
        if not players[player_id].get("weekly_points")
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

    sorted_players = {player_id: players[player_id] for player_id in sorted(players, key=int)}
    flat_rows = build_flat_rows(sorted_players)
    trade_coverage = build_trade_coverage(sorted_players)
    summary = {
        "generated_at": now_iso(),
        "players_total": len(sorted_players),
        "players_with_names": sum(1 for player in sorted_players.values() if player.get("name")),
        "players_with_weekly_points": sum(
            1 for player in sorted_players.values() if player.get("weekly_points")
        ),
        "weekly_point_rows": len(flat_rows),
        "extraction": extraction_summary,
        "enrichment": enrichment_summary,
        "trade_coverage": trade_coverage,
        "outputs": {
            "player_weekly_points": str(output_dir / "player_weekly_points.json"),
            "player_weekly_points_flat": str(output_dir / "player_weekly_points_flat.json"),
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
