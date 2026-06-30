from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from mygm_worker.analytics.adp import load_adp_index
from mygm_worker.analytics.draft import season_drafts
from mygm_worker.analytics.identity import load_team_seasons
from mygm_worker.analytics.json_tools import (
    as_array,
    as_object,
    float_value,
    int_value,
    string_value,
)
from mygm_worker.analytics.league_news import NewsContext, build_league_news
from mygm_worker.analytics.reader import FixtureReader
from mygm_worker.analytics.roster_fit import build_fit_index
from mygm_worker.analytics.trade_events import trade_event_rows
from mygm_worker.analytics.trade_grades import TradeGrade, grade_trade_event
from mygm_worker.analytics.veto import veto_likelihoods
from mygm_worker.analytics.vor import build_vor_model, position_for_lookup_entry
from mygm_worker.analytics.waiver_moves import waiver_move_rows

if TYPE_CHECKING:
    from mygm_worker.analytics.models import JsonObject

FIXTURE_ROOT = Path(__file__).parents[4] / "espn_exports" / "league_18254195"
LATEST_SEASON = 2025


def _news() -> JsonObject:
    reader = FixtureReader(FIXTURE_ROOT)
    managers, team_seasons = load_team_seasons(reader)
    team_lookup: dict[tuple[int, int], str] = {
        (row.season, row.team_id): row.manager_key for row in team_seasons
    }
    names: dict[str, str] = {key: manager.display_name for key, manager in managers.items()}
    vor_model = build_vor_model(reader)
    fit_index = build_fit_index(reader, team_seasons)
    positions: dict[int, str] = {
        int(pid): position_for_lookup_entry(player)
        for pid, player in reader.player_lookup().items()
        if isinstance(player, dict)
    }
    events = trade_event_rows(reader)
    grade_by_id: dict[str, TradeGrade] = {}
    for event in events:
        grade = grade_trade_event(
            event,
            vor_model=vor_model,
            position_by_player=positions,
            fit_index=fit_index,
            team_lookup=team_lookup,
        )
        if grade is not None:
            grade_by_id[grade.trade_id] = grade
    graded_pairs: list[tuple[JsonObject, TradeGrade]] = [
        (event, grade_by_id[string_value(event.get("tradeId"))])
        for event in events
        if string_value(event.get("tradeId")) in grade_by_id
    ]
    veto = veto_likelihoods(
        graded_pairs,
        players=reader.player_lookup(),
        fit_index=fit_index,
        adp_index=load_adp_index(),
        vor_model=vor_model,
        position_by_player=positions,
    )
    drafts = season_drafts(
        reader, managers, team_seasons, vor_model=vor_model, position_by_player=positions
    )
    final_week = next(s.final_week for s in reader.seasons() if s.season == LATEST_SEASON)
    return build_league_news(
        NewsContext(
            season=LATEST_SEASON,
            final_week=final_week,
            reader=reader,
            team_seasons=team_seasons,
            names=names,
            team_lookup=team_lookup,
            graded_pairs=graded_pairs,
            veto_results=veto,
            waiver_rows=list(waiver_move_rows(reader, vor_model)),
            drafts=drafts,
            standings=None,
            fit_index=fit_index,
            vor_model=vor_model,
            position_by_player=positions,
        )
    )


def test_news_is_scoped_to_latest_season_and_attributed() -> None:
    news = _news()
    assert int_value(news.get("season")) == LATEST_SEASON
    items = as_array(news.get("items"), "items")
    assert items
    # Every feed item is attributed (a manager key or a set of them) and season-scoped.
    for raw in items:
        item = as_object(raw, "item")
        assert int_value(item.get("season")) == LATEST_SEASON
        assert item.get("managerKey") or item.get("managerKeys")
        assert string_value(item.get("headline"))
        assert string_value(item.get("detail"))


def test_news_covers_trades_waivers_and_draft() -> None:
    news = _news()
    types = {
        string_value(as_object(raw, "item").get("type"))
        for raw in as_array(news.get("items"), "items")
    }
    assert "trade" in types
    assert "waiver" in types
    assert {"draftSteal", "draftBust"} & types
    assert "performance" in types


def test_trade_news_carries_grade_and_veto() -> None:
    news = _news()
    trade_items = [
        as_object(raw, "item")
        for raw in as_array(news.get("items"), "items")
        if string_value(as_object(raw, "item").get("type")) == "trade"
    ]
    assert trade_items
    for item in trade_items:
        assert as_object(item.get("grades"), "grades")
        assert item.get("veto") is not None
        assert "Veto risk" in string_value(item.get("detail"))


def test_team_strength_and_roster_aware_suggestions() -> None:
    news = _news()
    strength = as_array(news.get("teamStrength"), "teamStrength")
    assert strength
    # Each team has positional need readings and a strongest position.
    for raw in strength:
        row = as_object(raw, "strength")
        assert string_value(row.get("strongestPosition"))
        assert set(as_object(row.get("needs"), "needs")) == {"QB", "RB", "WR", "TE"}
    # Roster-aware suggestions name available free agents at weak positions with recent form.
    for raw in as_array(news.get("waiverSuggestions"), "waiverSuggestions"):
        row = as_object(raw, "suggestion")
        weak = as_array(row.get("weakPositions"), "weakPositions")
        suggestions = as_array(row.get("suggestions"), "suggestions")
        assert weak
        assert suggestions
        weak_positions = {string_value(position) for position in weak}
        for raw_suggestion in suggestions:
            suggestion = as_object(raw_suggestion, "suggestion")
            assert string_value(suggestion.get("position")) in weak_positions
            assert float_value(suggestion.get("trailingPoints")) >= 0
