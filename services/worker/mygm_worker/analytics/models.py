from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal

type JsonValue = (
    None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]
)
type JsonObject = dict[str, JsonValue]
type Confidence = Literal["high", "medium", "low", "no_grade"]

SNAPSHOT_VERSION: Final = "espn-league-analytics-snapshot-v1"
SNAPSHOT_SOURCE: Final = "espn"


@dataclass(frozen=True, slots=True)
class SeasonMeta:
    season: int
    final_week: int
    transaction_count: int
    schedule_items: int
    is_partial: bool
    source_file: str


@dataclass(frozen=True, slots=True)
class ManagerIdentity:
    manager_key: str
    display_name: str
    owner_id: str
    is_unresolved: bool


@dataclass(frozen=True, slots=True)
class ManagerIdentitySummary:
    manager_count: int
    unresolved_owner_buckets: int
    team_season_count: int
    all_team_seasons_mapped: bool


@dataclass(frozen=True, slots=True)
class TeamSeason:
    season: int
    team_id: int
    team_name: str
    manager_key: str
    wins: int
    losses: int
    ties: int
    points_for: float
    points_against: float
    source_file: str


@dataclass(frozen=True, slots=True)
class TradeAnalytics:
    completed_trade_accept_rows: int
    graded_rows: int
    ungraded_rows: int
    canonical_graded_trade_events: int
    canonical_groups_with_multiple_rows: int
    item_sources: dict[str, int]
    ungraded_reasons: dict[str, int]


@dataclass(frozen=True, slots=True)
class AcquisitionAnalytics:
    total_rows: int
    counted_rows: int
    excluded_rows: int
    type_counts: dict[str, int]
    status_counts: dict[str, int]
    exclusion_reasons: dict[str, int]
    gross_rows: int
    net_rows: int
    faab_warning: str


@dataclass(frozen=True, slots=True)
class AllTimeRecords:
    seasons_counted: int
    total_wins: int
    total_losses: int
    total_ties: int
    highest_weekly_score: float
    lowest_weekly_score: float


@dataclass(frozen=True, slots=True)
class ManagerRating:
    manager_key: str
    season: int | None
    raw_components: dict[str, float]
    normalized_components: dict[str, float]
    weights: dict[str, float]
    final_score: float
    confidence: Confidence
    formula_version: str
    warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AnalyticsSummary:
    status: Literal["PASS"]
    formula_version: str
    seasons: tuple[SeasonMeta, ...]
    career_included_seasons: tuple[int, ...]
    career_excluded_seasons: tuple[int, ...]
    manager_identity: ManagerIdentitySummary
    records: AllTimeRecords
    trade_analytics: TradeAnalytics
    acquisition_analytics: AcquisitionAnalytics
    gm_ratings: tuple[ManagerRating, ...]
    data_quality_warnings: tuple[str, ...]
