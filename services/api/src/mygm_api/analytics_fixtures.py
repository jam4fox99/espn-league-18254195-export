from dataclasses import dataclass
from typing import Final

from mygm_api.score_models import (
    ACQUISITION_SCORE_MODEL,
    CAREER_GM_SCORE_MODEL,
    DATA_HEALTH_MODEL,
    RECORDS_MODEL,
    SEASON_GM_SCORE_MODEL,
    TRADE_SCORE_MODEL,
)


@dataclass(frozen=True, slots=True)
class AnalyticsFixture:
    seasons: tuple[int, ...]
    player_week_rows: int
    waiver_rows: int
    free_agent_rows: int
    executed_accepted_trades: int
    graded_trade_rows: int
    canonical_trade_events: int
    box_score_payloads: int
    transaction_period_payloads: int
    zip_entries: int
    non_directory_files: int

    @property
    def source_counts(self) -> dict[str, int]:
        return {
            "seasons": len(self.seasons),
            "playerWeekRows": self.player_week_rows,
            "waiverRows": self.waiver_rows,
            "freeAgentRows": self.free_agent_rows,
            "executedAcceptedTrades": self.executed_accepted_trades,
            "gradedTradeRows": self.graded_trade_rows,
            "canonicalTradeEvents": self.canonical_trade_events,
            "boxScorePayloads": self.box_score_payloads,
            "transactionPeriodPayloads": self.transaction_period_payloads,
            "zipEntries": self.zip_entries,
            "nonDirectoryFiles": self.non_directory_files,
        }


LOCAL_FIXTURE: Final[AnalyticsFixture] = AnalyticsFixture(
    seasons=(2020, 2021, 2022, 2023, 2024, 2025, 2026),
    player_week_rows=28_294,
    waiver_rows=2_662,
    free_agent_rows=1_237,
    executed_accepted_trades=95,
    graded_trade_rows=70,
    canonical_trade_events=51,
    box_score_payloads=118,
    transaction_period_payloads=118,
    zip_entries=337,
    non_directory_files=306,
)

SCORE_MODELS: Final[tuple[str, ...]] = (
    TRADE_SCORE_MODEL,
    ACQUISITION_SCORE_MODEL,
    SEASON_GM_SCORE_MODEL,
    CAREER_GM_SCORE_MODEL,
    RECORDS_MODEL,
    DATA_HEALTH_MODEL,
)

PAYLOAD_VERSION: Final[str] = "mygm-fixture-dashboard-v1"
PRODUCT_LABEL: Final[str] = "Retrospective GM Rating"
FORMULA_VERSION: Final[str] = "mygm-retrospective-v1"
FORMULA_PROVENANCE: Final[str] = "fixture-derived ESPN export analytics"
FAAB_CONTEXT: Final[str] = "FAAB context unavailable: bidAmount is always 0"
CAREER_EXCLUSION: Final[str] = "2026 excluded from career ratings"
DATA_HEALTH_STATUS: Final[str] = "caveated"


class FixtureAnalyticsRepository:
    def dashboard_counts(self) -> dict[str, int]:
        return LOCAL_FIXTURE.source_counts

    def score_models(self) -> list[str]:
        return list(SCORE_MODELS)

    def warnings(self, version: str) -> list[str]:
        return [
            f"{version} uses local fixture-backed analytics until worker artifacts are available",
            CAREER_EXCLUSION,
        ]

    def metric_counts(self, model_name: str) -> dict[str, int]:
        counts = LOCAL_FIXTURE.source_counts
        if model_name == TRADE_SCORE_MODEL:
            return {
                "executedAcceptedTrades": counts["executedAcceptedTrades"],
                "gradedTradeRows": counts["gradedTradeRows"],
                "canonicalTradeEvents": counts["canonicalTradeEvents"],
                "ungradedExecutedAccepts": (
                    counts["executedAcceptedTrades"] - counts["gradedTradeRows"]
                ),
            }
        if model_name == ACQUISITION_SCORE_MODEL:
            return {
                "waiverRows": counts["waiverRows"],
                "freeAgentRows": counts["freeAgentRows"],
            }
        if model_name == RECORDS_MODEL:
            return {
                "boxScorePayloads": counts["boxScorePayloads"],
                "careerSeasonsIncluded": len(LOCAL_FIXTURE.seasons) - 1,
            }
        return counts


analytics_repository = FixtureAnalyticsRepository()
