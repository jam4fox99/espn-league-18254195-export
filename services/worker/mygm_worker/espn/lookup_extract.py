from __future__ import annotations

# pyright: reportAny=false, reportArgumentType=false, reportAttributeAccessIssue=false, reportCallIssue=false, reportExplicitAny=false, reportImplicitStringConcatenation=false, reportImportCycles=false, reportOperatorIssue=false, reportUnannotatedClassAttribute=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnnecessaryIsInstance=false, reportUnusedCallResult=false
from collections import Counter
from pathlib import Path
from typing import Any

from mygm_worker.espn.lookup_common import (
    LINEUP_SLOT_MAP,
    STARTING_LINEUP_SLOTS,
    append_unique,
    clean_points,
    empty_player,
    merge_player_meta,
    pick_stat,
    read_json,
    season_from_dir,
    set_weekly_point,
    week_from_file,
)


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
                extract_matchup_players(players, summary, season, week, matchup)

    summary["box_score_player_ids"] = len(summary["box_score_player_ids"])
    return summary


def extract_matchup_players(
    players: dict[str, dict[str, Any]],
    summary: dict[str, Any],
    season: int,
    week: int,
    matchup: dict[str, Any],
) -> None:
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
            add_box_score_entry(
                players=players,
                entry=entry,
                player_id=int(player_id),
                season=season,
                week=week,
                matchup_id=matchup_id,
                matchup_period=matchup_period,
                side=side,
                team_id=team_id,
            )


def add_box_score_entry(
    *,
    players: dict[str, dict[str, Any]],
    entry: dict[str, Any],
    player_id: int,
    season: int,
    week: int,
    matchup_id: Any,
    matchup_period: Any,
    side: str,
    team_id: Any,
) -> None:
    ppe = entry.get("playerPoolEntry") or {}
    player = ppe.get("player") or {}
    record = merge_player_meta(players, player_id, player, "box_score")
    stats = player.get("stats") or []
    actual = pick_stat(stats, season, week, 0)
    projected = pick_stat(stats, season, week, 1)
    points = clean_points(actual.get("appliedTotal") if actual else ppe.get("appliedStatTotal"))
    projected_points = clean_points(projected.get("appliedTotal") if projected else None)
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
        {"projected_points": projected_points, "appearances": [appearance]},
    )


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
            add_trade_context(players, summary, season, index, tx)

    return {
        "trade_transactions": summary["trade_transactions"],
        "trade_items": summary["trade_items"],
        "trade_player_ids": len(summary["trade_player_ids"]),
        "trade_type_counts": dict(summary["trade_type_counts"]),
        "trade_status_counts": dict(summary["trade_status_counts"]),
    }


def add_trade_context(
    players: dict[str, dict[str, Any]],
    summary: dict[str, Any],
    season: int,
    index: int,
    tx: dict[str, Any],
) -> None:
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
