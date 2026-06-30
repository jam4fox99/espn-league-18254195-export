from __future__ import annotations

# pyright: reportAny=false, reportArgumentType=false, reportAttributeAccessIssue=false, reportCallIssue=false, reportExplicitAny=false, reportImplicitStringConcatenation=false, reportImportCycles=false, reportOperatorIssue=false, reportUnannotatedClassAttribute=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnnecessaryIsInstance=false, reportUnusedCallResult=false
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from mygm_worker.espn.trade_common import ms_to_iso
from mygm_worker.espn.trade_loaders import (
    iter_transactions,
    load_player_lookup,
    load_rosters_by_period,
    load_team_maps,
)
from mygm_worker.espn.trade_scoring import apply_graded_sides, build_side


def reconstruct_trade_rows(
    export_root: Path,
    include_trade_week: bool,
) -> list[dict[str, Any]]:
    """Rebuild executed trades from actual weekly roster movement in the box scores.

    ESPN's transaction log marks many completed trades as PENDING/CANCELED and drops
    their item payloads (especially in later seasons), so the transaction status cannot
    be trusted. The box scores, by contrast, record every player's team each week, so a
    pair of teams that swap players across a week boundary is an unambiguous executed
    trade. Proposals are used only to enrich the player set and supply a trade date.
    """
    team_maps, final_periods = load_team_maps(export_root)
    players = load_player_lookup(export_root)
    rosters = load_rosters_by_period(export_root)
    proposals = _proposals_by_season(iter_transactions(export_root))

    rows: list[dict[str, Any]] = []
    for season in sorted(rosters):
        final_week = final_periods.get(season, 17)
        team_names = team_maps.get(season, {})
        rows.extend(
            _grade_reconstructed(detected, team_names, players, final_week, include_trade_week)
            for detected in _detect_season_trades(
                season, rosters[season], proposals.get(season, [])
            )
        )
    rows.sort(key=lambda row: (row["season"], row["week"], row["trade_id"]))
    return rows


def _proposals_by_season(
    transactions: list[dict[str, Any]],
) -> dict[int, list[dict[str, Any]]]:
    proposals: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for tx in transactions:
        if tx.get("type") != "TRADE_PROPOSAL":
            continue
        items = [
            item
            for item in (tx.get("items") or [])
            if item.get("type") == "TRADE"
            and item.get("playerId") is not None
            and item.get("fromTeamId") not in (None, 0)
            and item.get("toTeamId") not in (None, 0)
        ]
        if not items:
            continue
        teams = frozenset(
            team for item in items for team in (item["fromTeamId"], item["toTeamId"])
        )
        proposals[int(tx["_season"])].append(
            {
                "teams": teams,
                "player_ids": frozenset(int(item["playerId"]) for item in items),
                "items": items,
                "proposed_date": tx.get("proposedDate"),
            }
        )
    return proposals


def _detect_season_trades(
    season: int,
    by_period: dict[int, dict[int, int]],
    proposals: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    weeks = sorted(by_period)
    detected: list[dict[str, Any]] = []
    for index in range(len(weeks) - 1):
        before, after = by_period[weeks[index]], by_period[weeks[index + 1]]
        moves_by_pair: dict[frozenset[int], list[tuple[int, int, int]]] = defaultdict(list)
        for player_id, from_team in before.items():
            to_team = after.get(player_id)
            if to_team is not None and to_team != from_team:
                moves_by_pair[frozenset((from_team, to_team))].append(
                    (player_id, from_team, to_team)
                )
        for pair, moves in moves_by_pair.items():
            directions = {(frm, to) for _, frm, to in moves}
            if len(pair) != 2 or len(directions) < 2:
                continue  # one-directional movement is a waiver/free-agent add, not a trade
            detected.append(
                _build_detected_trade(season, weeks[index + 1], pair, moves, proposals)
            )
    return detected


def _build_detected_trade(
    season: int,
    week: int,
    pair: frozenset[int],
    moves: list[tuple[int, int, int]],
    proposals: list[dict[str, Any]],
) -> dict[str, Any]:
    # The roster movement is authoritative for which players changed teams; proposals are
    # only consulted for a trade date (their player sets cannot be trusted to add players,
    # since several competing proposals can exist between the same two teams in one week).
    items = [
        {"playerId": player_id, "fromTeamId": frm, "toTeamId": to, "type": "TRADE"}
        for player_id, frm, to in moves
    ]
    detected_ids = {player_id for player_id, _, _ in moves}
    proposed_date = None
    best_overlap = 0
    for proposal in proposals:
        if proposal["teams"] != pair:
            continue
        overlap = len(proposal["player_ids"] & detected_ids)
        if overlap > best_overlap:
            best_overlap = overlap
            proposed_date = proposal["proposed_date"]
    return {
        "season": season,
        "week": week,
        "teams": tuple(sorted(pair)),
        "items": items,
        "proposed_date": proposed_date,
    }


def _grade_reconstructed(
    detected: dict[str, Any],
    team_names: dict[int, str],
    players: dict[str, dict[str, Any]],
    final_week: int,
    include_trade_week: bool,
) -> dict[str, Any]:
    season = detected["season"]
    week = detected["week"]
    start_week = week if include_trade_week else week + 1
    grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for item in detected["items"]:
        grouped[int(item["toTeamId"])].append(item)
    row = _base_row(detected, team_names, start_week, final_week)
    if len(grouped) != 2:
        row["ungraded_reason"] = (
            f"expected 2 receiving teams, found {len(grouped)} "
            f"from {len(detected['items'])} TRADE items"
        )
        return row
    team_ids = sorted(grouped)
    side_a = build_side(
        team_ids[0], team_names, grouped[team_ids[0]], players, season, start_week, final_week
    )
    side_b = build_side(
        team_ids[1], team_names, grouped[team_ids[1]], players, season, start_week, final_week
    )
    apply_graded_sides(row, side_a, side_b)
    return row


def _base_row(
    detected: dict[str, Any],
    team_names: dict[int, str],
    start_week: int,
    final_week: int,
) -> dict[str, Any]:
    season = detected["season"]
    week = detected["week"]
    team_a, team_b = detected["teams"]
    canonical_key = _canonical_key(detected)
    trade_id = f"recon:{season}:{week}:{team_a}-{team_b}"
    trade_date_ms = detected.get("proposed_date")
    return {
        "trade_id": trade_id,
        "canonical_trade_key": canonical_key,
        "canonical_group_size": 1,
        "canonical_group_trade_ids": [trade_id],
        "related_transaction_id": None,
        "season": season,
        "week": week,
        "score_start_week": start_week,
        "score_end_week": final_week,
        "trade_date_ms": trade_date_ms,
        "trade_date_utc": ms_to_iso(trade_date_ms) if trade_date_ms else None,
        "transaction_type": "TRADE_RECONSTRUCTED",
        "transaction_status": "EXECUTED",
        "accepting_team_id": team_a,
        "accepting_team_name": team_names.get(team_a, f"Team {team_a}"),
        "raw_item_count": len(detected["items"]),
        "trade_item_count": len(detected["items"]),
        "receiving_team_count": len({int(item["toTeamId"]) for item in detected["items"]}),
        "trade_item_source": "roster_movement",
        "trade_item_source_transaction_id": None,
        "trade_item_source_type": "box_score_roster",
        "trade_item_source_status": "EXECUTED",
        "trade_item_source_raw_item_count": len(detected["items"]),
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


def _canonical_key(detected: dict[str, Any]) -> str:
    player_ids = sorted({int(item["playerId"]) for item in detected["items"]})
    return json.dumps(
        {
            "season": detected["season"],
            "week": detected["week"],
            "teams": list(detected["teams"]),
            "players": player_ids,
        },
        separators=(",", ":"),
        sort_keys=True,
    )
