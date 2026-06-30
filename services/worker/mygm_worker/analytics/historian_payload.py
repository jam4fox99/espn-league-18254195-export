from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from mygm_worker.analytics.career import manager_careers
from mygm_worker.analytics.draft import draft_grades, season_drafts
from mygm_worker.analytics.lineup_efficiency import lineup_efficiency_rows
from mygm_worker.analytics.manager_value import manager_value
from mygm_worker.analytics.player_directory import enrich_player_row
from mygm_worker.analytics.player_leaderboards import (
    PlayerLeaderboards,
    PlayerSeasonRecord,
    PlayerWeekRecord,
    player_leaderboards,
)
from mygm_worker.analytics.ratings import gm_ratings_v2, gm_ratings_v3
from mygm_worker.analytics.records import superlatives
from mygm_worker.analytics.rivalries import rivalry_matrix
from mygm_worker.analytics.signature_player import build_signature_players
from mygm_worker.analytics.standings import season_standings

if TYPE_CHECKING:
    from mygm_worker.analytics.adp import AdpIndex
    from mygm_worker.analytics.career import CareerEra, CareerSeasonLine, ManagerCareer
    from mygm_worker.analytics.draft import DraftGrades, DraftPick, SeasonDraft
    from mygm_worker.analytics.lineup_efficiency import LineupSeasonRow
    from mygm_worker.analytics.manager_value import (
        ManagerTradeLedger,
        ManagerWaiverLedger,
        TradePartner,
    )
    from mygm_worker.analytics.models import (
        AnalyticsSummary,
        JsonObject,
        JsonValue,
        ManagerIdentity,
        ManagerRating,
        TeamSeason,
    )
    from mygm_worker.analytics.player_directory import PlayerDirectoryEntry
    from mygm_worker.analytics.reader import FixtureReader
    from mygm_worker.analytics.records import Superlative
    from mygm_worker.analytics.rivalries import ManagerRivalry, RivalryEdge, RivalryMatrix
    from mygm_worker.analytics.standings import SeasonStandings, TeamStanding
    from mygm_worker.analytics.vor import VorModel


@dataclass(frozen=True, slots=True)
class HistorianSections:
    career_by_manager: dict[str, JsonObject]
    trade_ledger_by_manager: dict[str, JsonObject]
    waiver_ledger_by_manager: dict[str, JsonObject]
    rivalry_by_manager: dict[str, JsonObject]
    signature_by_manager: dict[str, JsonObject]
    standings_by_season: dict[int, JsonObject]
    draft_by_season: dict[int, JsonObject]
    season_superlatives_by_season: dict[int, list[JsonValue]]
    rivalries_section: JsonObject
    lineup_efficiency_section: JsonObject
    player_leaderboards_section: JsonObject
    superlative_records: list[JsonObject]
    ratings_v2: tuple[ManagerRating, ...]
    ratings_v3: tuple[ManagerRating, ...]
    draft_card_by_manager: JsonObject
    drafts: tuple[SeasonDraft, ...]


def build_historian_sections(
    reader: FixtureReader,
    summary: AnalyticsSummary,
    managers: dict[str, ManagerIdentity],
    team_seasons: list[TeamSeason],
    directory: dict[int, PlayerDirectoryEntry],
    vor_model: VorModel,
    position_by_player: dict[int, str],
    adp_index: AdpIndex,
) -> HistorianSections:
    included = summary.career_included_seasons
    standings = season_standings(reader, managers, team_seasons)
    drafts = season_drafts(
        reader,
        managers,
        team_seasons,
        vor_model=vor_model,
        position_by_player=position_by_player,
        adp_index=adp_index,
    )
    grades = draft_grades(drafts, included)
    lineup_rows = lineup_efficiency_rows(reader, managers, team_seasons)
    value = manager_value(reader, managers, team_seasons, vor_model=vor_model)
    matrix = rivalry_matrix(reader, managers, team_seasons, included)
    player_boards = player_leaderboards(reader, managers, team_seasons)
    ratings_v2 = gm_ratings_v2(
        team_seasons=team_seasons,
        included_seasons=included,
        season_values=value.season_values,
        lineup_rows=lineup_rows,
    )
    ratings_v3 = gm_ratings_v3(
        team_seasons=team_seasons,
        included_seasons=included,
        season_values=value.season_values,
        lineup_rows=lineup_rows,
        draft_surplus=grades.surplus_by_manager_season,
    )
    season_rating, career_rating = _rating_lookups(ratings_v3)
    careers = manager_careers(standings, managers, season_rating, career_rating, included)
    superlative_rows = superlatives(
        lineup_rows=lineup_rows,
        trade_ledgers=value.trade_ledgers,
        waiver_ledgers=value.waiver_ledgers,
        season_drafts=drafts,
        included_seasons=included,
    )
    return HistorianSections(
        career_by_manager={career.manager_key: _career_json(career) for career in careers},
        trade_ledger_by_manager={
            ledger.manager_key: _trade_ledger_json(ledger) for ledger in value.trade_ledgers
        },
        waiver_ledger_by_manager={
            ledger.manager_key: _waiver_ledger_json(ledger) for ledger in value.waiver_ledgers
        },
        rivalry_by_manager={
            summary_row.manager_key: _manager_rivalry_json(summary_row)
            for summary_row in matrix.summaries
        },
        signature_by_manager=build_signature_players(drafts),
        standings_by_season={row.season: _standings_json(row) for row in standings},
        draft_by_season={row.season: _draft_json(row, directory) for row in drafts},
        season_superlatives_by_season=_season_superlatives(drafts, included, directory),
        rivalries_section=_rivalries_section(matrix),
        lineup_efficiency_section={"seasons": [_lineup_json(row) for row in lineup_rows]},
        player_leaderboards_section=_player_leaderboards_section(player_boards, directory),
        superlative_records=[_superlative_record(row, directory) for row in superlative_rows],
        ratings_v2=ratings_v2,
        ratings_v3=ratings_v3,
        draft_card_by_manager=_draft_cards(grades, directory),
        drafts=drafts,
    )


def _draft_cards(
    grades: DraftGrades,
    directory: dict[int, PlayerDirectoryEntry],
) -> JsonObject:
    cards: JsonObject = {}
    for manager_key, surplus in grades.career_surplus.items():
        best = grades.best_pick_by_manager.get(manager_key)
        worst = grades.worst_pick_by_manager.get(manager_key)
        cards[manager_key] = {
            "careerSurplus": round(surplus, 4),
            "bestPick": _pick_json(best, directory) if best is not None else None,
            "worstPick": _pick_json(worst, directory) if worst is not None else None,
        }
    return cards


def _player_leaderboards_section(
    boards: PlayerLeaderboards,
    directory: dict[int, PlayerDirectoryEntry],
) -> JsonObject:
    return {
        "topWeeks": [_player_week_json(row, directory) for row in boards.top_weeks],
        "topSeasons": [_player_season_json(row, directory) for row in boards.top_seasons],
    }


def _player_week_json(
    row: PlayerWeekRecord,
    directory: dict[int, PlayerDirectoryEntry],
) -> JsonObject:
    return enrich_player_row(
        {
            "playerId": row.player_id,
            "playerName": row.player_name,
            "position": row.position,
            "season": row.season,
            "week": row.week,
            "points": row.points,
            "managerKey": row.manager_key,
            "displayName": row.display_name,
            "teamName": row.team_name,
        },
        directory,
    )


def _player_season_json(
    row: PlayerSeasonRecord,
    directory: dict[int, PlayerDirectoryEntry],
) -> JsonObject:
    return enrich_player_row(
        {
            "playerId": row.player_id,
            "playerName": row.player_name,
            "position": row.position,
            "season": row.season,
            "points": row.points,
            "weeks": row.weeks,
            "managerKey": row.manager_key,
            "displayName": row.display_name,
            "teamName": row.team_name,
        },
        directory,
    )


def _rating_lookups(
    ratings: tuple[ManagerRating, ...],
) -> tuple[dict[tuple[str, int], float], dict[str, float]]:
    season_rating: dict[tuple[str, int], float] = {}
    career_rating: dict[str, float] = {}
    for rating in ratings:
        if rating.season is None:
            career_rating[rating.manager_key] = rating.final_score
        else:
            season_rating[(rating.manager_key, rating.season)] = rating.final_score
    return season_rating, career_rating


def _career_json(career: ManagerCareer) -> JsonObject:
    return {
        "seasonsPlayed": career.seasons_played,
        "wins": career.wins,
        "losses": career.losses,
        "ties": career.ties,
        "winPct": career.win_pct,
        "pointsFor": career.points_for,
        "pointsAgainst": career.points_against,
        "titles": career.titles,
        "runnerUps": career.runner_ups,
        "playoffAppearances": career.playoff_appearances,
        "bestFinish": career.best_finish,
        "worstFinish": career.worst_finish,
        "bestFinishSeason": career.best_finish_season,
        "mostPointsSeason": career.most_points_season,
        "avgRating": career.avg_rating,
        "seasonLines": [_season_line_json(line) for line in career.season_lines],
        "eras": [_era_json(era) for era in career.eras],
    }


def _season_line_json(line: CareerSeasonLine) -> JsonObject:
    return {
        "season": line.season,
        "teamName": line.team_name,
        "rankFinal": line.rank_final,
        "madePlayoffs": line.made_playoffs,
        "isChampion": line.is_champion,
        "wins": line.wins,
        "losses": line.losses,
        "ties": line.ties,
        "pointsFor": line.points_for,
        "ratingScore": line.rating_score,
    }


def _era_json(era: CareerEra) -> JsonObject:
    return {
        "kind": era.kind,
        "startSeason": era.start_season,
        "endSeason": era.end_season,
        "seasons": list(era.seasons),
        "titles": era.titles,
        "summary": era.summary,
    }


def _trade_ledger_json(ledger: ManagerTradeLedger) -> JsonObject:
    return {
        "tradeCount": ledger.trade_count,
        "netPoints": ledger.net_points,
        "receivedPoints": ledger.received_points,
        "sentPoints": ledger.sent_points,
        "bestTrade": ledger.best_trade,
        "worstTrade": ledger.worst_trade,
        "partners": [_partner_json(partner) for partner in ledger.partners],
    }


def _partner_json(partner: TradePartner) -> JsonObject:
    return {
        "managerKey": partner.manager_key,
        "displayName": partner.display_name,
        "tradeCount": partner.trade_count,
        "netPoints": partner.net_points,
    }


def _waiver_ledger_json(ledger: ManagerWaiverLedger) -> JsonObject:
    return {
        "eligibleMoves": ledger.eligible_moves,
        "netPoints": ledger.net_points,
        "addedPoints": ledger.added_points,
        "droppedPoints": ledger.dropped_points,
        "bestPickup": ledger.best_pickup,
        "worstDrop": ledger.worst_drop,
    }


def _manager_rivalry_json(summary_row: ManagerRivalry) -> JsonObject:
    return {
        "nemesis": _edge_json(summary_row.nemesis) if summary_row.nemesis else None,
        "favorite": _edge_json(summary_row.favorite) if summary_row.favorite else None,
        "edges": [_edge_json(edge) for edge in summary_row.edges],
    }


def _edge_json(edge: RivalryEdge) -> JsonObject:
    return {
        "opponentKey": edge.opponent_key,
        "opponentDisplayName": edge.opponent_display_name,
        "wins": edge.wins,
        "losses": edge.losses,
        "ties": edge.ties,
        "games": edge.games,
        "winPct": edge.win_pct,
        "averagePointsFor": edge.average_points_for,
        "averagePointsAgainst": edge.average_points_against,
        "playoffWins": edge.playoff_wins,
        "playoffLosses": edge.playoff_losses,
        "currentStreak": edge.current_streak,
    }


def _rivalries_section(matrix: RivalryMatrix) -> JsonObject:
    return {
        "managers": [
            {"managerKey": key, "displayName": name} for key, name in matrix.managers
        ],
        "edges": [_matrix_edge_json(edge) for edge in matrix.edges],
        "summaries": [_summary_json(summary_row) for summary_row in matrix.summaries],
    }


def _matrix_edge_json(edge: RivalryEdge) -> JsonObject:
    return {
        "managerKey": edge.manager_key,
        "opponentKey": edge.opponent_key,
        "displayName": edge.display_name,
        "opponentDisplayName": edge.opponent_display_name,
        "wins": edge.wins,
        "losses": edge.losses,
        "ties": edge.ties,
        "games": edge.games,
        "winPct": edge.win_pct,
        "averagePointsFor": edge.average_points_for,
        "averagePointsAgainst": edge.average_points_against,
    }


def _summary_json(summary_row: ManagerRivalry) -> JsonObject:
    return {
        "managerKey": summary_row.manager_key,
        "displayName": summary_row.display_name,
        "nemesis": _edge_json(summary_row.nemesis) if summary_row.nemesis else None,
        "favorite": _edge_json(summary_row.favorite) if summary_row.favorite else None,
    }


def _standings_json(row: SeasonStandings) -> JsonObject:
    champion: JsonObject | None = (
        {
            "managerKey": row.champion_manager_key,
            "displayName": row.champion_display_name,
            "teamName": row.champion_team_name,
        }
        if row.champion_manager_key
        else None
    )
    runner_up: JsonObject | None = (
        {
            "managerKey": row.runner_up_manager_key,
            "displayName": row.runner_up_display_name,
        }
        if row.runner_up_manager_key
        else None
    )
    return {
        "playoffTeamCount": row.playoff_team_count,
        "champion": champion,
        "runnerUp": runner_up,
        "finalStandings": [_team_standing_json(team) for team in row.standings],
    }


def _team_standing_json(team: TeamStanding) -> JsonObject:
    return {
        "rankFinal": team.rank_final,
        "managerKey": team.manager_key,
        "displayName": team.display_name,
        "teamName": team.team_name,
        "playoffSeed": team.playoff_seed,
        "madePlayoffs": team.made_playoffs,
        "isChampion": team.is_champion,
        "wins": team.wins,
        "losses": team.losses,
        "ties": team.ties,
        "pointsFor": round(team.points_for, 4),
        "pointsAgainst": round(team.points_against, 4),
    }


def _draft_json(row: SeasonDraft, directory: dict[int, PlayerDirectoryEntry]) -> JsonObject:
    return {
        "pickCount": row.pick_count,
        "isPartial": row.is_partial,
        "bestSteal": _pick_json(row.best_steal, directory) if row.best_steal else None,
        "biggestBust": _pick_json(row.biggest_bust, directory) if row.biggest_bust else None,
        "picks": [_pick_json(pick, directory) for pick in row.picks],
    }


def _pick_json(pick: DraftPick, directory: dict[int, PlayerDirectoryEntry]) -> JsonObject:
    return enrich_player_row(
        {
            "overallPick": pick.overall_pick,
            "round": pick.round_id,
            "roundPick": pick.round_pick,
            "playerId": pick.player_id,
            "playerName": pick.player_name,
            "teamId": pick.team_id,
            "managerKey": pick.manager_key,
            "displayName": pick.display_name,
            "keeper": pick.keeper,
            "season": pick.season,
            "seasonPoints": pick.season_points,
            "pointsRank": pick.points_rank,
            "stealValue": pick.steal_value,
            "seasonVor": pick.season_vor,
            "expectedVor": pick.expected_vor,
            "surplus": pick.surplus,
            "adp": pick.adp,
            "reach": pick.reach,
        },
        directory,
    )


def _season_superlatives(
    drafts: tuple[SeasonDraft, ...],
    included: tuple[int, ...],
    directory: dict[int, PlayerDirectoryEntry],
) -> dict[int, list[JsonValue]]:
    included_set = set(included)
    result: dict[int, list[JsonValue]] = {}
    for draft in drafts:
        if draft.season not in included_set or draft.is_partial:
            continue
        rows: list[JsonValue] = []
        if draft.best_steal is not None:
            rows.append(_draft_highlight("Draft steal", draft.best_steal, directory))
        if draft.biggest_bust is not None:
            rows.append(_draft_highlight("Draft bust", draft.biggest_bust, directory))
        result[draft.season] = rows
    return result


def _draft_highlight(
    label: str,
    pick: DraftPick,
    directory: dict[int, PlayerDirectoryEntry],
) -> JsonObject:
    return enrich_player_row(
        {
            "label": label,
            "managerKey": pick.manager_key,
            "displayName": pick.display_name,
            "value": float(pick.steal_value),
            "playerId": pick.player_id,
            "playerName": pick.player_name,
            "detail": (
                f"{pick.player_name} drafted #{pick.overall_pick}, finished #{pick.points_rank}"
            ),
        },
        directory,
    )


def _lineup_json(row: LineupSeasonRow) -> JsonObject:
    return {
        "season": row.season,
        "teamId": row.team_id,
        "managerKey": row.manager_key,
        "displayName": row.display_name,
        "teamName": row.team_name,
        "weeksCounted": row.weeks_counted,
        "startedPoints": row.started_points,
        "optimalPoints": row.optimal_points,
        "benchPoints": row.bench_points,
        "avgEfficiency": row.avg_efficiency,
        "aggregateEfficiency": row.aggregate_efficiency,
    }


def _superlative_record(
    row: Superlative,
    directory: dict[int, PlayerDirectoryEntry],
) -> JsonObject:
    record: JsonObject = {
        "recordId": f"superlative:{row.key}",
        "category": row.key,
        "label": row.label,
        "value": row.value,
        "managerKey": row.manager_key,
        "displayName": row.display_name,
        "season": row.season,
        "detail": row.detail,
    }
    if row.player_id is not None:
        record["playerId"] = row.player_id
        record["playerName"] = row.player_name
        return enrich_player_row(record, directory)
    return record
