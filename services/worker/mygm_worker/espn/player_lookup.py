from __future__ import annotations

# pyright: reportAny=false, reportArgumentType=false, reportAttributeAccessIssue=false, reportCallIssue=false, reportExplicitAny=false, reportImplicitStringConcatenation=false, reportImportCycles=false, reportOperatorIssue=false, reportUnannotatedClassAttribute=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnnecessaryIsInstance=false, reportUnusedCallResult=false
import argparse
import json
from pathlib import Path
from typing import Any

from mygm_worker.espn.lookup_common import read_json
from mygm_worker.espn.lookup_enrich import enrich_from_player_cards
from mygm_worker.espn.lookup_extract import extract_box_scores, extract_trade_contexts
from mygm_worker.espn.lookup_outputs import build_trade_coverage, write_lookup_outputs
from mygm_worker.fixtures import require_espn_export_root

__all__ = [
    "build_trade_coverage",
    "extract_box_scores",
    "extract_trade_contexts",
    "read_json",
    "write_lookup_outputs",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build playerId -> weekly points lookup from ESPN export JSON."
    )
    parser.add_argument(
        "--export-root",
        default=None,
        help="Path containing export_manifest.json and season_* directories.",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Defaults to <export-root>/player_lookup.",
    )
    parser.add_argument("--env-file", default=".env")
    parser.add_argument(
        "--no-enrich",
        action="store_true",
        help="Skip ESPN player-card enrichment and use box score data only.",
    )
    parser.add_argument("--batch-size", type=int, default=50)
    parser.add_argument("--delay", type=float, default=0.15)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    requested_export_root = Path(args.export_root).expanduser() if args.export_root else None
    try:
        export_root = require_espn_export_root(requested_export_root)
    except FileNotFoundError as exc:
        raise SystemExit(str(exc)) from exc

    output_dir = (
        Path(args.output_dir).resolve()
        if args.output_dir
        else export_root / "player_lookup"
    )
    players: dict[str, dict[str, Any]] = {}
    extraction_summary = {
        "box_scores": extract_box_scores(export_root, players),
        "trades": extract_trade_contexts(export_root, players),
    }
    if args.no_enrich:
        enrichment_summary = {"enabled": False, "reason": "--no-enrich"}
    else:
        enrichment_summary = enrich_from_player_cards(
            players=players,
            export_root=export_root,
            env_file=Path(args.env_file),
            batch_size=args.batch_size,
            delay=args.delay,
        )

    summary = write_lookup_outputs(output_dir, players, extraction_summary, enrichment_summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
