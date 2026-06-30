#!/usr/bin/env -S uv run --script

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any


def main() -> None:
    args = parse_args()
    source = args.source
    out = args.out
    source_league_id = source.name.removeprefix("league_")
    target_league_id = args.league_id
    if source_league_id == source.name or not source_league_id:
        raise SystemExit(f"source fixture must be named league_<id>: {source}")
    if not source.is_dir():
        raise SystemExit(f"source fixture not found: {source}")
    if source.resolve() == out.resolve():
        raise SystemExit("output fixture must differ from source")
    if out.exists():
        if not is_safe_replace_target(out):
            raise SystemExit(f"refusing to replace output outside evidence or tmp fixture path: {out}")
        shutil.rmtree(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, out)
    rewrite_json_files(out, source_league_id, target_league_id)
    print(
        json.dumps(
            {
                "source": str(source),
                "out": str(out),
                "sourceLeagueId": source_league_id,
                "targetLeagueId": target_league_id,
                "status": "PASS",
            },
            sort_keys=True,
        )
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a league-agnostic ESPN fixture copy.")
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--league-id", required=True)
    parser.add_argument("--out", required=True, type=Path)
    return parser.parse_args()


def is_safe_replace_target(path: Path) -> bool:
    resolved = path.resolve()
    parts = resolved.parts
    return ".omo" in parts and "evidence" in parts and path.name.startswith("league_")


def rewrite_json_files(root: Path, source_league_id: str, target_league_id: str) -> None:
    for path in sorted(root.rglob("*.json")):
        payload = json.loads(path.read_text())
        rewritten = rewrite_value(payload, source_league_id, target_league_id)
        path.write_text(json.dumps(rewritten, indent=2, sort_keys=True) + "\n")


def rewrite_value(value: Any, source_league_id: str, target_league_id: str) -> Any:
    if isinstance(value, dict):
        return {
            rewrite_string(str(key), source_league_id, target_league_id): rewrite_value(
                item, source_league_id, target_league_id
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [rewrite_value(item, source_league_id, target_league_id) for item in value]
    if isinstance(value, str):
        return rewrite_string(value, source_league_id, target_league_id)
    if isinstance(value, int) and value == int(source_league_id):
        return int(target_league_id)
    return value


def rewrite_string(value: str, source_league_id: str, target_league_id: str) -> str:
    return value.replace(source_league_id, target_league_id)


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:
        sys.exit(1)
