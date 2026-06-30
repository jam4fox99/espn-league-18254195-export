from __future__ import annotations

import json
from typing import TYPE_CHECKING

from mygm_worker.analytics.adp import AdpIndex, load_adp_index, normalize_name
from mygm_worker.analytics.manager_archetype import (
    ARCHETYPES,
    ManagerSignals,
    _archetype_scores,
    _assign,
    _llm_one_liner,
    _percentiles,
    _template_one_liner,
)

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


# --------------------------------------------------------------- percentiles


def test_percentiles_midrank_orders_values() -> None:
    pct = _percentiles({"a": 1.0, "b": 2.0, "c": 3.0})
    assert pct["a"] < pct["b"] < pct["c"]
    # Midrank: (less + 0.5*equal) / n.
    assert pct["a"] == 0.5 / 3
    assert pct["b"] == 1.5 / 3
    assert pct["c"] == 2.5 / 3


def test_percentiles_ties_share_rank() -> None:
    pct = _percentiles({"a": 5.0, "b": 5.0})
    assert pct["a"] == pct["b"] == 0.5


def test_percentiles_single_manager_is_midpoint() -> None:
    assert _percentiles({"solo": 9.0}) == {"solo": 0.5}


# ------------------------------------------------------------------- assign


def test_assign_returns_argmax_and_runner_up() -> None:
    winner, runner_up = _assign(
        {"The Gambler": 0.2, "The Analyst": 0.9, "The Stoic": 0.5}
    )
    assert winner == "The Analyst"
    assert runner_up == "The Stoic"


def test_assign_breaks_ties_by_declared_order() -> None:
    # Gambler is declared before Analyst, so it wins an exact tie.
    winner, _ = _assign({"The Analyst": 0.5, "The Gambler": 0.5})
    assert winner == "The Gambler"


# ------------------------------------------- scoring → archetype assignment


def _signals(key: str, **values: float) -> ManagerSignals:
    return ManagerSignals(manager_key=key, **values)  # type: ignore[arg-type]


def test_dominant_signals_select_expected_archetypes() -> None:
    # Every manager carries realistic record/points (career data always does), so
    # luck reads as "wins beyond scoring" rather than just an unset default.
    population = {
        # Heavy, efficient waiver-wire worker.
        "opp": _signals(
            "opp",
            trade_volume=1,
            waiver_volume=50,
            waiver_net=500,
            lineup_efficiency=40,
            win_pct=0.5,
            points_for=1000,
            points_against=1000,
        ),
        # Always trading.
        "agg": _signals(
            "agg",
            trade_volume=20,
            trade_net=10,
            waiver_volume=5,
            waiver_net=10,
            lineup_efficiency=50,
            win_pct=0.5,
            points_for=1000,
            points_against=1000,
        ),
        # Set-and-forget: no churn, strong lineup.
        "sto": _signals(
            "sto",
            trade_volume=0,
            waiver_volume=0,
            lineup_efficiency=90,
            win_pct=0.5,
            points_for=1000,
            points_against=1000,
        ),
        # Wins beyond scoring (high win%, low points-for), easy schedule (low against).
        "luck": _signals(
            "luck",
            trade_volume=2,
            waiver_volume=2,
            lineup_efficiency=30,
            win_pct=0.9,
            points_for=800,
            points_against=700,
        ),
    }
    scores = _archetype_scores(population)
    assert _assign(scores["opp"])[0] == "The Opportunist"
    assert _assign(scores["agg"])[0] == "The Aggressor"
    assert _assign(scores["sto"])[0] == "The Stoic"
    assert _assign(scores["luck"])[0] == "The Lucky One"


def test_gambler_and_analyst_separate_on_draft_signals() -> None:
    population = {
        # Reaches on volatile players + churns trades.
        "gam": _signals("gam", reach_volatility=10, trade_volume=15, lineup_efficiency=40),
        # Drafts surplus value + efficient lineup + positive trade net.
        "ana": _signals(
            "ana", draft_value=20, lineup_efficiency=90, trade_net=100, trade_volume=5
        ),
        # Flat baseline so the two leaders dominate their own signals.
        "base": _signals("base", trade_volume=1, lineup_efficiency=30),
    }
    scores = _archetype_scores(population)
    assert _assign(scores["gam"])[0] == "The Gambler"
    assert _assign(scores["ana"])[0] == "The Analyst"


def test_every_archetype_has_scoring_weights() -> None:
    population = {"a": _signals("a", trade_volume=1), "b": _signals("b", waiver_volume=1)}
    scores = _archetype_scores(population)
    assert set(scores["a"]) == set(ARCHETYPES)


# ------------------------------------------------------------- one-liners


def test_template_one_liner_is_deterministic_and_named() -> None:
    facts = {
        "winPct": 0.62,
        "tradeCount": 12,
        "waiverMoves": 40,
        "draftSurplus": 8.0,
        "lineupEfficiency": 88.0,
    }
    for archetype in ARCHETYPES:
        sentence = _template_one_liner(archetype, "Casey", facts)
        assert sentence  # never empty
        assert "Casey" in sentence
        assert sentence == _template_one_liner(archetype, "Casey", facts)


def test_llm_one_liner_disabled_without_optin(monkeypatch: pytest.MonkeyPatch) -> None:
    # A key is present but the build-time opt-in is not — must stay offline.
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.delenv("MYGM_ARCHETYPE_LLM", raising=False)
    assert _llm_one_liner("The Analyst", "Casey", {"winPct": 0.5}) is None


# ------------------------------------------------------------------- ADP


def test_normalize_name_strips_punctuation_and_suffixes() -> None:
    assert normalize_name("Patrick Mahomes II") == "patrickmahomes"
    assert normalize_name("D.J. Moore") == "djmoore"
    assert normalize_name("Marquise Brown") == "marquisebrown"
    assert normalize_name(None) == ""


def test_adp_index_joins_by_normalized_name() -> None:
    index = AdpIndex(by_season={2021: {"christianmccaffrey": 1.2}})
    assert index.adp(2021, "Christian McCaffrey") == 1.2
    assert index.adp(2021, "Unknown Player") is None
    assert index.adp(2099, "Christian McCaffrey") is None
    assert index.has_season(2021)
    assert not index.has_season(2099)


def test_load_adp_index_reads_vendored_files(tmp_path: Path) -> None:
    (tmp_path / "adp_2021.json").write_text(
        json.dumps(
            {
                "season": 2021,
                "players": [
                    {"name": "Christian McCaffrey", "adp": 1.2},
                    {"name": "Dalvin Cook", "adp": 2.5},
                ],
            }
        ),
        encoding="utf-8",
    )
    index = load_adp_index(tmp_path)
    assert index.seasons == (2021,)
    assert index.adp(2021, "Christian McCaffrey") == 1.2
    assert index.adp(2021, "Dalvin Cook") == 2.5


def test_load_adp_index_skips_malformed_files(tmp_path: Path) -> None:
    (tmp_path / "adp_2020.json").write_text("{ not valid json", encoding="utf-8")
    (tmp_path / "adp_2021.json").write_text(
        json.dumps({"season": 2021, "players": "not-a-list"}), encoding="utf-8"
    )
    (tmp_path / "adp_2022.json").write_text(
        json.dumps({"season": 2022, "players": [{"name": "Joe Burrow", "adp": 30.0}]}),
        encoding="utf-8",
    )
    index = load_adp_index(tmp_path)
    # The two malformed files are skipped, not fatal; the good one still loads.
    assert index.seasons == (2022,)
    assert index.adp(2022, "Joe Burrow") == 30.0


def test_load_adp_index_keeps_lowest_adp_on_name_collision(tmp_path: Path) -> None:
    (tmp_path / "adp_2021.json").write_text(
        json.dumps(
            {
                "season": 2021,
                "players": [
                    {"name": "Mike Williams", "adp": 120.0},
                    {"name": "Mike Williams", "adp": 40.0},
                ],
            }
        ),
        encoding="utf-8",
    )
    # Order-independent: the lower (more relevant) ADP wins regardless of file order.
    assert load_adp_index(tmp_path).adp(2021, "Mike Williams") == 40.0
