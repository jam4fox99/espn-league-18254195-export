from __future__ import annotations

# pyright: reportAny=false, reportArgumentType=false, reportAttributeAccessIssue=false, reportCallIssue=false, reportExplicitAny=false, reportImplicitStringConcatenation=false, reportImportCycles=false, reportOperatorIssue=false, reportUnannotatedClassAttribute=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnnecessaryIsInstance=false, reportUnusedCallResult=false
import argparse
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from mygm_worker.espn.export_client import EspnExporter
from mygm_worker.espn.export_common import load_dotenv, require_env, write_json


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
        message = "--start-year must be <= --end-year"
        raise SystemExit(message)

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
        "exported_at": datetime.now(UTC).isoformat(),
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
