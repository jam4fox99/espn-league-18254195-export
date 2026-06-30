#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

from __future__ import annotations

import json
import os
import shutil
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Final, TypeAlias, TypedDict


EXPECTED_ZIP_ENTRIES: Final = 337
EXPECTED_ZIP_FILES: Final = 306
EXPECTED_SEASONS: Final = ("2020", "2021", "2022", "2023", "2024", "2025", "2026")
EXPECTED_TRANSACTION_PAYLOADS: Final = 118
EXPECTED_BOX_SCORE_PAYLOADS: Final = 118
EXPECTED_PLAYER_WEEK_ROWS: Final = 28_294
EXPECTED_WAIVER_ROWS: Final = 2_662
EXPECTED_FREEAGENT_ROWS: Final = 1_237
EXPECTED_EXECUTED_ACCEPTED_TRADES: Final = 95
EXPECTED_GRADED_ROWS: Final = 70
EXPECTED_CANONICAL_GRADED_EVENTS: Final = 51


class TransactionTypes(TypedDict, total=False):
    WAIVER: int
    FREEAGENT: int


class PlayerLookupSummary(TypedDict):
    weekly_point_rows: int


class TradeGradesSummary(TypedDict):
    completed_trade_accept_rows: int
    graded_rows: int
    canonical_graded_trade_groups: int


JsonValue: TypeAlias = type(None) | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]


@dataclass(frozen=True, slots=True)
class FixturePaths:
    zip_path: Path
    root: Path


class FixtureContractError(RuntimeError):
    def __init__(self, message: str) -> None:
        super().__init__(message)


def main() -> int:
    try:
        paths = parse_paths()
        ensure_fixture_root(paths)
        report = verify_fixture_contract(paths)
    except FixtureContractError as error:
        print(str(error), file=sys.stderr)
        return 1

    print(report)
    print("fixture verification: PASS")
    return 0


def parse_paths() -> FixturePaths:
    zip_value = os.environ.get("MYGM_FIXTURE_ZIP")
    root_value = os.environ.get("MYGM_FIXTURE_ROOT")
    return FixturePaths(
        zip_path=resolve_fixture_zip(zip_value),
        root=resolve_fixture_root(root_value),
    )


def resolve_fixture_zip(raw_path: str | None) -> Path:
    if raw_path:
        return Path(raw_path)
    matches = sorted(Path(".").glob("espn_league_*_export.zip"))
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise FixtureContractError("MYGM_FIXTURE_ZIP is required when no espn_league_*_export.zip file is present")
    raise FixtureContractError("MYGM_FIXTURE_ZIP is required when multiple espn_league_*_export.zip files are present")


def resolve_fixture_root(raw_path: str | None) -> Path:
    if raw_path:
        return Path(raw_path)
    fixture_parent = Path("tests/fixtures/espn")
    matches = sorted(path for path in fixture_parent.glob("league_*") if path.is_dir())
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise FixtureContractError("MYGM_FIXTURE_ROOT is required when no tests/fixtures/espn/league_* fixture is present")
    raise FixtureContractError("MYGM_FIXTURE_ROOT is required when multiple tests/fixtures/espn/league_* fixtures are present")


def ensure_fixture_root(paths: FixturePaths) -> None:
    if not paths.zip_path.exists():
        raise FixtureContractError(f"Missing ESPN fixture: {paths.zip_path}")
    if (paths.root / "export_manifest.json").exists():
        return

    source_prefix = detect_zip_source_prefix(paths.zip_path)
    paths.root.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(paths.zip_path) as fixture_zip:
        for member in fixture_zip.infolist():
            if member.is_dir() or not member.filename.startswith(source_prefix):
                continue
            relative_path = Path(member.filename.removeprefix(source_prefix))
            target = paths.root / relative_path
            target.parent.mkdir(parents=True, exist_ok=True)
            with fixture_zip.open(member) as source, target.open("wb") as destination:
                shutil.copyfileobj(source, destination)


def detect_zip_source_prefix(zip_path: Path) -> str:
    prefixes: set[str] = set()
    with zipfile.ZipFile(zip_path) as fixture_zip:
        for member in fixture_zip.infolist():
            if member.is_dir():
                continue
            parts = Path(member.filename).parts
            if len(parts) < 3 or parts[0] != "espn_exports" or not parts[1].startswith("league_"):
                continue
            prefixes.add(f"{parts[0]}/{parts[1]}/")
    if len(prefixes) == 1:
        return next(iter(prefixes))
    if not prefixes:
        raise FixtureContractError(f"No ESPN league export prefix found in {zip_path}")
    raise FixtureContractError(f"Multiple ESPN league export prefixes found in {zip_path}: {sorted(prefixes)}")


def verify_fixture_contract(paths: FixturePaths) -> str:
    zip_entries, zip_files = count_zip_entries(paths.zip_path)
    seasons = tuple(sorted(path.name.removeprefix("season_") for path in paths.root.glob("season_*") if path.is_dir()))
    transaction_payloads = len(list(paths.root.glob("season_*/transactions/period_*.json")))
    box_score_payloads = len(list(paths.root.glob("season_*/box_scores/week_*.json")))
    transaction_types = load_transaction_types(paths.root)
    lookup_summary = load_player_lookup_summary(paths.root / "player_lookup/lookup_summary.json")
    trade_summary = load_trade_grades_summary(paths.root / "trade_grades/trade_grades_summary.json")

    checks = {
        "zip entries": (zip_entries, EXPECTED_ZIP_ENTRIES),
        "zip files": (zip_files, EXPECTED_ZIP_FILES),
        "transaction-period payloads": (transaction_payloads, EXPECTED_TRANSACTION_PAYLOADS),
        "box-score payloads": (box_score_payloads, EXPECTED_BOX_SCORE_PAYLOADS),
        "player-week rows": (lookup_summary["weekly_point_rows"], EXPECTED_PLAYER_WEEK_ROWS),
        "WAIVER rows": (transaction_types.get("WAIVER", 0), EXPECTED_WAIVER_ROWS),
        "FREEAGENT rows": (transaction_types.get("FREEAGENT", 0), EXPECTED_FREEAGENT_ROWS),
        "executed accepted trade rows": (
            trade_summary["completed_trade_accept_rows"],
            EXPECTED_EXECUTED_ACCEPTED_TRADES,
        ),
        "graded rows": (trade_summary["graded_rows"], EXPECTED_GRADED_ROWS),
        "canonical graded trade events": (
            trade_summary["canonical_graded_trade_groups"],
            EXPECTED_CANONICAL_GRADED_EVENTS,
        ),
    }
    for label, values in checks.items():
        assert_expected(label, values[0], values[1])
    if seasons != EXPECTED_SEASONS:
        raise FixtureContractError(f"Expected seasons {EXPECTED_SEASONS}, found {seasons}")

    return "\n".join(
        (
            f"zip entries: {zip_entries}",
            f"zip non-directory files: {zip_files}",
            f"seasons: {', '.join(seasons)}",
            f"transaction-period payloads: {transaction_payloads}",
            f"box-score payloads: {box_score_payloads}",
            f"player-week rows: {lookup_summary['weekly_point_rows']}",
            f"WAIVER rows: {transaction_types.get('WAIVER', 0)}",
            f"FREEAGENT rows: {transaction_types.get('FREEAGENT', 0)}",
            f"executed accepted trade rows: {trade_summary['completed_trade_accept_rows']}",
            f"graded rows: {trade_summary['graded_rows']}",
            f"canonical graded trade events: {trade_summary['canonical_graded_trade_groups']}",
        )
    )


def count_zip_entries(zip_path: Path) -> tuple[int, int]:
    with zipfile.ZipFile(zip_path) as fixture_zip:
        entries = fixture_zip.infolist()
        files = sum(1 for entry in entries if not entry.is_dir())
        return len(entries), files


def load_transaction_types(root: Path) -> TransactionTypes:
    counts: TransactionTypes = {}
    for summary_path in root.glob("season_*/transactions/_types.json"):
        season_counts = load_transaction_type_summary(summary_path)
        counts["WAIVER"] = counts.get("WAIVER", 0) + season_counts.get("WAIVER", 0)
        counts["FREEAGENT"] = counts.get("FREEAGENT", 0) + season_counts.get("FREEAGENT", 0)
    return counts


def load_player_lookup_summary(path: Path) -> PlayerLookupSummary:
    document = load_json_document(path)
    match document:
        case {"weekly_point_rows": int() as weekly_point_rows}:
            return {"weekly_point_rows": weekly_point_rows}
        case _:
            raise FixtureContractError(f"Invalid player lookup summary shape: {path}")


def load_trade_grades_summary(path: Path) -> TradeGradesSummary:
    document = load_json_document(path)
    match document:
        case {
            "completed_trade_accept_rows": int() as completed_trade_accept_rows,
            "graded_rows": int() as graded_rows,
            "canonical_graded_trade_groups": int() as canonical_graded_trade_groups,
        }:
            return {
                "completed_trade_accept_rows": completed_trade_accept_rows,
                "graded_rows": graded_rows,
                "canonical_graded_trade_groups": canonical_graded_trade_groups,
            }
        case _:
            raise FixtureContractError(f"Invalid trade grades summary shape: {path}")


def load_transaction_type_summary(path: Path) -> TransactionTypes:
    document = load_json_document(path)
    match document:
        case {"WAIVER": int() as waiver, "FREEAGENT": int() as freeagent}:
            return {"WAIVER": waiver, "FREEAGENT": freeagent}
        case {"WAIVER": int() as waiver}:
            return {"WAIVER": waiver, "FREEAGENT": 0}
        case {"FREEAGENT": int() as freeagent}:
            return {"WAIVER": 0, "FREEAGENT": freeagent}
        case {}:
            return {"WAIVER": 0, "FREEAGENT": 0}
        case _:
            raise FixtureContractError(f"Invalid transaction type summary shape: {path}")


def load_json_document(path: Path) -> JsonValue:
    if not path.exists():
        raise FixtureContractError(f"Missing ESPN fixture file: {path}")
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def assert_expected(label: str, actual: int, expected: int) -> None:
    if actual != expected:
        raise FixtureContractError(f"Expected {label} {expected}, found {actual}")


if __name__ == "__main__":
    raise SystemExit(main())
