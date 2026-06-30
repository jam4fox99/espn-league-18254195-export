from __future__ import annotations

# pyright: reportAny=false, reportArgumentType=false, reportAttributeAccessIssue=false, reportCallIssue=false, reportExplicitAny=false, reportImplicitStringConcatenation=false, reportImportCycles=false, reportOperatorIssue=false, reportUnannotatedClassAttribute=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnnecessaryIsInstance=false, reportUnusedCallResult=false
import argparse
from pathlib import Path

from mygm_worker.espn.trade_outputs import print_sample, write_trade_outputs
from mygm_worker.espn.trade_summary import build_trade_grade_rows
from mygm_worker.fixtures import require_espn_export_root

__all__ = ["build_trade_grade_rows"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build completed-trade grade table from ESPN export data."
    )
    parser.add_argument(
        "--export-root",
        default=None,
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
    requested_export_root = Path(args.export_root).expanduser() if args.export_root else None
    try:
        export_root = require_espn_export_root(requested_export_root)
    except FileNotFoundError as exc:
        raise SystemExit(str(exc)) from exc
    if not (export_root / "player_lookup" / "player_weekly_points.json").exists():
        message = "Missing player lookup. Run build_player_lookup.py first."
        raise SystemExit(message)

    output_dir = (
        Path(args.output_dir).resolve()
        if args.output_dir
        else export_root / "trade_grades"
    )
    rows, summary = build_trade_grade_rows(export_root, args.include_trade_week)
    write_trade_outputs(output_dir, rows, summary, args.sample_size)
    print_sample(rows, summary, args.sample_size)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
