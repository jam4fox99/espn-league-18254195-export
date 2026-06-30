from __future__ import annotations

# pyright: reportAny=false, reportArgumentType=false, reportAttributeAccessIssue=false, reportCallIssue=false, reportExplicitAny=false, reportImplicitStringConcatenation=false, reportImportCycles=false, reportOperatorIssue=false, reportUnannotatedClassAttribute=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnnecessaryIsInstance=false, reportUnusedCallResult=false
import csv
import json
from pathlib import Path
from typing import Any

from mygm_worker.espn.export_common import write_json


def player_names_for_csv(players: list[dict[str, Any]]) -> str:
    return "; ".join(
        f"{player['name']} ({player['post_trade_points']:.2f})" for player in players
    )


def csv_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "trade_id": row["trade_id"],
        "related_transaction_id": row["related_transaction_id"],
        "season": row["season"],
        "week": row["week"],
        "score_start_week": row["score_start_week"],
        "score_end_week": row["score_end_week"],
        "trade_date_utc": row["trade_date_utc"],
        "raw_item_count": row["raw_item_count"],
        "trade_item_count": row["trade_item_count"],
        "receiving_team_count": row["receiving_team_count"],
        "trade_item_source": row["trade_item_source"],
        "trade_item_source_transaction_id": row["trade_item_source_transaction_id"],
        "trade_item_source_type": row["trade_item_source_type"],
        "trade_item_source_status": row["trade_item_source_status"],
        "trade_item_source_raw_item_count": row["trade_item_source_raw_item_count"],
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
    fieldnames = list(csv_rows[0].keys()) if csv_rows else list(csv_row(empty_csv_source()).keys())
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(csv_rows)


def empty_csv_source() -> dict[str, Any]:
    return {
        "trade_id": None,
        "related_transaction_id": None,
        "season": None,
        "week": None,
        "score_start_week": None,
        "score_end_week": None,
        "trade_date_utc": None,
        "raw_item_count": None,
        "trade_item_count": None,
        "receiving_team_count": None,
        "trade_item_source": None,
        "trade_item_source_transaction_id": None,
        "trade_item_source_type": None,
        "trade_item_source_status": None,
        "trade_item_source_raw_item_count": None,
        "grade_status": None,
        "ungraded_reason": None,
        "canonical_group_size": None,
        "canonical_group_trade_ids": [],
        "team_a_id": None,
        "team_a_name": None,
        "team_a_points": None,
        "team_a_grade": None,
        "team_a_players": [],
        "team_b_id": None,
        "team_b_name": None,
        "team_b_points": None,
        "team_b_grade": None,
        "team_b_players": [],
        "net_difference": None,
        "winner_team_id": None,
        "winner_team_name": None,
    }


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
        f"{player['name']} {player['post_trade_points']:.1f}" for player in players
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


def write_trade_outputs(
    output_dir: Path,
    rows: list[dict[str, Any]],
    summary: dict[str, Any],
    sample_size: int,
) -> None:
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
    write_json(output_dir / "trade_grades_sample.json", sample_rows(rows, sample_size))
    write_csv(output_dir / "trade_grades.csv", rows)
