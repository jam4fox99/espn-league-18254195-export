#!/usr/bin/env python3
"""Grade completed ESPN fantasy trades using post-trade player points."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from export_espn_league import write_json


GRADE_THRESHOLDS = [
    (60, "A+"),
    (40, "A"),
    (25, "B+"),
    (10, "B"),
    (-10, "C"),
    (-25, "D"),
    (-40, "D-"),
]


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def season_from_dir(path: Path) -> int:
    return int(path.name.split("_", 1)[1])


def ms_to_iso(value: Any) -> str | None:
    if value is None:
        return None
    try:
        return datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc).isoformat()
    except (TypeError, ValueError, OSError):
        return None


def grade_for_net(net_points: float | None) -> str | None:
    if net_points is None:
        return None
    for threshold, grade in GRADE_THRESHOLDS:
        if net_points > threshold:
            return grade
    return "F"


def team_display_name(team: dict[str, Any]) -> str:
    name = team.get("name")
    if name:
        return str(name)
    location = team.get("location")
    nickname = team.get("nickname")
    if location or nickname:
        return " ".join(str(part) for part in [location, nickname] if part)
    abbrev = team.get("abbrev")
    if abbrev:
        return str(abbrev)
    team_id = team.get("id")
    return f"Team {team_id}" if team_id is not None else "Unknown Team"


def load_team_maps(export_root: Path) -> tuple[dict[int, dict[int, str]], dict[int, int]]:
    team_maps: dict[int, dict[int, str]] = {}
    final_periods: dict[int, int] = {}
    for season_dir in sorted(export_root.glob("season_*")):
        if not season_dir.is_dir():
            continue
        season = season_from_dir(season_dir)
        core_path = season_dir / "core.json"
        summary_path = season_dir / "_season_summary.json"
        core = read_json(core_path).get("data") or {}
        team_maps[season] = {
            int(team["id"]): team_display_name(team)
            for team in core.get("teams") or []
            if team.get("id") is not None
        }
        if summary_path.exists():
            summary = read_json(summary_path)
            final_periods[season] = int(summary.get("final_scoring_period") or 17)
        else:
            final_periods[season] = int((core.get("status") or {}).get("finalScoringPeriod") or 17)
    return team_maps, final_periods


def load_player_lookup(export_root: Path) -> dict[str, dict[str, Any]]:
    lookup_path = export_root / "player_lookup" / "player_weekly_points.json"
    lookup = read_json(lookup_path)
    return lookup.get("players") or {}


def iter_transactions(export_root: Path) -> list[dict[str, Any]]:
    transactions: list[dict[str, Any]] = []
    for season_dir in sorted(export_root.glob("season_*")):
        if not season_dir.is_dir():
            continue
        season = season_from_dir(season_dir)
        for period_path in sorted((season_dir / "transactions").glob("period_*.json")):
            payload = read_json(period_path)
            data = payload.get("data") or {}
            for index, tx in enumerate(data.get("transactions") or []):
                tx_copy = dict(tx)
                tx_copy["_season"] = season
                tx_copy["_source_file"] = str(period_path)
                tx_copy["_source_index"] = index
                transactions.append(tx_copy)
    return transactions


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
            rounded = round(value, 4)
            counted[str(week)] = rounded
            total += value
    return round(total, 4), dict(sorted(counted.items(), key=lambda item: int(item[0]))), player.get("name")


def build_side(
    *,
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
            players=players,
            player_id=player_id,
            season=season,
            start_week=start_week,
            final_week=final_week,
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


def player_names_for_csv(players: list[dict[str, Any]]) -> str:
    return "; ".join(
        f"{player['name']} ({player['post_trade_points']:.2f})" for player in players
    )


def grade_trade(
    tx: dict[str, Any],
    *,
    team_names: dict[int, str],
    final_week: int,
    players: dict[str, dict[str, Any]],
    include_trade_week: bool,
) -> dict[str, Any]:
    season = int(tx["_season"])
    trade_week = int(tx.get("scoringPeriodId") or 0)
    start_week = trade_week if include_trade_week else trade_week + 1
    trade_date_ms = tx.get("processDate") or tx.get("proposedDate")
    raw_items = tx.get("items") or []
    trade_items = [
        item
        for item in raw_items
        if item.get("type") == "TRADE"
        and item.get("playerId") is not None
        and item.get("toTeamId") not in (None, 0)
        and item.get("fromTeamId") not in (None, 0)
    ]

    grouped: dict[int, list[dict[str, Any]]] = {}
    for item in trade_items:
        grouped.setdefault(int(item["toTeamId"]), []).append(item)

    row: dict[str, Any] = {
        "trade_id": tx.get("id"),
        "related_transaction_id": tx.get("relatedTransactionId"),
        "season": season,
        "week": trade_week,
        "score_start_week": start_week,
        "score_end_week": final_week,
        "trade_date_ms": trade_date_ms,
        "trade_date_utc": ms_to_iso(trade_date_ms),
        "transaction_type": tx.get("type"),
        "transaction_status": tx.get("status"),
        "accepting_team_id": tx.get("teamId"),
        "accepting_team_name": team_names.get(tx.get("teamId"), f"Team {tx.get('teamId')}"),
        "raw_item_count": len(raw_items),
        "trade_item_count": len(trade_items),
        "receiving_team_count": len(grouped),
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

    if len(grouped) != 2:
        row["ungraded_reason"] = (
            f"expected 2 receiving teams, found {len(grouped)} "
            f"from {len(trade_items)} TRADE items"
        )
        return row

    team_ids = sorted(grouped)
    side_a = build_side(
        team_id=team_ids[0],
        team_names=team_names,
        trade_items=grouped[team_ids[0]],
        players=players,
        season=season,
        start_week=start_week,
        final_week=final_week,
    )
    side_b = build_side(
        team_id=team_ids[1],
        team_names=team_names,
        trade_items=grouped[team_ids[1]],
        players=players,
        season=season,
        start_week=start_week,
        final_week=final_week,
    )

    net = round(side_a["points"] - side_b["points"], 4)
    if net > 0:
        winner_id = side_a["team_id"]
        winner_name = side_a["team_name"]
    elif net < 0:
        winner_id = side_b["team_id"]
        winner_name = side_b["team_name"]
    else:
        winner_id = None
        winner_name = "Tie"

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
    return row


def build_trade_grade_rows(
    export_root: Path,
    include_trade_week: bool,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    team_maps, final_periods = load_team_maps(export_root)
    players = load_player_lookup(export_root)
    transactions = iter_transactions(export_root)

    trade_accept_status_counts: Counter[str] = Counter()
    for tx in transactions:
        if tx.get("type") == "TRADE_ACCEPT":
            trade_accept_status_counts[tx.get("status") or "UNKNOWN"] += 1

    completed = [
        tx
        for tx in transactions
        if tx.get("type") == "TRADE_ACCEPT" and tx.get("status") == "EXECUTED"
    ]
    rows = [
        grade_trade(
            tx,
            team_names=team_maps.get(int(tx["_season"]), {}),
            final_week=final_periods.get(int(tx["_season"]), 17),
            players=players,
            include_trade_week=include_trade_week,
        )
        for tx in completed
    ]
    annotate_duplicate_groups(rows)

    status_counts = Counter(row["grade_status"] for row in rows)
    ungraded_reasons = Counter(
        row["ungraded_reason"] for row in rows if row.get("ungraded_reason")
    )
    by_season: dict[str, dict[str, int]] = {}
    for row in rows:
        season = str(row["season"])
        by_season.setdefault(season, {"total": 0, "graded": 0, "ungraded": 0})
        by_season[season]["total"] += 1
        if row["grade_status"] == "graded":
            by_season[season]["graded"] += 1
        else:
            by_season[season]["ungraded"] += 1

    summary = {
        "generated_at": now_iso(),
        "filter": {
            "transaction_type": "TRADE_ACCEPT",
            "transaction_status": "EXECUTED",
            "include_trade_week": include_trade_week,
            "score_rule": (
                "sum player weekly points from trade week through season end"
                if include_trade_week
                else "sum player weekly points from the week after the trade week through season end"
            ),
        },
        "trade_accept_status_counts": dict(trade_accept_status_counts),
        "completed_trade_accept_rows": len(rows),
        "graded_rows": status_counts.get("graded", 0),
        "ungraded_rows": len(rows) - status_counts.get("graded", 0),
        "canonical_graded_trade_groups": len(
            {
                row["canonical_trade_key"]
                for row in rows
                if row.get("canonical_trade_key")
            }
        ),
        "canonical_groups_with_multiple_rows": len(
            {
                row["canonical_trade_key"]
                for row in rows
                if row.get("canonical_trade_key")
                and row.get("canonical_group_size", 1) > 1
            }
        ),
        "ungraded_reasons": dict(ungraded_reasons),
        "by_season": by_season,
        "grade_thresholds": [
            {"net_points_greater_than": threshold, "grade": grade}
            for threshold, grade in GRADE_THRESHOLDS
        ]
        + [{"net_points_less_or_equal_to": -40, "grade": "F"}],
    }
    return rows, summary


def canonical_key_for_row(row: dict[str, Any]) -> str | None:
    if row.get("grade_status") != "graded":
        return None
    team_ids = sorted([row["team_a_id"], row["team_b_id"]])
    player_ids: list[int] = []
    for side in ("team_a", "team_b"):
        for player in row.get(f"{side}_players") or []:
            player_ids.append(int(player["playerId"]))
    return json.dumps(
        {
            "season": row["season"],
            "week": row["week"],
            "teams": team_ids,
            "players": sorted(player_ids),
        },
        separators=(",", ":"),
        sort_keys=True,
    )


def annotate_duplicate_groups(rows: list[dict[str, Any]]) -> None:
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        key = canonical_key_for_row(row)
        row["canonical_trade_key"] = key
        row["canonical_group_size"] = None
        row["canonical_group_trade_ids"] = []
        if key:
            groups.setdefault(key, []).append(row)

    for group_rows in groups.values():
        trade_ids = [row["trade_id"] for row in group_rows]
        for row in group_rows:
            row["canonical_group_size"] = len(group_rows)
            row["canonical_group_trade_ids"] = trade_ids


def csv_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "trade_id": row["trade_id"],
        "related_transaction_id": row["related_transaction_id"],
        "season": row["season"],
        "week": row["week"],
        "score_start_week": row["score_start_week"],
        "score_end_week": row["score_end_week"],
        "trade_date_utc": row["trade_date_utc"],
        "grade_status": row["grade_status"],
        "ungraded_reason": row["ungraded_reason"],
        "canonical_group_size": row.get("canonical_group_size"),
        "canonical_group_trade_ids": "; ".join(row.get("canonical_group_trade_ids") or []),
        "team_a_id": row["team_a_id"],
        "team_a_name": row["team_a_name"],
        "team_a_points": row["team_a_points"],
        "team_a_grade": row["team_a_grade"],
        "team_a_players": player_names_for_csv(row.get("team_a_players") or []),
        "team_b_id": row["team_b_id"],
        "team_b_name": row["team_b_name"],
        "team_b_points": row["team_b_points"],
        "team_b_grade": row["team_b_grade"],
        "team_b_players": player_names_for_csv(row.get("team_b_players") or []),
        "net_difference": row["net_difference"],
        "winner_team_id": row["winner_team_id"],
        "winner_team_name": row["winner_team_name"],
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    csv_rows = [csv_row(row) for row in rows]
    fieldnames = [
        "trade_id",
        "related_transaction_id",
        "season",
        "week",
        "score_start_week",
        "score_end_week",
        "trade_date_utc",
        "grade_status",
        "ungraded_reason",
        "canonical_group_size",
        "canonical_group_trade_ids",
        "team_a_id",
        "team_a_name",
        "team_a_points",
        "team_a_grade",
        "team_a_players",
        "team_b_id",
        "team_b_name",
        "team_b_points",
        "team_b_grade",
        "team_b_players",
        "net_difference",
        "winner_team_id",
        "winner_team_name",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(csv_rows)


def sample_rows(rows: list[dict[str, Any]], sample_size: int) -> list[dict[str, Any]]:
    graded = [row for row in rows if row["grade_status"] == "graded"]
    sorted_rows = sorted(
        graded,
        key=lambda row: (abs(float(row["net_difference"])), row["season"], row["week"]),
        reverse=True,
    )
    sample: list[dict[str, Any]] = []
    seen_keys: set[str] = set()
    for row in sorted_rows:
        key = row.get("canonical_trade_key") or str(row["trade_id"])
        if key in seen_keys:
            continue
        seen_keys.add(key)
        sample.append(row)
        if len(sample) >= sample_size:
            break
    return sample


def compact_side(side_name: str, row: dict[str, Any]) -> str:
    players = row.get(f"{side_name}_players") or []
    player_text = ", ".join(
        f"{player['name']} {player['post_trade_points']:.1f}"
        for player in players
    )
    return (
        f"{row[f'{side_name}_name']} "
        f"({row[f'{side_name}_points']:.1f} pts, {row[f'{side_name}_grade']}) "
        f"got [{player_text}]"
    )


def print_sample(rows: list[dict[str, Any]], summary: dict[str, Any], sample_size: int) -> None:
    print(json.dumps(summary, indent=2, sort_keys=True))
    print("\nSample graded trades:")
    for row in sample_rows(rows, sample_size):
        side_a = compact_side("team_a", row)
        side_b = compact_side("team_b", row)
        print(
            f"- {row['season']} W{row['week']} | {side_a} vs {side_b} | "
            f"net {row['net_difference']:+.1f} | winner: {row['winner_team_name']}"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build completed-trade grade table from ESPN export data."
    )
    parser.add_argument(
        "--export-root",
        default="espn_exports/league_18254195",
        help="Path containing export_manifest.json, season_* data, and player_lookup.",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Defaults to <export-root>/trade_grades.",
    )
    parser.add_argument(
        "--include-trade-week",
        action="store_true",
        help="Count points from the trade scoring period itself instead of starting the next week.",
    )
    parser.add_argument("--sample-size", type=int, default=15)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    export_root = Path(args.export_root).resolve()
    if not (export_root / "export_manifest.json").exists():
        raise SystemExit(f"Missing export manifest under {export_root}")
    if not (export_root / "player_lookup" / "player_weekly_points.json").exists():
        raise SystemExit("Missing player lookup. Run build_player_lookup.py first.")

    output_dir = Path(args.output_dir).resolve() if args.output_dir else export_root / "trade_grades"
    rows, summary = build_trade_grade_rows(
        export_root=export_root,
        include_trade_week=args.include_trade_week,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(
        output_dir / "trade_grades.json",
        {
            "_meta": {
                "generated_at": summary["generated_at"],
                "description": "Completed TRADE_ACCEPT/EXECUTED trade grade table.",
            },
            "trades": rows,
        },
    )
    write_json(output_dir / "trade_grades_table.json", rows)
    write_json(output_dir / "trade_grades_summary.json", summary)
    write_json(output_dir / "trade_grades_sample.json", sample_rows(rows, args.sample_size))
    write_csv(output_dir / "trade_grades.csv", rows)
    print_sample(rows, summary, args.sample_size)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
