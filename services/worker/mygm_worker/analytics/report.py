from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from mygm_worker.analytics.identity import load_team_seasons, manager_summary
from mygm_worker.analytics.models import AcquisitionAnalytics, AnalyticsSummary, TradeAnalytics
from mygm_worker.analytics.ratings import FORMULA_VERSION, gm_ratings, rating_warnings
from mygm_worker.analytics.reader import FixtureReader
from mygm_worker.analytics.records import records
from mygm_worker.analytics.transactions import acquisition_analytics, trade_analytics


class PartialSeasonIncludedError(ValueError):
    def __init__(self, season: int) -> None:
        super().__init__(
            f"partial season cannot be included without explicit override: {season}"
        )


def analyze_fixture(
    fixture_root: Path,
    *,
    include_partial_career: bool = False,
    strict: bool = False,
) -> AnalyticsSummary:
    reader = FixtureReader(fixture_root)
    reader.require()
    seasons = reader.seasons()
    partial_seasons = tuple(season.season for season in seasons if season.is_partial)
    if include_partial_career and strict and partial_seasons:
        raise PartialSeasonIncludedError(partial_seasons[0])

    included_seasons = tuple(
        season.season
        for season in seasons
        if include_partial_career or not season.is_partial
    )
    managers, team_seasons = load_team_seasons(reader)
    trades = trade_analytics(reader)
    acquisitions = acquisition_analytics(reader)
    warning_rows = _warnings(partial_seasons, trades, acquisitions)

    return AnalyticsSummary(
        status="PASS",
        formula_version=FORMULA_VERSION,
        seasons=seasons,
        career_included_seasons=included_seasons,
        career_excluded_seasons=partial_seasons if not include_partial_career else (),
        manager_identity=manager_summary(managers, team_seasons),
        records=records(reader, team_seasons, included_seasons),
        trade_analytics=trades,
        acquisition_analytics=acquisitions,
        gm_ratings=gm_ratings(
            team_seasons=team_seasons,
            included_seasons=included_seasons,
            trade_summary=trades,
            acquisition_summary=acquisitions,
        ),
        data_quality_warnings=warning_rows,
    )


def write_summary(
    fixture_root: Path,
    output_dir: Path,
    *,
    include_partial_career: bool = False,
    strict: bool = False,
) -> Path:
    summary = analyze_fixture(
        fixture_root,
        include_partial_career=include_partial_career,
        strict=strict,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "summary.json"
    _ = path.write_text(summary_to_json(summary), encoding="utf-8")
    return path


def summary_to_json(summary: AnalyticsSummary) -> str:
    return json.dumps(asdict(summary), indent=2, sort_keys=True) + "\n"


def _warnings(
    partial_seasons: tuple[int, ...],
    trades: TradeAnalytics,
    acquisitions: AcquisitionAnalytics,
) -> tuple[str, ...]:
    warnings = list(rating_warnings(trades, acquisitions))
    warnings.extend(
        f"{season} excluded from career ratings by default" for season in partial_seasons
    )
    return tuple(warnings)
