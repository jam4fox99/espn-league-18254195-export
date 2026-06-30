from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, final

from mygm_worker.analytics.adp import load_adp_index
from mygm_worker.analytics.identity import load_team_seasons
from mygm_worker.analytics.json_tools import as_array, as_object, string_value
from mygm_worker.analytics.reader import FixtureReader
from mygm_worker.analytics.roster_fit import FitIndex, build_fit_index
from mygm_worker.analytics.trade_events import trade_event_rows
from mygm_worker.analytics.trade_grades import TradeGrade, grade_trade_event
from mygm_worker.analytics.trade_highlights import trade_highlights
from mygm_worker.analytics.trade_tree import trade_trees
from mygm_worker.analytics.veto import veto_likelihoods
from mygm_worker.analytics.vor import VorModel, build_vor_model, position_for_lookup_entry
from mygm_worker.analytics.waiver_moves import waiver_move_rows

if TYPE_CHECKING:
    from mygm_worker.analytics.models import JsonObject

FIXTURE_ROOT = Path(__file__).parents[4] / "espn_exports" / "league_18254195"


@final
class _Context:
    def __init__(self) -> None:
        self.reader = FixtureReader(FIXTURE_ROOT)
        managers, team_seasons = load_team_seasons(self.reader)
        self.team_seasons = team_seasons
        self.team_lookup: dict[tuple[int, int], str] = {
            (row.season, row.team_id): row.manager_key for row in team_seasons
        }
        self.names: dict[str, str] = {
            key: manager.display_name for key, manager in managers.items()
        }
        self.vor_model: VorModel = build_vor_model(self.reader)
        self.fit_index: FitIndex = build_fit_index(self.reader, team_seasons)
        self.positions: dict[int, str] = {
            int(pid): position_for_lookup_entry(player)
            for pid, player in self.reader.player_lookup().items()
            if isinstance(player, dict)
        }
        self.events = trade_event_rows(self.reader)
        grade_by_id: dict[str, TradeGrade] = {}
        for event in self.events:
            grade = grade_trade_event(
                event,
                vor_model=self.vor_model,
                position_by_player=self.positions,
                fit_index=self.fit_index,
                team_lookup=self.team_lookup,
            )
            if grade is not None:
                grade_by_id[grade.trade_id] = grade
        self.graded_pairs: list[tuple[JsonObject, TradeGrade]] = [
            (event, grade_by_id[string_value(event.get("tradeId"))])
            for event in self.events
            if string_value(event.get("tradeId")) in grade_by_id
        ]


def test_veto_percentages_are_bounded_and_mostly_fair() -> None:
    context = _Context()
    results = veto_likelihoods(
        context.graded_pairs,
        players=context.reader.player_lookup(),
        fit_index=context.fit_index,
        adp_index=load_adp_index(),
        vor_model=context.vor_model,
        position_by_player=context.positions,
    )
    assert results
    for result in results.values():
        assert 0.0 <= result.percent <= 100.0
        assert result.band in {"Looks fair", "Lean veto", "Collusion risk"}
        assert set(result.signals) == {"imbalance", "oneSidedNeed", "collusion"}
        assert len(result.rationale_by_manager) == 2
    # The league is mostly fair: the median trade should read as low veto risk.
    percents = sorted(result.percent for result in results.values())
    assert percents[len(percents) // 2] < 25.0


def test_best_and_worst_highlights_are_different_trades() -> None:
    context = _Context()
    highlights = trade_highlights(context.graded_pairs, context.names)
    assert highlights.best is not None
    assert highlights.worst is not None
    assert highlights.best["tradeId"] != highlights.worst["tradeId"]
    assert highlights.most_even is not None
    assert isinstance(highlights.most_even["valueGap"], float)


def test_trade_trees_trace_lineage_with_extracted_value() -> None:
    context = _Context()
    waiver_rows = list(waiver_move_rows(context.reader, context.vor_model))
    trees = trade_trees(
        list(context.events),
        waiver_rows,
        reader=context.reader,
        vor_model=context.vor_model,
        position_by_player=context.positions,
        team_lookup=context.team_lookup,
    )
    assert trees
    sample = as_object(next(iter(trees.values())), "tree")
    assert "branches" in sample
    assert "extractedVor" in sample
    # At least one asset somewhere was traded away again (a real multi-hop chain).
    any_multihop = False
    for tree in trees.values():
        tree_obj = as_object(tree, "tree")
        for branch in as_array(tree_obj.get("branches"), "branches"):
            branch_obj = as_object(branch, "branch")
            children = branch_obj.get("children")
            if isinstance(children, list) and children:
                any_multihop = True
    assert any_multihop
