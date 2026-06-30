from __future__ import annotations

# pyright: reportAny=false, reportArgumentType=false, reportAttributeAccessIssue=false, reportCallIssue=false, reportExplicitAny=false, reportImplicitStringConcatenation=false, reportImportCycles=false, reportOperatorIssue=false, reportUnannotatedClassAttribute=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnnecessaryIsInstance=false, reportUnusedCallResult=false
from collections import Counter
from pathlib import Path
from typing import Any

from mygm_worker.espn.trade_common import GRADE_THRESHOLDS, now_iso
from mygm_worker.espn.trade_loaders import iter_transactions
from mygm_worker.espn.trade_reconstruct import reconstruct_trade_rows


def build_trade_grade_rows(
    export_root: Path,
    include_trade_week: bool,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    # Executed trades are reconstructed from actual box-score roster movement rather than
    # ESPN's transaction status, which is unreliable for this league: completed trades are
    # frequently marked PENDING/CANCELED and their item payloads are dropped (especially in
    # 2024/2025). See trade_reconstruct.reconstruct_trade_rows for the full rationale.
    rows = reconstruct_trade_rows(export_root, include_trade_week)
    transactions = iter_transactions(export_root)
    return rows, summarize_rows(rows, transactions, include_trade_week)


def summarize_rows(
    rows: list[dict[str, Any]],
    transactions: list[dict[str, Any]],
    include_trade_week: bool,
) -> dict[str, Any]:
    status_counts = Counter(row["grade_status"] for row in rows)
    ungraded_reasons = Counter(row["ungraded_reason"] for row in rows if row.get("ungraded_reason"))
    trade_item_sources = Counter(row["trade_item_source"] for row in rows)
    trade_accept_status_counts = Counter(
        tx.get("status") or "UNKNOWN"
        for tx in transactions
        if tx.get("type") == "TRADE_ACCEPT"
    )
    return {
        "generated_at": now_iso(),
        "filter": {
            "trade_source": "box_score_roster_movement",
            "include_trade_week": include_trade_week,
            "score_rule": (
                "sum player weekly points from trade week through season end"
                if include_trade_week
                else (
                    "sum player weekly points from the week after the trade week "
                    "through season end"
                )
            ),
        },
        "trade_accept_status_counts": dict(trade_accept_status_counts),
        "completed_trade_accept_rows": len(rows),
        "graded_rows": status_counts.get("graded", 0),
        "ungraded_rows": len(rows) - status_counts.get("graded", 0),
        "trade_item_sources": dict(trade_item_sources),
        "canonical_graded_trade_groups": canonical_group_count(rows),
        "canonical_groups_with_multiple_rows": canonical_multirow_group_count(rows),
        "ungraded_reasons": dict(ungraded_reasons),
        "by_season": summarize_by_season(rows),
        "grade_thresholds": [
            {"net_points_greater_than": threshold, "grade": grade}
            for threshold, grade in GRADE_THRESHOLDS
        ]
        + [{"net_points_less_or_equal_to": -40, "grade": "F"}],
    }


def summarize_by_season(rows: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    by_season: dict[str, dict[str, int]] = {}
    for row in rows:
        season = str(row["season"])
        by_season.setdefault(season, {"total": 0, "graded": 0, "ungraded": 0})
        by_season[season]["total"] += 1
        if row["grade_status"] == "graded":
            by_season[season]["graded"] += 1
        else:
            by_season[season]["ungraded"] += 1
    return by_season


def canonical_group_count(rows: list[dict[str, Any]]) -> int:
    return len({row["canonical_trade_key"] for row in rows if row.get("canonical_trade_key")})


def canonical_multirow_group_count(rows: list[dict[str, Any]]) -> int:
    return len(
        {
            row["canonical_trade_key"]
            for row in rows
            if row.get("canonical_trade_key") and row.get("canonical_group_size", 1) > 1
        }
    )
