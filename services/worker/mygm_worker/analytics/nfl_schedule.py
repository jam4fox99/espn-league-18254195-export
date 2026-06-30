"""NFL game schedules, vendored as static per-season files.

The files under ``mygm_worker/data/nfl/schedule_<season>.json`` are factual NFL
matchups (who played whom each week), fetched once from nflverse (see
``scripts/fetch_nfl_schedule.py``) and committed so builds are reproducible with
no runtime network dependency. The worker uses them to find each player's weekly
opponent so it can derive defense-vs-position strength for the "Matchup Based"
player badge. The schedule is NFL-wide, so the vendored data is league-agnostic.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from mygm_worker.analytics.json_tools import (
    as_object,
    int_value,
    read_json,
    string_value,
)

_DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "nfl"

# nflverse uses current franchise codes; PRO_TEAM_ABBREV (ESPN) differs on two.
# Alias ESPN -> nflverse so a proTeamId-derived abbreviation joins the schedule.
_ESPN_TO_NFLVERSE = {"LAR": "LA", "WSH": "WAS"}


@dataclass(frozen=True, slots=True)
class ScheduleIndex:
    """(season -> team abbrev -> week -> opponent abbrev), opponents in nflverse codes."""

    by_season: dict[int, dict[str, dict[int, str]]]

    def opponent(self, season: int, team_abbrev: str, week: int) -> str:
        """Opponent faced by ``team_abbrev`` in ``week``; "" when unknown."""
        team = _ESPN_TO_NFLVERSE.get(team_abbrev, team_abbrev)
        return self.by_season.get(season, {}).get(team, {}).get(week, "")

    def has_season(self, season: int) -> bool:
        return season in self.by_season

    @property
    def seasons(self) -> tuple[int, ...]:
        return tuple(sorted(self.by_season))


def load_schedule_index(data_dir: Path | None = None) -> ScheduleIndex:
    """Load every vendored ``schedule_<season>.json`` into an opponent index."""
    directory = data_dir or _DATA_DIR
    by_season: dict[int, dict[str, dict[int, str]]] = {}
    if not directory.is_dir():
        return ScheduleIndex(by_season={})
    for path in sorted(directory.glob("schedule_*.json")):
        # Guard the whole parse so one malformed vendored file is skipped, not fatal.
        try:
            payload = as_object(read_json(path), str(path))
            season = int_value(payload.get("season"), 0)
            if season <= 0:
                continue
            teams: dict[str, dict[int, str]] = {}
            for team, weeks in as_object(payload.get("byTeam"), "byTeam").items():
                schedule = {
                    int(week): string_value(opponent)
                    for week, opponent in as_object(weeks, team).items()
                    if week.isdigit() and string_value(opponent)
                }
                if schedule:
                    teams[team] = schedule
        except (OSError, ValueError):
            continue
        if teams:
            by_season[season] = teams
    return ScheduleIndex(by_season=by_season)
