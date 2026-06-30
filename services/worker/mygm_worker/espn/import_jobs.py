from __future__ import annotations

# pyright: reportAny=false, reportUnknownArgumentType=false, reportUnknownVariableType=false
import json
from dataclasses import dataclass
from pathlib import Path
from typing import NewType

from mygm_worker.fixtures import require_espn_export_root

LeagueId = NewType("LeagueId", str)
OrgId = NewType("OrgId", str)
ImportRunId = NewType("ImportRunId", str)
TransformVersion = NewType("TransformVersion", str)
type JsonValue = None | bool | int | float | str | list[JsonValue] | dict[str, JsonValue]
type JsonObject = dict[str, JsonValue]


@dataclass(frozen=True, slots=True)
class EspnImportRequest:
    league_id: LeagueId
    export_root: Path | None = None


@dataclass(frozen=True, slots=True)
class SeasonImportSummary:
    season: int
    teams: int
    final_scoring_period: int
    box_score_player_entries: int
    transactions_total: int
    trade_transactions_total: int


@dataclass(frozen=True, slots=True)
class EspnImportSummary:
    league_id: LeagueId
    start_year: int
    end_year: int
    seasons: tuple[SeasonImportSummary, ...]
    players_total: int
    weekly_point_rows: int
    completed_trade_accept_rows: int
    graded_trade_rows: int
    canonical_graded_trade_groups: int


@dataclass(frozen=True, slots=True)
class ImportStorageRequest:
    org_id: OrgId
    league_id: LeagueId
    import_run_id: ImportRunId
    transform_version: TransformVersion


@dataclass(frozen=True, slots=True)
class ImportStoragePaths:
    raw_import_prefix: str
    derived_artifact_prefix: str


def read_json(path: Path) -> JsonObject:
    data = parse_json_value(json.loads(path.read_text(encoding="utf-8")))
    match data:
        case dict():
            return data
        case _:
            message = f"Expected JSON object at {path}"
            raise TypeError(message)


def parse_json_value(value: object) -> JsonValue:
    match value:
        case None | bool() | int() | float() | str():
            return value
        case list():
            return [parse_json_value(item) for item in value]
        case dict():
            return {
                key: parse_json_value(item)
                for key, item in value.items()
                if isinstance(key, str)
            }
        case _:
            message = f"Unexpected JSON value: {type(value).__name__}"
            raise TypeError(message)


def season_rows(value: JsonValue | None) -> list[JsonObject]:
    if not isinstance(value, list):
        message = "Expected seasons list in export manifest"
        raise TypeError(message)
    return [row for row in value if isinstance(row, dict)]


def int_field(data: JsonObject, name: str) -> int:
    value = data.get(name)
    if isinstance(value, int):
        return value
    message = f"Expected integer field {name}"
    raise TypeError(message)


def str_field(data: JsonObject, name: str) -> str:
    value = data.get(name)
    if isinstance(value, str):
        return value
    message = f"Expected string field {name}"
    raise TypeError(message)


def season_summary(data: JsonObject) -> SeasonImportSummary:
    return SeasonImportSummary(
        season=int_field(data, "year"),
        teams=int_field(data, "teams"),
        final_scoring_period=int_field(data, "final_scoring_period"),
        box_score_player_entries=int_field(data, "box_score_player_entries"),
        transactions_total=int_field(data, "transactions_total"),
        trade_transactions_total=int_field(data, "trade_transactions_total"),
    )


def summarize_export(request: EspnImportRequest) -> EspnImportSummary:
    export_root = require_espn_export_root(request.export_root)
    manifest = read_json(export_root / "export_manifest.json")
    lookup = read_json(export_root / "player_lookup" / "lookup_summary.json")
    trade_grades = read_json(export_root / "trade_grades" / "trade_grades_summary.json")
    seasons = [season_summary(row) for row in season_rows(manifest.get("seasons"))]

    return EspnImportSummary(
        league_id=LeagueId(str_field(manifest, "league_id")),
        start_year=int_field(manifest, "start_year"),
        end_year=int_field(manifest, "end_year"),
        seasons=tuple(seasons),
        players_total=int_field(lookup, "players_total"),
        weekly_point_rows=int_field(lookup, "weekly_point_rows"),
        completed_trade_accept_rows=int_field(trade_grades, "completed_trade_accept_rows"),
        graded_trade_rows=int_field(trade_grades, "graded_rows"),
        canonical_graded_trade_groups=int_field(trade_grades, "canonical_graded_trade_groups"),
    )


def import_storage_paths(request: ImportStorageRequest) -> ImportStoragePaths:
    return ImportStoragePaths(
        raw_import_prefix=(
            f"org/{request.org_id}/league/{request.league_id}/"
            f"import/{request.import_run_id}/"
        ),
        derived_artifact_prefix=(
            f"league/{request.league_id}/source_import/{request.import_run_id}/"
            f"transform/{request.transform_version}/"
        ),
    )
