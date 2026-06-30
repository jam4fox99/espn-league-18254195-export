from __future__ import annotations

# pyright: reportAny=false, reportArgumentType=false, reportAttributeAccessIssue=false, reportCallIssue=false, reportExplicitAny=false, reportImplicitStringConcatenation=false, reportImportCycles=false, reportOperatorIssue=false, reportUnannotatedClassAttribute=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnnecessaryIsInstance=false, reportUnusedCallResult=false
import json
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from mygm_worker.espn.export_common import repeated_query, write_json
from mygm_worker.espn.export_sections import (
    export_activity,
    export_box_scores,
    export_transactions,
)


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
            except (
                json.JSONDecodeError,
                OSError,
                TimeoutError,
                urllib.error.URLError,
            ) as exc:
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
                "exported_at": datetime.now(UTC).isoformat(),
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

        summary: dict[str, Any] = {"year": year, "core_status": status}
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
            summary.update(export_box_scores(self, year, season_dir, first_period, final_period))
            summary.update(export_transactions(self, year, season_dir, first_period, final_period))
            if include_activity:
                summary.update(
                    export_activity(self, year, season_dir, activity_page_size, activity_max_items)
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
