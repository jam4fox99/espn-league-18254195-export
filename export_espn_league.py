#!/usr/bin/env python3
"""Export ESPN Fantasy Football league history to JSON files.

This intentionally uses ESPN's raw JSON endpoints instead of a wrapper library
so old-season behavior is visible and reproducible.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_ACTIVITY_MESSAGE_TYPES = [178, 180, 179, 239, 181, 244]
TRADE_TYPES = {
    "TRADE_ACCEPT",
    "TRADE_DECLINE",
    "TRADE_ERROR",
    "TRADE_PROPOSAL",
    "TRADE_UPHOLD",
    "TRADE_VETO",
}


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return

    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip()
        if (
            len(value) >= 2
            and value[0] == value[-1]
            and value[0] in {"'", '"'}
        ):
            value = value[1:-1]
        os.environ.setdefault(key, value)


def require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f"Missing required env var: {name}")
    return value


def repeated_query(params: list[tuple[str, str]]) -> str:
    return urllib.parse.urlencode(params)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp_path.replace(path)


class EspnExporter:
    def __init__(
        self,
        league_id: str,
        swid: str,
        espn_s2: str,
        out_dir: Path,
        delay_seconds: float = 0.15,
        retries: int = 3,
    ) -> None:
        self.league_id = league_id
        self.out_dir = out_dir
        self.delay_seconds = delay_seconds
        self.retries = retries
        self.cookie = f"espn_s2={espn_s2}; SWID={swid}; swid={swid}"

    def season_base(self, year: int) -> str:
        return (
            "https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/"
            f"seasons/{year}/segments/0/leagues/{self.league_id}"
        )

    def season_url(self, year: int, params: list[tuple[str, str]]) -> str:
        return f"{self.season_base(year)}?{repeated_query(params)}"

    def request_json(
        self,
        url: str,
        extra_headers: dict[str, str] | None = None,
    ) -> tuple[int | str, Any | None, str | None]:
        headers = {
            "Accept": "application/json,text/plain,*/*",
            "Cookie": self.cookie,
            "User-Agent": "Mozilla/5.0",
        }
        if extra_headers:
            headers.update(extra_headers)

        last_error: str | None = None
        for attempt in range(1, self.retries + 1):
            if self.delay_seconds:
                time.sleep(self.delay_seconds)
            request = urllib.request.Request(url, headers=headers)
            try:
                with urllib.request.urlopen(request, timeout=30) as response:
                    text = response.read().decode("utf-8", errors="replace")
                    return response.status, json.loads(text), None
            except urllib.error.HTTPError as exc:
                text = exc.read().decode("utf-8", errors="replace")
                last_error = text[:2000]
                if exc.code in {429, 500, 502, 503, 504} and attempt < self.retries:
                    time.sleep(1.5 * attempt)
                    continue
                return exc.code, None, last_error
            except Exception as exc:  # noqa: BLE001
                last_error = str(exc)
                if attempt < self.retries:
                    time.sleep(1.5 * attempt)
                    continue
                return "ERR", None, last_error

        return "ERR", None, last_error

    def write_response(
        self,
        path: Path,
        status: int | str,
        data: Any | None,
        error: str | None,
        url: str,
    ) -> None:
        payload: dict[str, Any] = {
            "_export_meta": {
                "status": status,
                "url": url,
                "exported_at": datetime.now(timezone.utc).isoformat(),
            }
        }
        if data is not None:
            payload["data"] = data
        if error is not None:
            payload["error"] = error
        write_json(path, payload)

    def export_core(self, year: int, season_dir: Path) -> tuple[dict[str, Any], Any | None]:
        params = [
            ("view", "mSettings"),
            ("view", "mTeam"),
            ("view", "mRoster"),
            ("view", "mStandings"),
            ("view", "mMatchup"),
            ("view", "mDraftDetail"),
        ]
        url = self.season_url(year, params)
        status, data, error = self.request_json(url)
        self.write_response(season_dir / "core.json", status, data, error, url)

        summary: dict[str, Any] = {
            "year": year,
            "core_status": status,
        }
        if status == 200 and isinstance(data, dict):
            settings = data.get("settings") or {}
            status_obj = data.get("status") or {}
            draft_detail = data.get("draftDetail") or {}
            summary.update(
                {
                    "league_name": settings.get("name"),
                    "teams": len(data.get("teams") or []),
                    "schedule_items": len(data.get("schedule") or []),
                    "first_scoring_period": status_obj.get("firstScoringPeriod"),
                    "final_scoring_period": status_obj.get("finalScoringPeriod"),
                    "previous_seasons": status_obj.get("previousSeasons") or [],
                    "draft_picks": len(draft_detail.get("picks") or []),
                }
            )
        else:
            summary["core_error"] = error
        return summary, data

    def export_box_scores(
        self,
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
            url = self.season_url(year, params)
            status, data, error = self.request_json(url, headers)
            self.write_response(box_dir / f"week_{period:02d}.json", status, data, error, url)

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
        self,
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
            url = self.season_url(year, params)
            status, data, error = self.request_json(url)
            self.write_response(tx_dir / f"period_{period:02d}.json", status, data, error, url)
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
            "periods_with_transactions": sum(
                1 for row in period_summaries if row["transactions"] > 0
            ),
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
        self,
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
            url = f"{self.season_base(year)}/communication/?{repeated_query(params)}"
            filters = {
                "topics": {
                    "filterType": {"value": ["ACTIVITY_TRANSACTIONS"]},
                    "limit": page_size,
                    "limitPerMessageSet": {"value": 25},
                    "offset": offset,
                    "sortMessageDate": {"sortPriority": 1, "sortAsc": False},
                    "sortFor": {"sortPriority": 2, "sortAsc": False},
                    "filterIncludeMessageTypeIds": {
                        "value": DEFAULT_ACTIVITY_MESSAGE_TYPES
                    },
                }
            }
            headers = {
                "x-fantasy-filter": json.dumps(filters, separators=(",", ":")),
            }
            status, data, error = self.request_json(url, headers)
            self.write_response(
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

    def export_year(
        self,
        year: int,
        include_activity: bool,
        activity_page_size: int,
        activity_max_items: int,
    ) -> dict[str, Any]:
        season_dir = self.out_dir / f"season_{year}"
        summary, core_data = self.export_core(year, season_dir)

        first_period = int(summary.get("first_scoring_period") or 1)
        final_period = int(summary.get("final_scoring_period") or 17)

        if summary["core_status"] == 200:
            summary.update(
                self.export_box_scores(year, season_dir, first_period, final_period)
            )
            summary.update(
                self.export_transactions(year, season_dir, first_period, final_period)
            )
            if include_activity:
                summary.update(
                    self.export_activity(
                        year,
                        season_dir,
                        activity_page_size,
                        activity_max_items,
                    )
                )
        elif core_data is None:
            summary.update(
                {
                    "box_score_requests": 0,
                    "box_score_successes": 0,
                    "transactions_total": 0,
                    "trade_transactions_total": 0,
                }
            )

        write_json(season_dir / "_season_summary.json", summary)
        return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export ESPN Fantasy Football league history JSON."
    )
    parser.add_argument("--env-file", default=".env", help="Path to .env file")
    parser.add_argument("--start-year", type=int, default=None)
    parser.add_argument("--end-year", type=int, default=None)
    parser.add_argument("--out-dir", default=None)
    parser.add_argument("--no-activity", action="store_true")
    parser.add_argument("--activity-page-size", type=int, default=100)
    parser.add_argument("--activity-max-items", type=int, default=1000)
    parser.add_argument("--delay", type=float, default=0.15)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    load_dotenv(Path(args.env_file))

    league_id = require_env("ESPN_LEAGUE_ID")
    swid = require_env("ESPN_SWID")
    espn_s2 = require_env("ESPN_S2")

    start_year = args.start_year or int(os.environ.get("ESPN_START_YEAR", "2020"))
    end_year = args.end_year or int(os.environ.get("ESPN_END_YEAR", "2026"))
    if start_year > end_year:
        raise SystemExit("--start-year must be <= --end-year")

    out_dir = Path(args.out_dir or f"espn_exports/league_{league_id}").resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    exporter = EspnExporter(
        league_id=league_id,
        swid=swid,
        espn_s2=espn_s2,
        out_dir=out_dir,
        delay_seconds=args.delay,
    )

    manifest: dict[str, Any] = {
        "league_id": league_id,
        "start_year": start_year,
        "end_year": end_year,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "output_dir": str(out_dir),
        "include_activity": not args.no_activity,
        "seasons": [],
    }

    for year in range(start_year, end_year + 1):
        print(f"Exporting {year}...", flush=True)
        summary = exporter.export_year(
            year=year,
            include_activity=not args.no_activity,
            activity_page_size=args.activity_page_size,
            activity_max_items=args.activity_max_items,
        )
        manifest["seasons"].append(summary)

    write_json(out_dir / "export_manifest.json", manifest)
    print(f"Done. Wrote export to: {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

