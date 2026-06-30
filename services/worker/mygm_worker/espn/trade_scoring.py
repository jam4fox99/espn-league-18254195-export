from __future__ import annotations

# pyright: reportAny=false, reportArgumentType=false, reportAttributeAccessIssue=false, reportCallIssue=false, reportExplicitAny=false, reportImplicitStringConcatenation=false, reportImportCycles=false, reportOperatorIssue=false, reportUnannotatedClassAttribute=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnnecessaryIsInstance=false, reportUnusedCallResult=false
from typing import Any

from mygm_worker.espn.trade_common import grade_for_net, ms_to_iso


def player_week_points(
    players: dict[str, dict[str, Any]],
    player_id: int,
    season: int,
    start_week: int,
    final_week: int,
) -> tuple[float, dict[str, float], str | None]:
    player = players.get(str(player_id))
    if not player:
        return 0.0, {}, None

    weekly = player.get("weekly_points", {}).get(str(season), {}) or {}
    counted: dict[str, float] = {}
    total = 0.0
    for week_text, points in weekly.items():
        try:
            week = int(week_text)
            value = float(points)
        except (TypeError, ValueError):
            continue
        if start_week <= week <= final_week:
            counted[str(week)] = round(value, 4)
            total += value
    return (
        round(total, 4),
        dict(sorted(counted.items(), key=lambda item: int(item[0]))),
        player.get("name"),
    )


def build_side(
    team_id: int,
    team_names: dict[int, str],
    trade_items: list[dict[str, Any]],
    players: dict[str, dict[str, Any]],
    season: int,
    start_week: int,
    final_week: int,
) -> dict[str, Any]:
    player_rows: list[dict[str, Any]] = []
    total = 0.0
    for item in trade_items:
        player_id = int(item["playerId"])
        points, weekly_points, name = player_week_points(
            players,
            player_id,
            season,
            start_week,
            final_week,
        )
        player_rows.append(
            {
                "playerId": player_id,
                "name": name or f"Unknown Player {player_id}",
                "fromTeamId": item.get("fromTeamId"),
                "toTeamId": item.get("toTeamId"),
                "post_trade_points": points,
                "weekly_points": weekly_points,
            }
        )
        total += points

    return {
        "team_id": team_id,
        "team_name": team_names.get(team_id, f"Team {team_id}"),
        "points": round(total, 4),
        "players": player_rows,
    }


def usable_trade_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        item
        for item in items
        if item.get("type") == "TRADE"
        and item.get("playerId") is not None
        and item.get("toTeamId") not in (None, 0)
        and item.get("fromTeamId") not in (None, 0)
    ]


def group_items_by_receiving_team(
    trade_items: list[dict[str, Any]],
) -> dict[int, list[dict[str, Any]]]:
    grouped: dict[int, list[dict[str, Any]]] = {}
    for item in trade_items:
        grouped.setdefault(int(item["toTeamId"]), []).append(item)
    return grouped


def grade_trade(
    tx: dict[str, Any],
    team_names: dict[int, str],
    final_week: int,
    players: dict[str, dict[str, Any]],
    include_trade_week: bool,
    transactions_by_season_id: dict[tuple[int, str], dict[str, Any]],
) -> dict[str, Any]:
    context = trade_context(tx, include_trade_week, transactions_by_season_id)
    row = ungraded_row(tx, team_names, final_week, context)
    if len(context["grouped"]) != 2:
        row["ungraded_reason"] = (
            f"expected 2 receiving teams, found {len(context['grouped'])} "
            f"from {len(context['trade_items'])} TRADE items"
        )
        return row

    team_ids = sorted(context["grouped"])
    side_a = build_side(
        team_ids[0],
        team_names,
        context["grouped"][team_ids[0]],
        players,
        row["season"],
        row["score_start_week"],
        final_week,
    )
    side_b = build_side(
        team_ids[1],
        team_names,
        context["grouped"][team_ids[1]],
        players,
        row["season"],
        row["score_start_week"],
        final_week,
    )
    apply_graded_sides(row, side_a, side_b)
    return row


def trade_context(
    tx: dict[str, Any],
    include_trade_week: bool,
    transactions_by_season_id: dict[tuple[int, str], dict[str, Any]],
) -> dict[str, Any]:
    season = int(tx["_season"])
    raw_items = tx.get("items") or []
    trade_items = usable_trade_items(raw_items)
    grouped = group_items_by_receiving_team(trade_items)
    context = {
        "season": season,
        "trade_week": int(tx.get("scoringPeriodId") or 0),
        "start_week": int(tx.get("scoringPeriodId") or 0)
        if include_trade_week
        else int(tx.get("scoringPeriodId") or 0) + 1,
        "raw_items": raw_items,
        "trade_items": trade_items,
        "grouped": grouped,
        "source": "accept_transaction",
        "source_tx": tx,
    }
    if len(grouped) == 2 or not tx.get("relatedTransactionId"):
        return context
    related_tx = transactions_by_season_id.get((season, str(tx["relatedTransactionId"])))
    if not related_tx:
        return context
    related_items = related_tx.get("items") or []
    related_trade_items = usable_trade_items(related_items)
    related_grouped = group_items_by_receiving_team(related_trade_items)
    if len(related_grouped) == 2:
        context.update(
            {
                "raw_items": raw_items,
                "trade_items": related_trade_items,
                "grouped": related_grouped,
                "source": "related_transaction",
                "source_tx": related_tx,
            }
        )
    return context


def ungraded_row(
    tx: dict[str, Any],
    team_names: dict[int, str],
    final_week: int,
    context: dict[str, Any],
) -> dict[str, Any]:
    source_tx = context["source_tx"]
    trade_date_ms = tx.get("processDate") or tx.get("proposedDate")
    return {
        "trade_id": tx.get("id"),
        "related_transaction_id": tx.get("relatedTransactionId"),
        "season": context["season"],
        "week": context["trade_week"],
        "score_start_week": context["start_week"],
        "score_end_week": final_week,
        "trade_date_ms": trade_date_ms,
        "trade_date_utc": ms_to_iso(trade_date_ms),
        "transaction_type": tx.get("type"),
        "transaction_status": tx.get("status"),
        "accepting_team_id": tx.get("teamId"),
        "accepting_team_name": team_names.get(tx.get("teamId"), f"Team {tx.get('teamId')}"),
        "raw_item_count": len(context["raw_items"]),
        "trade_item_count": len(context["trade_items"]),
        "receiving_team_count": len(context["grouped"]),
        "trade_item_source": context["source"],
        "trade_item_source_transaction_id": source_tx.get("id"),
        "trade_item_source_type": source_tx.get("type"),
        "trade_item_source_status": source_tx.get("status"),
        "trade_item_source_raw_item_count": len(source_tx.get("items") or []),
        "grade_status": "ungraded",
        "ungraded_reason": None,
        "team_a_id": None,
        "team_a_name": None,
        "team_a_players": [],
        "team_a_points": None,
        "team_a_grade": None,
        "team_b_id": None,
        "team_b_name": None,
        "team_b_players": [],
        "team_b_points": None,
        "team_b_grade": None,
        "net_difference": None,
        "winner_team_id": None,
        "winner_team_name": None,
    }


def apply_graded_sides(row: dict[str, Any], side_a: dict[str, Any], side_b: dict[str, Any]) -> None:
    net = round(side_a["points"] - side_b["points"], 4)
    winner_id = side_a["team_id"] if net > 0 else side_b["team_id"] if net < 0 else None
    winner_name = side_a["team_name"] if net > 0 else side_b["team_name"] if net < 0 else "Tie"
    row.update(
        {
            "grade_status": "graded",
            "team_a_id": side_a["team_id"],
            "team_a_name": side_a["team_name"],
            "team_a_players": side_a["players"],
            "team_a_points": side_a["points"],
            "team_a_grade": grade_for_net(net),
            "team_b_id": side_b["team_id"],
            "team_b_name": side_b["team_name"],
            "team_b_players": side_b["players"],
            "team_b_points": side_b["points"],
            "team_b_grade": grade_for_net(-net),
            "net_difference": net,
            "winner_team_id": winner_id,
            "winner_team_name": winner_name,
        }
    )
