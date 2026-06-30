from __future__ import annotations

# pyright: reportAny=false, reportArgumentType=false, reportAttributeAccessIssue=false, reportCallIssue=false, reportExplicitAny=false, reportImplicitStringConcatenation=false, reportImportCycles=false, reportOperatorIssue=false, reportUnannotatedClassAttribute=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnnecessaryIsInstance=false, reportUnusedCallResult=false
import json
from collections import Counter
from pathlib import Path
from typing import TYPE_CHECKING, Any

from mygm_worker.espn.export_common import repeated_query, write_json

if TYPE_CHECKING:
    from mygm_worker.espn.export_client import EspnExporter

DEFAULT_ACTIVITY_MESSAGE_TYPES = [178, 180, 179, 239, 181, 244]
TRADE_TYPES = {
    "TRADE_ACCEPT",
    "TRADE_DECLINE",
    "TRADE_ERROR",
    "TRADE_PROPOSAL",
    "TRADE_UPHOLD",
    "TRADE_VETO",
}


def export_box_scores(
    exporter: EspnExporter,
    year: int,
    season_dir: Path,
    first_period: int,
    final_period: int,
) -> dict[str, Any]:
    box_dir = season_dir / "box_scores"
    period_summaries: list[dict[str, Any]] = []

    for period in range(first_period, final_period + 1):
        params = [
            ("view", "mMatchupScore"),
            ("view", "mScoreboard"),
            ("scoringPeriodId", str(period)),
        ]
        headers = {
            "x-fantasy-filter": json.dumps(
                {"schedule": {"filterMatchupPeriodIds": {"value": [period]}}},
                separators=(",", ":"),
            )
        }
        url = exporter.season_url(year, params)
        status, data, error = exporter.request_json(url, headers)
        exporter.write_response(box_dir / f"week_{period:02d}.json", status, data, error, url)

        matchups = 0
        player_entries = 0
        if status == 200 and isinstance(data, dict):
            schedule = data.get("schedule") or []
            matchups = len(schedule)
            for matchup in schedule:
                for side in ("home", "away"):
                    team_data = matchup.get(side) or {}
                    roster = team_data.get("rosterForCurrentScoringPeriod") or {}
                    player_entries += len(roster.get("entries") or [])

        period_summaries.append(
            {
                "period": period,
                "status": status,
                "matchups": matchups,
                "player_entries": player_entries,
            }
        )

    write_json(box_dir / "_summary.json", period_summaries)
    return {
        "box_score_requests": len(period_summaries),
        "box_score_successes": sum(1 for row in period_summaries if row["status"] == 200),
        "box_score_player_entries": sum(row["player_entries"] for row in period_summaries),
    }


def export_transactions(
    exporter: EspnExporter,
    year: int,
    season_dir: Path,
    first_period: int,
    final_period: int,
) -> dict[str, Any]:
    tx_dir = season_dir / "transactions"
    period_summaries: list[dict[str, Any]] = []
    all_trade_transactions: list[dict[str, Any]] = []
    type_counts: Counter[str] = Counter()
    status_counts: Counter[str] = Counter()
    request_status_counts: Counter[str] = Counter()

    for period in range(first_period, final_period + 1):
        params = [("view", "mTransactions2"), ("scoringPeriodId", str(period))]
        url = exporter.season_url(year, params)
        status, data, error = exporter.request_json(url)
        exporter.write_response(tx_dir / f"period_{period:02d}.json", status, data, error, url)
        request_status_counts[str(status)] += 1

        transactions = []
        if status == 200 and isinstance(data, dict):
            transactions = data.get("transactions") or []

        for tx in transactions:
            tx_type = tx.get("type") or "UNKNOWN"
            tx_status = tx.get("status") or "UNKNOWN"
            type_counts[tx_type] += 1
            status_counts[tx_status] += 1
            if tx_type in TRADE_TYPES:
                all_trade_transactions.append(
                    {
                        "scoringPeriodId": period,
                        "type": tx_type,
                        "status": tx_status,
                        "date": tx.get("processDate") or tx.get("proposedDate"),
                        "teamId": tx.get("teamId"),
                        "items": tx.get("items") or [],
                    }
                )

        period_summaries.append(
            {
                "period": period,
                "status": status,
                "transactions": len(transactions),
                "error": error if status != 200 else None,
            }
        )

    summary = {
        "request_status_counts": dict(request_status_counts),
        "periods_with_transactions": sum(1 for row in period_summaries if row["transactions"] > 0),
        "transactions_total": sum(row["transactions"] for row in period_summaries),
        "transaction_type_counts": dict(type_counts),
        "transaction_status_counts": dict(status_counts),
        "trade_transactions_total": len(all_trade_transactions),
    }
    write_json(tx_dir / "_summary.json", period_summaries)
    write_json(tx_dir / "_types.json", dict(type_counts))
    write_json(tx_dir / "_trades.json", all_trade_transactions)
    return summary


def export_activity(
    exporter: EspnExporter,
    year: int,
    season_dir: Path,
    page_size: int,
    max_items: int,
) -> dict[str, Any]:
    activity_dir = season_dir / "activity"
    topics_total = 0
    pages: list[dict[str, Any]] = []

    for offset in range(0, max_items, page_size):
        params = [("view", "kona_league_communication")]
        url = f"{exporter.season_base(year)}/communication/?{repeated_query(params)}"
        filters = {
            "topics": {
                "filterType": {"value": ["ACTIVITY_TRANSACTIONS"]},
                "limit": page_size,
                "limitPerMessageSet": {"value": 25},
                "offset": offset,
                "sortMessageDate": {"sortPriority": 1, "sortAsc": False},
                "sortFor": {"sortPriority": 2, "sortAsc": False},
                "filterIncludeMessageTypeIds": {"value": DEFAULT_ACTIVITY_MESSAGE_TYPES},
            }
        }
        headers = {"x-fantasy-filter": json.dumps(filters, separators=(",", ":"))}
        status, data, error = exporter.request_json(url, headers)
        exporter.write_response(
            activity_dir / f"offset_{offset:04d}.json",
            status,
            data,
            error,
            url,
        )

        topics = []
        if status == 200 and isinstance(data, dict):
            topics = data.get("topics") or []
            topics_total += len(topics)

        pages.append(
            {
                "offset": offset,
                "status": status,
                "topics": len(topics),
                "error": error if status != 200 else None,
            }
        )

        if status != 200 or not topics:
            break

    write_json(activity_dir / "_summary.json", pages)
    return {
        "activity_pages": len(pages),
        "activity_topics_total": topics_total,
        "activity_statuses": dict(Counter(str(row["status"]) for row in pages)),
    }
