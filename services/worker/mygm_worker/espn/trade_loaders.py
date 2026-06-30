from __future__ import annotations

# pyright: reportAny=false, reportArgumentType=false, reportAttributeAccessIssue=false, reportCallIssue=false, reportExplicitAny=false, reportImplicitStringConcatenation=false, reportImportCycles=false, reportOperatorIssue=false, reportUnannotatedClassAttribute=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnnecessaryIsInstance=false, reportUnusedCallResult=false
from pathlib import Path
from typing import Any

from mygm_worker.espn.trade_common import read_json, season_from_dir, team_display_name


def load_team_maps(export_root: Path) -> tuple[dict[int, dict[int, str]], dict[int, int]]:
    team_maps: dict[int, dict[int, str]] = {}
    final_periods: dict[int, int] = {}
    for season_dir in sorted(export_root.glob("season_*")):
        if not season_dir.is_dir():
            continue
        season = season_from_dir(season_dir)
        core_path = season_dir / "core.json"
        summary_path = season_dir / "_season_summary.json"
        core = read_json(core_path).get("data") or {}
        team_maps[season] = {
            int(team["id"]): team_display_name(team)
            for team in core.get("teams") or []
            if team.get("id") is not None
        }
        if summary_path.exists():
            summary = read_json(summary_path)
            final_periods[season] = int(summary.get("final_scoring_period") or 17)
        else:
            final_periods[season] = int((core.get("status") or {}).get("finalScoringPeriod") or 17)
    return team_maps, final_periods


def load_player_lookup(export_root: Path) -> dict[str, dict[str, Any]]:
    lookup_path = export_root / "player_lookup" / "player_weekly_points.json"
    lookup = read_json(lookup_path)
    return lookup.get("players") or {}


def iter_transactions(export_root: Path) -> list[dict[str, Any]]:
    transactions: list[dict[str, Any]] = []
    for season_dir in sorted(export_root.glob("season_*")):
        if not season_dir.is_dir():
            continue
        season = season_from_dir(season_dir)
        for period_path in sorted((season_dir / "transactions").glob("period_*.json")):
            payload = read_json(period_path)
            data = payload.get("data") or {}
            for index, tx in enumerate(data.get("transactions") or []):
                tx_copy = dict(tx)
                tx_copy["_season"] = season
                tx_copy["_source_file"] = str(period_path)
                tx_copy["_source_index"] = index
                transactions.append(tx_copy)
    return transactions


def _week_from_box_path(path: Path) -> int:
    stem = path.stem
    _, _, tail = stem.partition("_")
    try:
        return int(tail)
    except ValueError:
        return 0


def _roster_from_box_score(box_path: Path) -> dict[int, int]:
    """Map every rostered player to their team id for a single box-score week."""
    data = read_json(box_path).get("data") or {}
    schedule = data.get("schedule")
    roster: dict[int, int] = {}
    if not isinstance(schedule, list):
        return roster
    for matchup in schedule:
        if not isinstance(matchup, dict):
            continue
        for side_name in ("home", "away"):
            side = matchup.get(side_name)
            if not isinstance(side, dict):
                continue
            team_id = side.get("teamId")
            if team_id in (None, 0):
                continue
            entries = (side.get("rosterForCurrentScoringPeriod") or {}).get("entries") or []
            for entry in entries:
                pool = entry.get("playerPoolEntry") if isinstance(entry, dict) else None
                player_id = pool.get("id") if isinstance(pool, dict) else None
                if player_id is not None:
                    roster[int(player_id)] = int(team_id)
    return roster


def load_rosters_by_period(export_root: Path) -> dict[int, dict[int, dict[int, int]]]:
    """season -> scoring period -> {playerId: teamId} from weekly box scores."""
    rosters: dict[int, dict[int, dict[int, int]]] = {}
    for season_dir in sorted(export_root.glob("season_*")):
        if not season_dir.is_dir():
            continue
        season = season_from_dir(season_dir)
        by_period: dict[int, dict[int, int]] = {}
        for box_path in sorted((season_dir / "box_scores").glob("week_*.json")):
            week = _week_from_box_path(box_path)
            if week <= 0:
                continue
            roster = _roster_from_box_score(box_path)
            if roster:
                by_period[week] = roster
        if by_period:
            rosters[season] = by_period
    return rosters
