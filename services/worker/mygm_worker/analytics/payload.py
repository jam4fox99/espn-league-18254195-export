from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING, Final

from mygm_worker.analytics.adp import load_adp_index
from mygm_worker.analytics.dvp import load_dvp_index
from mygm_worker.analytics.head_to_head import HeadToHeadPair, MatchupRow, head_to_head_pairs
from mygm_worker.analytics.historian_payload import HistorianSections, build_historian_sections
from mygm_worker.analytics.identity import load_team_seasons, manager_rows
from mygm_worker.analytics.injuries import load_injury_index
from mygm_worker.analytics.json_tools import (
    as_array,
    as_object,
    float_value,
    int_value,
    read_json,
    string_value,
)
from mygm_worker.analytics.league_news import NewsContext, build_league_news
from mygm_worker.analytics.manager_archetype import compute_manager_archetypes
from mygm_worker.analytics.models import SNAPSHOT_SOURCE, SNAPSHOT_VERSION
from mygm_worker.analytics.nfl_schedule import load_schedule_index
from mygm_worker.analytics.player_badges import compute_player_badges
from mygm_worker.analytics.player_directory import (
    build_player_directory,
    enrich_player_row,
    player_directory_json,
)
from mygm_worker.analytics.ratings import (
    FORMULA_VERSION,
    FORMULA_VERSION_V2,
    FORMULA_VERSION_V3,
    RATING_V2_CAVEAT,
    RATING_V3_CAVEAT,
    RATING_WEIGHTS_V2,
    RATING_WEIGHTS_V3,
    manager_rating_rows,
)
from mygm_worker.analytics.reader import FixtureReader
from mygm_worker.analytics.records import (
    LuckStrengthRow,
    RecordRow,
    luck_strength_rows,
    record_rows,
)
from mygm_worker.analytics.report import analyze_fixture, summary_to_json
from mygm_worker.analytics.roster_fit import build_fit_index
from mygm_worker.analytics.roster_history import roster_history
from mygm_worker.analytics.team_logos import build_logo_index
from mygm_worker.analytics.trade_events import trade_event_rows
from mygm_worker.analytics.trade_grades import SideGrade, TradeGrade, grade_trade_event
from mygm_worker.analytics.trade_highlights import TradeHighlights, trade_highlights
from mygm_worker.analytics.trade_tree import trade_trees
from mygm_worker.analytics.veto import VetoResult, veto_likelihoods
from mygm_worker.analytics.vor import build_vor_model, position_for_lookup_entry
from mygm_worker.analytics.waiver_moves import (
    manager_waiver_scores,
    waiver_move_rows,
    waiver_superlatives,
)

if TYPE_CHECKING:
    from mygm_worker.analytics.models import (
        AnalyticsSummary,
        JsonObject,
        JsonValue,
        ManagerRating,
        SeasonMeta,
    )
    from mygm_worker.analytics.player_directory import PlayerDirectoryEntry

PAYLOAD_VERSION: Final = "mygm-fixture-dashboard-v1"
TITLE: Final = "Retrospective GM Rating"
PROVENANCE: Final = "fixture-derived ESPN export analytics"
FAAB_CONTEXT_UNAVAILABLE: Final = "FAAB context unavailable"
LEGACY_ADAPTER_CAVEAT: Final = "legacy fixture dashboard payload adapted"
MANAGERS_PATH: Final = "managers"
SNAPSHOT_VERSION_PATH: Final = "meta.snapshotVersion"
ANALYTICS_SNAPSHOT_FILENAME: Final = "analytics_snapshot.json"


def dashboard_payload(summary: AnalyticsSummary) -> JsonObject:
    leaderboard = _leaderboard(summary)
    return {
        "payload_version": PAYLOAD_VERSION,
        "dashboard": _dashboard(summary, leaderboard),
        "seasons": _seasons(summary),
        "gm_leaderboard": leaderboard,
        "gm_leaderboard_count": len(leaderboard),
        "manager_report": _manager_report(summary),
        "trades": _trades(summary),
        "waivers": _waivers(summary),
        "records": _records(summary),
        "formula": _formula(summary),
        "data_health": _data_health(summary),
        "visible_strings": _visible_strings(summary),
    }


class SnapshotValidationError(ValueError):
    def __init__(self, path: str) -> None:
        super().__init__(f"{path} is required by {SNAPSHOT_VERSION}")


def league_analytics_snapshot(
    summary: AnalyticsSummary,
    fixture_root: Path | None = None,
    *,
    league_id: str | None = None,
) -> JsonObject:
    if fixture_root is not None:
        return _fixture_league_analytics_snapshot(summary, fixture_root, league_id)
    leaderboard = _leaderboard_objects(summary)
    manager_keys = _manager_keys(leaderboard)
    return _validate_snapshot(
        {
            "meta": {
                "snapshotVersion": SNAPSHOT_VERSION,
                "source": SNAPSHOT_SOURCE,
                "generatedAt": "fixture-contract",
                "productLabel": TITLE,
                "formulaVersion": summary.formula_version,
                "importStatus": "available",
            },
            "league": {
                "leagueId": "fixture-league",
                "name": "ESPN fixture league",
                "platform": SNAPSHOT_SOURCE,
            },
            "seasons": [_snapshot_season_row(season) for season in summary.seasons],
            "managers": [_snapshot_manager_row(row) for row in leaderboard],
            "leaderboards": {
                "allTime": [_snapshot_leaderboard_row(row) for row in leaderboard],
                "bySeason": [],
            },
            "trades": {"items": [_snapshot_trade_row(summary, manager_keys)]},
            "waivers": {"items": [_snapshot_waiver_row(summary, manager_keys)]},
            "records": {"items": [_snapshot_record_row(summary, manager_keys)]},
            "headToHead": {"pairs": [_snapshot_head_to_head_pair(manager_keys)]},
            "dataHealth": _snapshot_data_health(summary, ()),
            "formula": _snapshot_formula(summary),
        }
    )


def read_league_analytics_snapshot(payload: JsonObject) -> JsonObject:
    if "meta" in payload:
        return _validate_snapshot(payload)
    if "payload_version" in payload:
        return _legacy_payload_to_snapshot(payload)
    raise SnapshotValidationError(SNAPSHOT_VERSION_PATH)


def write_dashboard_payload(fixture_root: Path, output_dir: Path) -> Path:
    summary = analyze_fixture(fixture_root)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "dashboard_payload.json"
    _ = path.write_text(payload_to_json(dashboard_payload(summary)), encoding="utf-8")
    return path


def write_analytics_snapshot(
    fixture_root: Path,
    output_dir: Path,
    *,
    league_id: str | None = None,
    summary: AnalyticsSummary | None = None,
) -> Path:
    resolved_summary = summary or analyze_fixture(fixture_root)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / ANALYTICS_SNAPSHOT_FILENAME
    snapshot = league_analytics_snapshot(
        resolved_summary,
        fixture_root,
        league_id=league_id,
    )
    _ = path.write_text(payload_to_json(snapshot), encoding="utf-8")
    return path


def write_snapshot_artifacts(
    fixture_root: Path,
    output_dir: Path,
    *,
    league_id: str | None = None,
) -> tuple[Path, Path]:
    summary = analyze_fixture(fixture_root)
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / "summary.json"
    _ = summary_path.write_text(summary_to_json(summary), encoding="utf-8")
    snapshot_path = write_analytics_snapshot(
        fixture_root,
        output_dir,
        league_id=league_id,
        summary=summary,
    )
    return summary_path, snapshot_path


def payload_to_json(payload: JsonObject) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _fixture_league_analytics_snapshot(
    summary: AnalyticsSummary,
    fixture_root: Path,
    league_id: str | None,
) -> JsonObject:
    reader = FixtureReader(fixture_root)
    managers, team_seasons = load_team_seasons(reader)
    team_lookup = {
        (row.season, row.team_id): row.manager_key for row in team_seasons
    }
    directory = build_player_directory(reader)
    # Grade every player's career signature, then fold it into the directory so the
    # badge rides along everywhere a player row is enriched (leaderboards, trades,
    # waivers) without threading a parallel map through each builder.
    badges = compute_player_badges(
        reader, directory, load_schedule_index(), load_dvp_index(), load_injury_index()
    )
    directory = {
        player_id: replace(entry, badge=badges.get(player_id, ""))
        for player_id, entry in directory.items()
    }
    logo_index = build_logo_index(reader)
    vor_model = build_vor_model(reader)
    fit_index = build_fit_index(reader, team_seasons)
    adp_index = load_adp_index()
    position_by_player = {
        int_value(pid): position_for_lookup_entry(player)
        for pid, player in reader.player_lookup().items()
        if isinstance(player, dict)
    }
    historian = build_historian_sections(
        reader, summary, managers, team_seasons, directory, vor_model, position_by_player, adp_index
    )
    signature_index = historian.signature_by_manager
    archetypes = compute_manager_archetypes(
        reader,
        managers,
        team_seasons,
        careers=historian.career_by_manager,
        trade_ledgers=historian.trade_ledger_by_manager,
        waiver_ledgers=historian.waiver_ledger_by_manager,
        ratings=historian.ratings_v3,
        adp_index=adp_index,
    )
    roster_history_by_manager = roster_history(
        reader, managers, team_seasons, directory=directory
    )
    manager_identity_rows = [
        _enrich_manager_row(row, historian, logo_index, archetypes, roster_history_by_manager)
        for row in manager_rows(managers=managers, team_seasons=team_seasons)
    ]
    rating_rows_v1 = manager_rating_rows(team_seasons=team_seasons, ratings=summary.gm_ratings)
    rating_rows_v2 = manager_rating_rows(team_seasons=team_seasons, ratings=historian.ratings_v2)
    rating_rows_v3 = manager_rating_rows(team_seasons=team_seasons, ratings=historian.ratings_v3)
    leaderboards_v1 = _fixture_leaderboards(rating_rows_v1, logo_index, signature_index, archetypes)
    leaderboards_v2 = _fixture_leaderboards(rating_rows_v2, logo_index, signature_index, archetypes)
    leaderboards_v3 = _fixture_leaderboards(rating_rows_v3, logo_index, signature_index, archetypes)
    names = {key: manager.display_name for key, manager in managers.items()}
    trade_events = trade_event_rows(reader)
    raw_waiver_rows = list(waiver_move_rows(reader, vor_model))
    trade_grade_by_id: dict[str, TradeGrade] = {}
    for event in trade_events:
        grade = grade_trade_event(
            event,
            vor_model=vor_model,
            position_by_player=position_by_player,
            fit_index=fit_index,
            team_lookup=team_lookup,
        )
        if grade is not None:
            trade_grade_by_id[grade.trade_id] = grade
    graded_pairs = [
        (event, trade_grade_by_id[string_value(event.get("tradeId"))])
        for event in trade_events
        if string_value(event.get("tradeId")) in trade_grade_by_id
    ]
    veto_results = veto_likelihoods(
        graded_pairs,
        players=reader.player_lookup(),
        fit_index=fit_index,
        adp_index=adp_index,
        vor_model=vor_model,
        position_by_player=position_by_player,
    )
    highlights = trade_highlights(graded_pairs, names)
    for manager_row in manager_identity_rows:
        manager_row["fairTrader"] = highlights.fair_trader_by_manager.get(
            string_value(manager_row.get("managerKey"))
        )
    trees = trade_trees(
        list(trade_events),
        raw_waiver_rows,
        reader=reader,
        vor_model=vor_model,
        position_by_player=position_by_player,
        team_lookup=team_lookup,
    )
    news_season = max(summary.career_included_seasons) if summary.career_included_seasons else 0
    final_weeks = {season.season: season.final_week for season in summary.seasons}
    league_news = build_league_news(
        NewsContext(
            season=news_season,
            final_week=final_weeks.get(news_season, 17),
            reader=reader,
            team_seasons=team_seasons,
            names=names,
            team_lookup=team_lookup,
            graded_pairs=graded_pairs,
            veto_results=veto_results,
            waiver_rows=raw_waiver_rows,
            drafts=historian.drafts,
            standings=historian.standings_by_season.get(news_season),
            fit_index=fit_index,
            vor_model=vor_model,
            position_by_player=position_by_player,
        )
    )
    trade_rows = [
        _fixture_trade_row(row, team_lookup, directory, trade_grade_by_id, veto_results)
        for row in trade_events
    ]
    waiver_rows = [_fixture_waiver_row(row, directory) for row in raw_waiver_rows]
    record_items = [
        _fixture_record_row(row)
        for row in record_rows(reader, team_seasons, summary.career_included_seasons)
    ]
    record_items.extend(historian.superlative_records)
    pairs = [
        _fixture_head_to_head_pair(pair)
        for pair in head_to_head_pairs(reader, team_seasons, summary.career_included_seasons)
    ]
    luck_rows = luck_strength_rows(reader, team_seasons, summary.career_included_seasons)
    league = _fixture_league(reader, league_id)
    season_rows = [
        _enrich_season_row(_snapshot_season_row(season), historian)
        for season in summary.seasons
    ]
    waiver_superlatives_by_season = _superlatives_by_season(
        waiver_superlatives(raw_waiver_rows, names=names)
    )
    snapshot: JsonObject = {
        "meta": {
            "snapshotVersion": SNAPSHOT_VERSION,
            "source": SNAPSHOT_SOURCE,
            "generatedAt": string_value(_export_manifest(reader).get("exported_at"), "fixture"),
            "productLabel": TITLE,
            "formulaVersion": FORMULA_VERSION_V3,
            "importStatus": "available",
        },
        "league": league,
        "seasons": _json_array(season_rows),
        "managers": _json_array(manager_identity_rows),
        "leaderboards": leaderboards_v3,
        "formulas": _formulas_section(leaderboards_v1, leaderboards_v2, leaderboards_v3),
        "trades": {
            "items": _json_array(trade_rows),
            "highlights": _highlights_json(highlights),
            "trees": trees,
        },
        "waivers": {
            "items": _json_array(waiver_rows),
            "managerScores": manager_waiver_scores(waiver_rows),
            "superlatives": waiver_superlatives_by_season,
        },
        "records": {"items": _json_array(record_items)},
        "headToHead": {"pairs": _json_array(pairs)},
        "rivalries": historian.rivalries_section,
        "lineupEfficiency": historian.lineup_efficiency_section,
        "playerLeaderboards": historian.player_leaderboards_section,
        "playerDirectory": player_directory_json(directory),
        "draftCards": historian.draft_card_by_manager,
        "rosterHistory": dict(roster_history_by_manager),
        "waiverSuperlatives": waiver_superlatives_by_season,
        "leagueNews": league_news,
        "dataHealth": _fixture_data_health(
            summary,
            trade_rows,
            waiver_rows,
            record_items,
            pairs,
            luck_rows,
        ),
        "formula": _formula_v3(),
    }
    return _validate_snapshot(snapshot)


def _formulas_section(
    leaderboards_v1: JsonObject,
    leaderboards_v2: JsonObject,
    leaderboards_v3: JsonObject,
) -> JsonObject:
    return {
        "default": FORMULA_VERSION_V3,
        "available": [
            {
                **_formula_v3(),
                "leaderboards": leaderboards_v3,
            },
            {
                **_formula_v2(),
                "deprecated": True,
                "leaderboards": leaderboards_v2,
            },
            {
                "formulaVersion": FORMULA_VERSION,
                "label": "Retrospective GM Rating (v1)",
                "provenance": PROVENANCE,
                "weights": {
                    "tradePerformance": 0.35,
                    "waiverPerformance": 0.35,
                    "recordAndPoints": 0.2,
                    "luckAdjusted": 0.1,
                },
                "deprecated": True,
                "caveat": "v1 trade/waiver components are league-wide constants.",
                "leaderboards": leaderboards_v1,
            },
        ],
    }


def _formula_v3() -> JsonObject:
    return {
        "formulaVersion": FORMULA_VERSION_V3,
        "label": "League Historian GM Rating (v3)",
        "provenance": PROVENANCE,
        "weights": dict(RATING_WEIGHTS_V3),
        "componentLabels": {
            "tradeValue": "Trade value (VOR)",
            "waiverValue": "Waiver/FA value (VOR)",
            "lineupEfficiency": "Lineup efficiency",
            "recordAndPoints": "Record & points",
            "draftValue": "Draft value (VOR surplus)",
            "luck": "Luck",
        },
        "caveat": RATING_V3_CAVEAT,
    }


def _formula_v2() -> JsonObject:
    return {
        "formulaVersion": FORMULA_VERSION_V2,
        "label": "League Historian GM Rating (v2)",
        "provenance": PROVENANCE,
        "weights": dict(RATING_WEIGHTS_V2),
        "componentLabels": {
            "tradeValue": "Trade value",
            "waiverValue": "Waiver/FA value",
            "lineupEfficiency": "Lineup efficiency",
            "recordAndPoints": "Record & points",
        },
        "caveat": RATING_V2_CAVEAT,
    }


def _enrich_manager_row(
    row: JsonObject,
    historian: HistorianSections,
    logo_index: dict[str, JsonObject],
    archetypes: dict[str, JsonObject],
    roster_history_by_manager: dict[str, JsonObject],
) -> JsonObject:
    manager_key = string_value(row.get("managerKey"))
    enriched = dict(row)
    enriched["career"] = historian.career_by_manager.get(manager_key)
    enriched["value"] = {
        "trade": historian.trade_ledger_by_manager.get(manager_key),
        "waiver": historian.waiver_ledger_by_manager.get(manager_key),
    }
    enriched["rivalry"] = historian.rivalry_by_manager.get(manager_key)
    logo = logo_index.get(manager_key)
    if logo is not None:
        enriched["logo"] = logo
    enriched["signaturePlayer"] = historian.signature_by_manager.get(manager_key)
    enriched["archetype"] = archetypes.get(manager_key)
    enriched["draftCard"] = historian.draft_card_by_manager.get(manager_key)
    enriched["rosterHistory"] = roster_history_by_manager.get(manager_key)
    return enriched


def _superlatives_by_season(by_season: dict[int, JsonObject]) -> JsonObject:
    # JSON object keys must be strings; key the waiver award cards by season string.
    return {str(season): by_season[season] for season in sorted(by_season)}


def _enrich_season_row(row: JsonObject, historian: HistorianSections) -> JsonObject:
    season = int_value(row.get("season"))
    enriched = dict(row)
    standings = historian.standings_by_season.get(season)
    if standings is not None:
        enriched["champion"] = standings.get("champion")
        enriched["runnerUp"] = standings.get("runnerUp")
        enriched["finalStandings"] = standings.get("finalStandings")
        enriched["playoffTeamCount"] = standings.get("playoffTeamCount")
    enriched["draftRecap"] = historian.draft_by_season.get(season)
    enriched["superlatives"] = historian.season_superlatives_by_season.get(season, [])
    return enriched


def _json_array(rows: list[JsonObject]) -> list[JsonValue]:
    return list(rows)


def _highlights_json(highlights: TradeHighlights) -> JsonObject:
    return {
        "best": highlights.best,
        "worst": highlights.worst,
        "mostEven": highlights.most_even,
    }


def _fixture_league(reader: FixtureReader, league_id: str | None) -> JsonObject:
    manifest = _export_manifest(reader)
    seasons = as_array(manifest.get("seasons"), "seasons")
    first_season = as_object(seasons[0], "seasons[0]") if seasons else {}
    return {
        "leagueId": league_id or string_value(manifest.get("league_id"), "fixture-league"),
        "name": string_value(first_season.get("league_name"), "ESPN fixture league"),
        "platform": SNAPSHOT_SOURCE,
    }


def _export_manifest(reader: FixtureReader) -> JsonObject:
    return as_object(read_json(reader.root / "export_manifest.json"), "export_manifest")


def _fixture_leaderboards(
    rating_rows: list[JsonObject],
    logo_index: dict[str, JsonObject],
    signature_index: dict[str, JsonObject],
    archetypes: dict[str, JsonObject],
) -> JsonObject:
    all_time: list[JsonValue] = [
        _fixture_leaderboard_row(
            row, rank, logo_index, signature_index, archetypes, include_signature=True
        )
        for rank, row in enumerate(
            sorted(
                (
                    row
                    for row in rating_rows
                    if row.get("ratingScope") == "allTime"
                ),
                key=lambda item: (
                    -float_value(item.get("score")),
                    string_value(item.get("managerKey")),
                ),
            ),
            start=1,
        )
    ]
    by_season: list[JsonValue] = [
        _fixture_leaderboard_row(
            row, rank, logo_index, signature_index, archetypes, include_signature=False
        )
        for rank, row in enumerate(
            sorted(
                (
                    row
                    for row in rating_rows
                    if row.get("ratingScope") == "season"
                ),
                key=lambda item: (
                    int_value(item.get("season")),
                    -float_value(item.get("score")),
                    string_value(item.get("managerKey")),
                ),
            ),
            start=1,
        )
    ]
    return {"allTime": all_time, "bySeason": by_season}


def _fixture_leaderboard_row(
    row: JsonObject,
    rank: int,
    logo_index: dict[str, JsonObject],
    signature_index: dict[str, JsonObject],
    archetypes: dict[str, JsonObject],
    *,
    include_signature: bool,
) -> JsonObject:
    manager_key = string_value(row.get("managerKey"))
    payload: JsonObject = {
        "rank": rank,
        "managerKey": manager_key,
        "score": float_value(row.get("score")),
        "confidence": string_value(row.get("confidence"), "no_grade"),
        "season": row.get("season"),
        "components": as_object(row.get("normalizedComponents"), "normalizedComponents"),
        "caveats": as_array(row.get("caveats"), "caveats"),
    }
    logo = logo_index.get(manager_key)
    if logo is not None:
        payload["logo"] = logo
    if include_signature:
        payload["signaturePlayer"] = signature_index.get(manager_key)
        # Career archetype rides on the all-time board (it's a career label).
        payload["archetype"] = archetypes.get(manager_key)
    return payload


def _fixture_trade_row(
    row: JsonObject,
    team_lookup: dict[tuple[int, int], str],
    directory: dict[int, PlayerDirectoryEntry],
    trade_grade_by_id: dict[str, TradeGrade],
    veto_results: dict[str, VetoResult],
) -> JsonObject:
    season = int_value(row.get("season"))
    trade_id = string_value(row.get("tradeId"))
    grade = trade_grade_by_id.get(trade_id)
    side_grades = {side.team_id: side for side in grade.sides} if grade else {}
    sides = [
        _fixture_trade_side(
            as_object(side, "trade.side"), season, team_lookup, directory, side_grades
        )
        for side in as_array(row.get("sides"), "sides")
        if isinstance(side, dict)
    ]
    manager_keys = _stable_manager_keys(
        [string_value(side.get("managerKey")) for side in sides],
        season,
    )
    caveats = [
        string_value(caveat)
        for caveat in as_array(row.get("caveats"), "caveats")
        if string_value(caveat)
    ]
    if len(sides) < 2:
        caveats.append("Trade counterparty unresolved from source transaction items")
    payload: JsonObject = {
        **row,
        "season": season,
        "managerKeys": manager_keys,
        "sides": _json_array(sides),
        "scoreEligible": bool(row.get("scoreEligible")) and len(sides) >= 2,
        "caveats": list(caveats),
    }
    if grade is not None:
        payload["tradeGrade"] = {
            "valueGap": grade.value_gap,
            "winnerManagerKey": grade.winner_manager_key,
            "bothFillNeed": grade.both_fill_need,
        }
    veto = veto_results.get(trade_id)
    if veto is not None:
        payload["veto"] = {
            "percent": veto.percent,
            "band": veto.band,
            "signals": dict(veto.signals),
            "rationale": dict(veto.rationale_by_manager),
        }
    return payload


def _fixture_trade_side(
    side: JsonObject,
    season: int,
    team_lookup: dict[tuple[int, int], str],
    directory: dict[int, PlayerDirectoryEntry],
    side_grades: dict[int, SideGrade],
) -> JsonObject:
    team_id = int_value(side.get("teamId"))
    received_assets: list[JsonValue] = [
        enrich_player_row(dict(asset), directory)
        for asset in as_array(side.get("receivedAssets"), "receivedAssets")
        if isinstance(asset, dict)
    ]
    payload: JsonObject = {
        **side,
        "managerKey": team_lookup.get((season, team_id), f"unresolved:{season}:{team_id}"),
        "receivedAssets": received_assets,
    }
    side_grade = side_grades.get(team_id)
    if side_grade is not None:
        # Overwrite the legacy net-points letter with the VOR/fit grade so every surface
        # that already reads ``side.grade`` reflects the new model.
        payload["grade"] = side_grade.grade
        payload["vorGrade"] = side_grade.grade
        payload["valueScore"] = side_grade.value_score
        payload["fitScore"] = side_grade.fit_score
        payload["composite"] = side_grade.composite
        payload["receivedVor"] = side_grade.received_vor
        payload["givenUpVor"] = side_grade.given_up_vor
        payload["netVor"] = side_grade.net_vor
        payload["needsFilled"] = list(side_grade.needs_filled)
    return payload


def _stable_manager_keys(keys: list[str], season: int) -> list[JsonValue]:
    ordered = [key for key in dict.fromkeys(keys) if key]
    while len(ordered) < 2:
        ordered.append(f"unresolved:{season}:0")
    return list(ordered)


def _fixture_waiver_row(
    row: JsonObject,
    directory: dict[int, PlayerDirectoryEntry],
) -> JsonObject:
    transaction_id = string_value(row.get("sourceTransactionId"))
    exclusion_reason = string_value(row.get("exclusionReason"))
    caveats = [string_value(row.get("faabCaveat"))]
    if exclusion_reason:
        caveats.append(f"Move visible but excluded from scoring: {exclusion_reason}")
    return {
        **row,
        "moveId": f"waiver:{row.get('season')}:{transaction_id}",
        "addedPlayers": _enriched_players(row.get("addedPlayers"), directory),
        "droppedPlayers": _enriched_players(row.get("droppedPlayers"), directory),
        "caveats": [caveat for caveat in caveats if caveat],
    }


def _enriched_players(
    value: JsonValue,
    directory: dict[int, PlayerDirectoryEntry],
) -> list[JsonValue]:
    return [
        enrich_player_row(dict(player), directory)
        for player in as_array(value, "players")
        if isinstance(player, dict)
    ]


def _fixture_record_row(row: RecordRow) -> JsonObject:
    payload: JsonObject = {
        "recordId": f"{row.category}:{row.season or 'all'}:{row.team_id or 'league'}",
        "category": row.category,
        "label": _record_label(row.category),
        "value": row.value,
    }
    if row.manager_key is not None:
        payload["managerKey"] = row.manager_key
    if row.season is not None:
        payload["season"] = row.season
    if row.team_id is not None:
        payload["teamId"] = row.team_id
    return payload


def _record_label(category: str) -> str:
    return {
        "highest_weekly_score": "Highest weekly score",
        "lowest_weekly_score": "Lowest weekly score",
        "closest_matchup": "Closest matchup",
        "largest_matchup": "Largest matchup",
        "best_season_record": "Best season record",
        "worst_season_record": "Worst season record",
        "most_season_points": "Most season points",
        "most_career_points": "Most points all-time",
        "highest_career_ppg": "Highest points per game (career)",
    }.get(category, category.replace("_", " ").title())


def _fixture_head_to_head_pair(pair: HeadToHeadPair) -> JsonObject:
    return {
        "pairId": pair.pair_id,
        "managerAKey": pair.manager_a_key,
        "managerBKey": pair.manager_b_key,
        "matchups": [_fixture_matchup(row) for row in pair.matchups],
        "winsA": pair.wins_a,
        "winsB": pair.wins_b,
        "ties": pair.ties,
        "averageScoreA": pair.average_score_a,
        "averageScoreB": pair.average_score_b,
        "biggestWinMargin": pair.biggest_win_margin,
        "currentStreak": pair.current_streak,
        "playoffWinsA": pair.playoff_wins_a,
        "playoffWinsB": pair.playoff_wins_b,
        "playoffTies": pair.playoff_ties,
        "caveats": list(pair.caveats),
    }


def _fixture_matchup(row: MatchupRow) -> JsonObject:
    return {
        "season": row.season,
        "week": row.week,
        "teamAId": row.team_a_id,
        "teamBId": row.team_b_id,
        "teamAScore": row.team_a_score,
        "teamBScore": row.team_b_score,
        "result": row.result,
        "isPlayoff": row.is_playoff,
    }


def _fixture_data_health(
    summary: AnalyticsSummary,
    trade_rows: list[JsonObject],
    waiver_rows: list[JsonObject],
    record_items: list[JsonObject],
    pairs: list[JsonObject],
    luck_rows: tuple[LuckStrengthRow, ...],
) -> JsonObject:
    warnings: list[JsonValue] = list(summary.data_quality_warnings)
    caveats: list[JsonValue] = [
        *warnings,
        *(
            string_value(caveat)
            for row in luck_rows
            for caveat in row.caveats
            if string_value(caveat)
        ),
    ]
    withheld_scores: list[JsonValue] = [
        "FAAB-adjusted waiver context",
        "Draft grades excluded because ADP data is unavailable",
    ]
    return {
        "status": "caveated" if caveats else "available",
        "caveats": caveats,
        "warnings": warnings,
        "withheldScores": withheld_scores,
        "careerExcludedSeasons": list(summary.career_excluded_seasons),
        "sourceCounts": {
            "managers": summary.manager_identity.manager_count,
            "trades": len(trade_rows),
            "waivers": len(waiver_rows),
            "records": len(record_items),
            "headToHeadPairs": len(pairs),
            **_trade_source_counts(summary),
        },
    }


def _validate_snapshot(payload: JsonObject) -> JsonObject:
    meta = as_object(payload.get("meta"), "meta")
    _ = _required_string(meta, "snapshotVersion", "meta.snapshotVersion")
    _ = _required_object(payload, "league")
    _ = _required_array(payload, "seasons")
    managers = _required_array(payload, "managers")
    _ = _required_object(payload, "leaderboards")
    _ = _required_object(payload, "trades")
    _ = _required_object(payload, "waivers")
    _ = _required_object(payload, "records")
    _ = _required_object(payload, "headToHead")
    _ = _required_object(payload, "dataHealth")
    _ = _required_object(payload, "formula")
    if not managers:
        raise SnapshotValidationError(MANAGERS_PATH)
    for index, manager in enumerate(managers):
        _ = _required_string(as_object(manager, f"managers[{index}]"), "managerKey", "managerKey")
    return payload


def _legacy_payload_to_snapshot(payload: JsonObject) -> JsonObject:
    dashboard = as_object(payload.get("dashboard"), "dashboard")
    leaderboard = [
        as_object(row, f"gm_leaderboard[{index}]")
        for index, row in enumerate(as_array(payload.get("gm_leaderboard"), "gm_leaderboard"))
    ]
    manager_keys = _manager_keys(leaderboard)
    return _validate_snapshot(
        {
            "meta": {
                "snapshotVersion": SNAPSHOT_VERSION,
                "source": SNAPSHOT_SOURCE,
                "generatedAt": "legacy-fixture-adapter",
                "productLabel": string_value(dashboard.get("title"), TITLE),
                "formulaVersion": string_value(dashboard.get("formula_version")),
                "importStatus": "available",
            },
            "league": {
                "leagueId": "fixture-league",
                "name": "ESPN fixture league",
                "platform": SNAPSHOT_SOURCE,
            },
            "seasons": _legacy_seasons(payload),
            "managers": [_snapshot_manager_row(row) for row in leaderboard],
            "leaderboards": {
                "allTime": [_snapshot_leaderboard_row(row) for row in leaderboard],
                "bySeason": [],
            },
            "trades": {"items": [_legacy_trade_row(payload, manager_keys)]},
            "waivers": {"items": [_legacy_waiver_row(payload, manager_keys)]},
            "records": {"items": [_legacy_record_row(payload, manager_keys)]},
            "headToHead": {"pairs": [_snapshot_head_to_head_pair(manager_keys)]},
            "dataHealth": _legacy_data_health(payload),
            "formula": _legacy_formula(payload),
        }
    )


def _required_object(payload: JsonObject, key: str) -> JsonObject:
    return as_object(payload.get(key), key)


def _required_array(payload: JsonObject, key: str) -> list[JsonValue]:
    return as_array(payload.get(key), key)


def _required_string(payload: JsonObject, key: str, path: str) -> str:
    value = payload.get(key)
    if isinstance(value, str) and value:
        return value
    raise SnapshotValidationError(path)


def _leaderboard_objects(summary: AnalyticsSummary) -> list[JsonObject]:
    return [
        as_object(row, f"leaderboard[{index}]")
        for index, row in enumerate(_leaderboard(summary))
    ]


def _manager_keys(leaderboard: list[JsonObject]) -> tuple[str, str]:
    keys = tuple(
        string_value(row.get("manager_key"))
        for row in leaderboard
        if string_value(row.get("manager_key"))
    )
    if len(keys) >= 2:
        return (keys[0], keys[1])
    if len(keys) == 1:
        return (keys[0], keys[0])
    return ("unresolved:fixture:1", "unresolved:fixture:2")


def _snapshot_season_row(season: SeasonMeta) -> JsonObject:
    return {
        "season": season.season,
        "finalWeek": season.final_week,
        "transactionCount": season.transaction_count,
        "scheduleItems": season.schedule_items,
        "isPartial": season.is_partial,
    }


def _snapshot_manager_row(row: JsonObject) -> JsonObject:
    manager_key = string_value(row.get("manager_key"))
    return {
        "managerKey": manager_key,
        "displayName": manager_key,
        "scoreEligible": True,
        "caveats": as_array(row.get("warnings"), "warnings"),
    }


def _snapshot_leaderboard_row(row: JsonObject) -> JsonObject:
    return {
        "rank": row.get("rank", 0),
        "managerKey": row.get("manager_key", ""),
        "score": row.get("score", 0),
        "confidence": row.get("confidence", "no_grade"),
    }


def _snapshot_trade_row(
    summary: AnalyticsSummary,
    manager_keys: tuple[str, str],
) -> JsonObject:
    return {
        "tradeId": "fixture-trade-summary",
        "season": summary.career_included_seasons[-1],
        "managerKeys": list(manager_keys),
        "scoreEligible": False,
        "sourceCount": summary.trade_analytics.canonical_graded_trade_events,
        "caveats": ["contract fixture trade row; detailed derivation lands in Todo 3"],
    }


def _snapshot_waiver_row(
    summary: AnalyticsSummary,
    manager_keys: tuple[str, str],
) -> JsonObject:
    return {
        "moveId": "fixture-waiver-summary",
        "season": summary.career_included_seasons[-1],
        "managerKey": manager_keys[0],
        "transactionType": "WAIVER",
        "scoreEligible": False,
        "sourceCount": summary.acquisition_analytics.type_counts.get("WAIVER", 0),
        "caveats": [summary.acquisition_analytics.faab_warning],
    }


def _snapshot_record_row(
    summary: AnalyticsSummary,
    manager_keys: tuple[str, str],
) -> JsonObject:
    return {
        "recordId": "highest-weekly-score",
        "category": "weeklyScore",
        "label": "Highest weekly score",
        "value": summary.records.highest_weekly_score,
        "managerKey": manager_keys[0],
    }


def _snapshot_head_to_head_pair(manager_keys: tuple[str, str]) -> JsonObject:
    return {
        "pairId": f"{manager_keys[0]}::{manager_keys[1]}",
        "managerAKey": manager_keys[0],
        "managerBKey": manager_keys[1],
        "matchups": [],
        "caveats": ["contract fixture pair; matchup derivation lands in Todo 5"],
    }


def _snapshot_data_health(
    summary: AnalyticsSummary,
    extra_caveats: tuple[str, ...],
) -> JsonObject:
    return {
        "status": "caveated",
        "caveats": [*summary.data_quality_warnings, *extra_caveats],
        "warnings": list(summary.data_quality_warnings),
        "withheldScores": ["FAAB-adjusted waiver context"],
        "careerExcludedSeasons": list(summary.career_excluded_seasons),
        "sourceCounts": _trade_source_counts(summary),
    }


def _trade_source_counts(summary: AnalyticsSummary) -> JsonObject:
    trades = summary.trade_analytics
    return {
        "executedAcceptedTrades": trades.completed_trade_accept_rows,
        "gradedTradeRows": trades.graded_rows,
        "ungradedExecutedAccepts": trades.ungraded_rows,
        "canonicalTradeEvents": trades.canonical_graded_trade_events,
    }


def _snapshot_formula(summary: AnalyticsSummary) -> JsonObject:
    return {
        "formulaVersion": summary.formula_version,
        "provenance": PROVENANCE,
        "weights": {
            "tradePerformance": 0.35,
            "waiverPerformance": 0.35,
            "recordAndPoints": 0.2,
            "luckAdjusted": 0.1,
        },
    }


def _legacy_seasons(payload: JsonObject) -> list[JsonValue]:
    return [
        {
            "season": row.get("season", 0),
            "finalWeek": row.get("final_week", 0),
            "transactionCount": row.get("transaction_count", 0),
            "scheduleItems": row.get("schedule_items", 0),
            "isPartial": row.get("is_partial", False),
        }
        for row in (
            as_object(season, f"seasons[{index}]")
            for index, season in enumerate(as_array(payload.get("seasons"), "seasons"))
        )
    ]


def _legacy_trade_row(payload: JsonObject, manager_keys: tuple[str, str]) -> JsonObject:
    trades = as_object(payload.get("trades"), "trades")
    return {
        "tradeId": "legacy-trade-summary",
        "season": 0,
        "managerKeys": list(manager_keys),
        "scoreEligible": False,
        "sourceCount": trades.get("canonical_graded_trade_events", 0),
        "caveats": [LEGACY_ADAPTER_CAVEAT],
    }


def _legacy_waiver_row(payload: JsonObject, manager_keys: tuple[str, str]) -> JsonObject:
    waivers = as_object(payload.get("waivers"), "waivers")
    return {
        "moveId": "legacy-waiver-summary",
        "season": 0,
        "managerKey": manager_keys[0],
        "transactionType": "WAIVER",
        "scoreEligible": False,
        "sourceCount": as_object(waivers.get("type_counts"), "type_counts").get("WAIVER", 0),
        "caveats": [string_value(waivers.get("faab_context"), FAAB_CONTEXT_UNAVAILABLE)],
    }


def _legacy_record_row(payload: JsonObject, manager_keys: tuple[str, str]) -> JsonObject:
    records = as_object(payload.get("records"), "records")
    return {
        "recordId": "legacy-highest-weekly-score",
        "category": "weeklyScore",
        "label": "Highest weekly score",
        "value": float_value(records.get("highest_weekly_score")),
        "managerKey": manager_keys[0],
    }


def _legacy_data_health(payload: JsonObject) -> JsonObject:
    data_health = as_object(payload.get("data_health"), "data_health")
    caveats = [
        *as_array(data_health.get("warnings"), "warnings"),
        *as_array(data_health.get("confidence_caveats"), "confidence_caveats"),
        LEGACY_ADAPTER_CAVEAT,
    ]
    return {
        "status": string_value(data_health.get("status"), "caveated"),
        "caveats": caveats,
        "warnings": caveats,
        "withheldScores": ["FAAB-adjusted waiver context"],
    }


def _legacy_formula(payload: JsonObject) -> JsonObject:
    formula = as_object(payload.get("formula"), "formula")
    return {
        "formulaVersion": string_value(formula.get("version")),
        "provenance": string_value(formula.get("provenance"), PROVENANCE),
        "weights": as_object(formula.get("weights"), "weights"),
    }


def _dashboard(summary: AnalyticsSummary, leaderboard: list[JsonValue]) -> JsonObject:
    return {
        "title": TITLE,
        "status": summary.status,
        "formula_version": summary.formula_version,
        "manager_count": summary.manager_identity.manager_count,
        "career_seasons_counted": len(summary.career_included_seasons),
        "career_seasons_excluded": list(summary.career_excluded_seasons),
        "top_manager": leaderboard[0] if leaderboard else None,
        "data_health_status": "caveated",
    }


def _seasons(summary: AnalyticsSummary) -> list[JsonValue]:
    return [_season_row(season) for season in summary.seasons]


def _season_row(season: SeasonMeta) -> JsonObject:
    return {
        "season": season.season,
        "final_week": season.final_week,
        "transaction_count": season.transaction_count,
        "schedule_items": season.schedule_items,
        "is_partial": season.is_partial,
        "source_file": season.source_file,
    }


def _leaderboard(summary: AnalyticsSummary) -> list[JsonValue]:
    career_ratings = [
        rating for rating in summary.gm_ratings if rating.season is None
    ]
    sorted_ratings = sorted(
        career_ratings,
        key=lambda rating: (-rating.final_score, rating.manager_key),
    )
    return [_rating_row(rating, rank) for rank, rating in enumerate(sorted_ratings, start=1)]


def _manager_report(summary: AnalyticsSummary) -> JsonObject:
    return {
        "title": TITLE,
        "career": _leaderboard(summary),
        "season_ratings": [
            _rating_row(rating, 0)
            for rating in summary.gm_ratings
            if rating.season is not None
        ],
    }


def _rating_row(rating: ManagerRating, rank: int) -> JsonObject:
    return {
        "rank": rank,
        "manager_key": rating.manager_key,
        "season": rating.season,
        "score": rating.final_score,
        "confidence": rating.confidence,
        "formula_version": rating.formula_version,
        "components": dict(rating.normalized_components),
        "warnings": list(rating.warnings),
    }


def _trades(summary: AnalyticsSummary) -> JsonObject:
    trades = summary.trade_analytics
    return {
        "completed_trade_accept_rows": trades.completed_trade_accept_rows,
        "graded_rows": trades.graded_rows,
        "ungraded_executed_accepts": trades.ungraded_rows,
        "canonical_graded_trade_events": trades.canonical_graded_trade_events,
        "canonical_groups_with_multiple_rows": trades.canonical_groups_with_multiple_rows,
        "item_sources": dict(trades.item_sources),
        "ungraded_reasons": dict(trades.ungraded_reasons),
        "visible_summary": (
            f"{trades.canonical_graded_trade_events} canonical graded trade events"
        ),
    }


def _waivers(summary: AnalyticsSummary) -> JsonObject:
    acquisitions = summary.acquisition_analytics
    return {
        "total_rows": acquisitions.total_rows,
        "counted_rows": acquisitions.counted_rows,
        "excluded_rows": acquisitions.excluded_rows,
        "type_counts": dict(acquisitions.type_counts),
        "status_counts": dict(acquisitions.status_counts),
        "exclusion_reasons": dict(acquisitions.exclusion_reasons),
        "gross_rows": acquisitions.gross_rows,
        "net_rows": acquisitions.net_rows,
        "faab_context": acquisitions.faab_warning,
    }


def _records(summary: AnalyticsSummary) -> JsonObject:
    records = summary.records
    return {
        "seasons_counted": records.seasons_counted,
        "total_wins": records.total_wins,
        "total_losses": records.total_losses,
        "total_ties": records.total_ties,
        "highest_weekly_score": records.highest_weekly_score,
        "lowest_weekly_score": records.lowest_weekly_score,
    }


def _formula(summary: AnalyticsSummary) -> JsonObject:
    weights: JsonObject = (
        dict(summary.gm_ratings[0].weights)
        if summary.gm_ratings
        else {}
    )
    score_range: JsonObject = {"min": 0, "max": 100}
    return {
        "name": TITLE,
        "version": summary.formula_version,
        "provenance": PROVENANCE,
        "weights": weights,
        "components": list(weights),
        "score_range": score_range,
    }


def _data_health(summary: AnalyticsSummary) -> JsonObject:
    excluded = ", ".join(str(season) for season in summary.career_excluded_seasons)
    career_exclusion = f"{excluded} excluded from career ratings"
    return {
        "status": "caveated",
        "all_team_seasons_mapped": summary.manager_identity.all_team_seasons_mapped,
        "confidence_caveats": list(summary.data_quality_warnings),
        "career_exclusion": career_exclusion,
        "warnings": list(summary.data_quality_warnings),
    }


def _visible_strings(summary: AnalyticsSummary) -> list[JsonValue]:
    trades = summary.trade_analytics
    return [
        TITLE,
        f"{trades.canonical_graded_trade_events} canonical graded trade events",
        f"{trades.ungraded_rows} ungraded executed accepts",
        FAAB_CONTEXT_UNAVAILABLE,
        "2026 excluded from career ratings",
        summary.formula_version,
        PROVENANCE,
    ]
