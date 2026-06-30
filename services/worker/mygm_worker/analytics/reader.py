from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from mygm_worker.analytics.json_tools import (
    as_object,
    int_value,
    object_field,
    read_json,
)
from mygm_worker.analytics.models import JsonObject, JsonValue, SeasonMeta


class FixtureReader:
    def __init__(self, fixture_root: Path) -> None:
        self.root: Path = fixture_root
        # Parsing the large export JSON with the in-repo parser is expensive; several
        # analytics passes read the same core/player files repeatedly, so memoize them.
        self._core_cache: dict[int, JsonObject] = {}
        self._player_lookup_cache: JsonObject | None = None

    def require(self) -> None:
        if not self.root.exists():
            raise FileNotFoundError(f"Missing ESPN fixture root: {self.root}")
        if not (self.root / "export_manifest.json").exists():
            raise FileNotFoundError(f"Missing ESPN fixture manifest: {self.root}")

    def season_dirs(self) -> list[Path]:
        return sorted(path for path in self.root.glob("season_*") if path.is_dir())

    def seasons(self) -> tuple[SeasonMeta, ...]:
        seasons: list[SeasonMeta] = []
        for season_dir in self.season_dirs():
            season = int(season_dir.name.split("_", 1)[1])
            summary_path = season_dir / "_season_summary.json"
            summary = as_object(read_json(summary_path), str(summary_path))
            transaction_count = int_value(summary.get("transactions_total"))
            schedule_items = int_value(summary.get("schedule_items"))
            seasons.append(
                SeasonMeta(
                    season=season,
                    final_week=int_value(summary.get("final_scoring_period"), 17),
                    transaction_count=transaction_count,
                    schedule_items=schedule_items,
                    is_partial=season >= 2026 or transaction_count == 0,
                    source_file=str(summary_path),
                )
            )
        return tuple(seasons)

    def core(self, season: int) -> JsonObject:
        cached = self._core_cache.get(season)
        if cached is not None:
            return cached
        payload = as_object(read_json(self.root / f"season_{season}" / "core.json"), "core")
        data = object_field(payload, "data")
        self._core_cache[season] = data
        return data

    def transaction_rows(self) -> Iterator[JsonObject]:
        for season_dir in self.season_dirs():
            season = int(season_dir.name.split("_", 1)[1])
            for period_path in sorted((season_dir / "transactions").glob("period_*.json")):
                payload = as_object(read_json(period_path), str(period_path))
                data = object_field(payload, "data")
                transactions = data.get("transactions")
                if not isinstance(transactions, list):
                    continue
                for index, item in enumerate(transactions):
                    if isinstance(item, dict):
                        row = dict(item)
                        row["_season"] = season
                        row["_source_file"] = str(period_path)
                        row["_source_index"] = index
                        yield row

    def weekly_scores(self) -> Iterator[tuple[int, int, int, float]]:
        for season_dir in self.season_dirs():
            season = int(season_dir.name.split("_", 1)[1])
            for week_path in sorted((season_dir / "box_scores").glob("week_*.json")):
                payload = as_object(read_json(week_path), str(week_path))
                data = object_field(payload, "data")
                schedules = data.get("schedule")
                if not isinstance(schedules, list):
                    continue
                for matchup in schedules:
                    if isinstance(matchup, dict):
                        week = int_value(matchup.get("matchupPeriodId"))
                        yield from _matchup_scores(season, week, matchup)

    def trade_grade_summary(self) -> JsonObject:
        return as_object(
            read_json(self.root / "trade_grades" / "trade_grades_summary.json"),
            "trade_grades_summary",
        )

    def trade_grade_rows(self) -> list[JsonObject]:
        value = read_json(self.root / "trade_grades" / "trade_grades_table.json")
        if isinstance(value, list):
            return [dict(row) for row in value if isinstance(row, dict)]
        return []

    def player_lookup(self) -> JsonObject:
        if self._player_lookup_cache is not None:
            return self._player_lookup_cache
        payload = as_object(
            read_json(self.root / "player_lookup" / "player_weekly_points.json"),
            "player_weekly_points",
        )
        players = payload.get("players")
        resolved = players if isinstance(players, dict) else {}
        self._player_lookup_cache = resolved
        return resolved


def _matchup_scores(
    season: int,
    week: int,
    matchup: JsonObject,
) -> Iterator[tuple[int, int, int, float]]:
    for side_name in ("home", "away"):
        side = matchup.get(side_name)
        if isinstance(side, dict):
            team_id = int_value(side.get("teamId"))
            total_points = _numeric_value(side.get("totalPoints"))
            if team_id != 0 and total_points is not None:
                yield season, week, team_id, total_points


def _numeric_value(value: JsonValue) -> float | None:
    match value:
        case bool():
            return None
        case int() | float():
            return float(value)
        case None | str() | list() | dict():
            return None
