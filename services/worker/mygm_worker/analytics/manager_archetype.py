"""Manager archetypes ("GM DNA").

Assigns one of six archetypes to each manager from career signals, computed
league-relatively so the model is league-agnostic (next-build goal, Priority 3).
Independent best-fit — duplicates are allowed; the highest-scoring archetype wins
per manager. The scoring weights below are the single documented, tunable source
of truth.

Signals (all real, from existing snapshot data + vendored ADP):
  - trade volume / net points            (manager_value trade ledger)
  - waiver volume / net efficiency        (manager_value waiver ledger)
  - draft surplus value vs draft slot      (draft.steal_value)
  - reaching on boom-or-bust players       (ADP reach x weekly-points volatility)
  - lineup efficiency / record & points    (GM rating v2 components)
  - record vs scoring + schedule luck      (career win% vs points-for / against)

A one-sentence description is generated at build time (one cheap LLM call per
manager, cached into the snapshot) with a deterministic template fallback so a
build with no API key still produces a valid sentence and never hard-fails.
"""

from __future__ import annotations

import json
import os
import statistics
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, cast

from mygm_worker.analytics.draft import season_drafts
from mygm_worker.analytics.json_tools import (
    as_object,
    float_value,
    int_value,
    string_value,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from http.client import HTTPResponse

    from mygm_worker.analytics.adp import AdpIndex
    from mygm_worker.analytics.models import (
        JsonObject,
        JsonValue,
        ManagerIdentity,
        ManagerRating,
        TeamSeason,
    )
    from mygm_worker.analytics.reader import FixtureReader

# Display order + descriptions kept with the code that scores them.
ARCHETYPES: tuple[str, ...] = (
    "The Gambler",
    "The Analyst",
    "The Opportunist",
    "The Aggressor",
    "The Stoic",
    "The Lucky One",
)

# One-line definition per archetype — anchors the LLM sentence to the trait that
# actually won, so it doesn't drift onto whatever raw number is largest.
ARCHETYPE_BLURBS: dict[str, str] = {
    "The Gambler": "reaches early on boom-or-bust players and makes high-variance moves",
    "The Analyst": "drafts for value and starts an optimal lineup — process over noise",
    "The Opportunist": "works the waiver wire relentlessly and efficiently",
    "The Aggressor": "is always trading and churning the roster",
    "The Stoic": "rarely trades or streams — sets the roster and trusts it",
    "The Lucky One": "wins more than the underlying scoring and schedule deserve",
}

# Weighted blends of league-relative signal percentiles (each 0..1). Tunable.
ARCHETYPE_WEIGHTS: dict[str, dict[str, float]] = {
    "The Gambler": {"reach_volatility": 0.6, "trade_volume": 0.4},
    "The Analyst": {"draft_value": 0.4, "lineup_efficiency": 0.35, "trade_net": 0.25},
    "The Opportunist": {"waiver_volume": 0.5, "waiver_net": 0.5},
    "The Aggressor": {"trade_volume": 0.6, "waiver_volume": 0.4},
    "The Stoic": {"low_trade": 0.5, "low_waiver": 0.3, "lineup_efficiency": 0.2},
    "The Lucky One": {"luck": 1.0},
}


@dataclass(slots=True)
class ManagerSignals:
    manager_key: str
    seasons: int = 1
    trade_volume: float = 0.0
    trade_net: float = 0.0
    waiver_volume: float = 0.0
    waiver_net: float = 0.0
    draft_value: float = 0.0
    reach_volatility: float = 0.0
    lineup_efficiency: float = 0.0
    win_pct: float = 0.0
    points_for: float = 0.0
    points_against: float = 0.0
    rating: float = 0.0
    facts: JsonObject = field(default_factory=dict)


def _obj(value: JsonValue) -> JsonObject:
    """Narrow a JsonValue to an object, or empty dict — never raises."""
    return value if isinstance(value, dict) else {}


def _as_int(text: str) -> int | None:
    try:
        return int(text)
    except (TypeError, ValueError):
        return None


def _player_volatility(reader: FixtureReader) -> dict[tuple[int, int], float]:
    """(season, playerId) → coefficient of variation of weekly points (boom-or-bust)."""
    players = _obj(reader.player_lookup().get("players"))
    result: dict[tuple[int, int], float] = {}
    for pid_str, entry in players.items():
        pid = _as_int(pid_str)
        if pid is None:
            continue
        weekly = _obj(_obj(entry).get("weekly_points"))
        for season_str, weeks in weekly.items():
            season = _as_int(season_str)
            if season is None:
                continue
            scored = [
                value
                for value in (float_value(week) for week in _obj(weeks).values())
                if value > 0
            ]
            if len(scored) < 3:
                continue
            mean = statistics.fmean(scored)
            if mean <= 0:
                continue
            result[(season, pid)] = statistics.pstdev(scored) / mean
    return result


def _draft_signals(
    reader: FixtureReader,
    managers: dict[str, ManagerIdentity],
    team_seasons: list[TeamSeason],
    adp_index: AdpIndex,
    volatility: dict[tuple[int, int], float],
) -> dict[str, tuple[float, float]]:
    """manager_key → (mean draft surplus value, mean reach x volatility)."""
    surplus: dict[str, list[float]] = {}
    reach_vol: dict[str, list[float]] = {}
    for draft in season_drafts(reader, managers, team_seasons):
        for pick in draft.picks:
            if pick.keeper:
                continue
            mk = pick.manager_key
            if pick.season_points > 0:
                surplus.setdefault(mk, []).append(float(pick.steal_value))
            # A pick with no consensus ADP (obscure/late) or taken at/after ADP is not a
            # reach → 0.0, but it still counts toward the denominator so the per-manager
            # mean is over all non-keeper picks, not only ADP-matched ones (avoids
            # rewarding managers who simply draft fewer ADP-listed players).
            adp = adp_index.adp(pick.season, pick.player_name)
            reach = (adp - pick.overall_pick) if adp is not None else 0.0
            if reach <= 0:
                reach_vol.setdefault(mk, []).append(0.0)
                continue
            cv = volatility.get((pick.season, pick.player_id), 0.0)
            reach_vol.setdefault(mk, []).append(reach * cv)
    keys = set(surplus) | set(reach_vol)
    return {
        mk: (
            statistics.fmean(surplus[mk]) if surplus.get(mk) else 0.0,
            statistics.fmean(reach_vol[mk]) if reach_vol.get(mk) else 0.0,
        )
        for mk in keys
    }


def _gather_signals(
    reader: FixtureReader,
    managers: dict[str, ManagerIdentity],
    team_seasons: list[TeamSeason],
    careers: Mapping[str, JsonObject],
    trade_ledgers: Mapping[str, JsonObject],
    waiver_ledgers: Mapping[str, JsonObject],
    ratings: Sequence[ManagerRating],
    adp_index: AdpIndex,
) -> dict[str, ManagerSignals]:
    career_ratings = {r.manager_key: r for r in ratings if r.season is None}
    volatility = _player_volatility(reader)
    draft = _draft_signals(reader, managers, team_seasons, adp_index, volatility)

    signals: dict[str, ManagerSignals] = {}
    for manager_key, manager in managers.items():
        if manager.is_unresolved:
            continue
        career = careers.get(manager_key) or {}
        trade = trade_ledgers.get(manager_key) or {}
        waiver = waiver_ledgers.get(manager_key) or {}
        rating = career_ratings.get(manager_key)
        components = rating.normalized_components if rating else {}
        seasons = max(int_value(career.get("seasonsPlayed"), 1), 1)
        draft_value, reach_volatility = draft.get(manager_key, (0.0, 0.0))
        lineup_eff = float_value(components.get("lineupEfficiency"))
        win_pct = float_value(career.get("winPct"))
        rating_score = rating.final_score if rating else 0.0
        facts: JsonObject = {
            "tradeCount": float_value(trade.get("tradeCount")),
            "tradeNet": float_value(trade.get("netPoints")),
            "waiverMoves": float_value(waiver.get("eligibleMoves")),
            "waiverNet": float_value(waiver.get("netPoints")),
            "draftSurplus": round(draft_value, 1),
            "lineupEfficiency": round(lineup_eff, 1),
            "winPct": round(win_pct, 3),
            "rating": round(rating_score, 1),
        }
        signals[manager_key] = ManagerSignals(
            manager_key=manager_key,
            seasons=seasons,
            # All blended signals are per-season rates so cross-manager comparison
            # isn't biased toward longer-tenured managers (net is cumulative career
            # value; dividing by seasons matches the volume signals). The career
            # totals are kept in `facts` for the one-liner.
            trade_volume=float_value(trade.get("tradeCount")) / seasons,
            trade_net=float_value(trade.get("netPoints")) / seasons,
            waiver_volume=float_value(waiver.get("eligibleMoves")) / seasons,
            waiver_net=float_value(waiver.get("netPoints")) / seasons,
            draft_value=draft_value,
            reach_volatility=reach_volatility,
            lineup_efficiency=lineup_eff,
            win_pct=win_pct,
            points_for=float_value(career.get("pointsFor")),
            points_against=float_value(career.get("pointsAgainst")),
            rating=rating_score,
            facts=facts,
        )
    return signals


def _percentiles(values: dict[str, float]) -> dict[str, float]:
    """Midrank percentile in [0,1] for each key (league-relative, tie-safe)."""
    if not values:
        return {}
    items = list(values.values())
    n = len(items)
    if n == 1:
        return dict.fromkeys(values, 0.5)
    result: dict[str, float] = {}
    for key, value in values.items():
        less = sum(1 for other in items if other < value)
        equal = sum(1 for other in items if other == value)
        result[key] = (less + 0.5 * equal) / n
    return result


def _archetype_scores(signals: dict[str, ManagerSignals]) -> dict[str, dict[str, float]]:
    keys = list(signals)
    pct: dict[str, dict[str, float]] = {}
    for attr in (
        "trade_volume",
        "trade_net",
        "waiver_volume",
        "waiver_net",
        "draft_value",
        "reach_volatility",
        "lineup_efficiency",
        "win_pct",
        "points_for",
        "points_against",
    ):
        pct[attr] = _percentiles({key: getattr(signals[key], attr) for key in keys})

    # Composite percentiles used by the weighted blends.
    signal_p: dict[str, dict[str, float]] = {}
    for key in keys:
        win_p = pct["win_pct"][key]
        pf_p = pct["points_for"][key]
        pa_p = pct["points_against"][key]
        over_performance = 0.5 + 0.5 * (win_p - pf_p)  # wins beyond scoring → up to 1
        easy_schedule = 1.0 - pa_p  # faced weaker scoring → lucky
        signal_p[key] = {
            "trade_volume": pct["trade_volume"][key],
            "trade_net": pct["trade_net"][key],
            "waiver_volume": pct["waiver_volume"][key],
            "waiver_net": pct["waiver_net"][key],
            "draft_value": pct["draft_value"][key],
            "reach_volatility": pct["reach_volatility"][key],
            "lineup_efficiency": pct["lineup_efficiency"][key],
            "low_trade": 1.0 - pct["trade_volume"][key],
            "low_waiver": 1.0 - pct["waiver_volume"][key],
            "luck": max(0.0, min(1.0, 0.6 * over_performance + 0.4 * easy_schedule)),
        }

    scores: dict[str, dict[str, float]] = {}
    for key in keys:
        scores[key] = {
            archetype: round(
                sum(weight * signal_p[key].get(signal, 0.0) for signal, weight in weights.items()),
                4,
            )
            for archetype, weights in ARCHETYPE_WEIGHTS.items()
        }
    return scores


def _assign(scores: dict[str, float]) -> tuple[str, str]:
    ranked = sorted(scores.items(), key=lambda item: (-item[1], ARCHETYPES.index(item[0])))
    winner = ranked[0][0]
    runner_up = ranked[1][0] if len(ranked) > 1 else winner
    return winner, runner_up


def _template_one_liner(archetype: str, name: str, facts: JsonObject) -> str:
    """Deterministic fallback sentence — always valid, no API needed."""
    win = round(float_value(facts.get("winPct")) * 100)
    trades = int(float_value(facts.get("tradeCount")))
    waivers = int(float_value(facts.get("waiverMoves")))
    surplus = float_value(facts.get("draftSurplus"))
    lineup = round(float_value(facts.get("lineupEfficiency")))
    templates = {
        "The Gambler": (
            f"{name} swings for upside — reaching early on boom-or-bust players and "
            f"working {trades} trades to chase the ceiling."
        ),
        "The Analyst": (
            f"{name} drafts for value (+{surplus:g} surplus spots vs slot) and starts "
            f"{lineup}% of an optimal lineup — process over noise."
        ),
        "The Opportunist": (
            f"{name} lives on the waiver wire with {waivers} pickups, turning "
            f"free-agent churn into roster wins."
        ),
        "The Aggressor": (
            f"{name} is always wheeling and dealing — {trades} trades and {waivers} "
            f"waiver moves keep the roster in motion."
        ),
        "The Stoic": (
            f"{name} sets the roster and trusts it — few trades, few waivers, and a "
            f"steady {win}% win rate."
        ),
        "The Lucky One": (
            f"{name} keeps winning the games that matter, banking a {win}% record that "
            f"outruns the underlying math."
        ),
    }
    return templates.get(archetype, f"{name} brings a distinctive style to the league.")


def _llm_enabled() -> bool:
    """Build-time opt-in. Off by default so tests + key-less builds use templates."""
    return os.environ.get("MYGM_ARCHETYPE_LLM", "").strip().lower() in {"1", "true", "yes"}


def _llm_one_liner(archetype: str, name: str, facts: JsonObject) -> str | None:
    """One cheap Claude call, build-time only. Returns None on any failure."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key or not _llm_enabled():
        return None
    model = os.environ.get("MYGM_ARCHETYPE_MODEL", "claude-haiku-4-5")
    blurb = ARCHETYPE_BLURBS.get(archetype, "")
    prompt = (
        f"You are labeling a fantasy-football manager's 'GM DNA'. Their archetype is "
        f"'{archetype}' — meaning this manager {blurb}. Manager: {name}. Real career "
        f"numbers: {json.dumps(facts)}. Write ONE punchy sentence (max 22 words) in a "
        f"sports-analyst voice that captures how {name} embodies '{archetype}'. Lead with "
        f"the number that best fits '{archetype}' — not merely the largest number — use no "
        f"dollar signs, and give no preamble. Just the sentence."
    )
    body = json.dumps(
        {
            "model": model,
            "max_tokens": 80,
            "messages": [{"role": "user", "content": prompt}],
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=body,
        headers={
            "content-type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    try:
        # urlopen is typed `Any` in typeshed; pin the boundary to a concrete type.
        response = cast("HTTPResponse", urllib.request.urlopen(request, timeout=30))
        try:
            decoded = response.read().decode("utf-8")
        finally:
            response.close()
        payload = as_object(cast("JsonValue", json.loads(decoded)), "llm")
        content = payload.get("content")
        blocks = content if isinstance(content, list) else []
        text = " ".join(string_value(_obj(block).get("text")) for block in blocks).strip()
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError):
        return None
    return text or None


def compute_manager_archetypes(
    reader: FixtureReader,
    managers: dict[str, ManagerIdentity],
    team_seasons: list[TeamSeason],
    *,
    careers: Mapping[str, JsonObject],
    trade_ledgers: Mapping[str, JsonObject],
    waiver_ledgers: Mapping[str, JsonObject],
    ratings: Sequence[ManagerRating],
    adp_index: AdpIndex,
    names: dict[str, str] | None = None,
) -> dict[str, JsonObject]:
    """manager_key → {name, oneLiner, runnerUp, scores, signals}."""
    signals = _gather_signals(
        reader,
        managers,
        team_seasons,
        careers,
        trade_ledgers,
        waiver_ledgers,
        ratings,
        adp_index,
    )
    scores = _archetype_scores(signals)
    display_names = names or {key: manager.display_name for key, manager in managers.items()}

    result: dict[str, JsonObject] = {}
    for manager_key, manager_signals in signals.items():
        archetype, runner_up = _assign(scores[manager_key])
        display = display_names.get(manager_key, manager_key)
        facts = manager_signals.facts
        one_liner = _llm_one_liner(archetype, display, facts) or _template_one_liner(
            archetype, display, facts
        )
        result[manager_key] = {
            "name": archetype,
            "oneLiner": one_liner,
            "runnerUp": runner_up,
            "scores": {key: float(value) for key, value in sorted(scores[manager_key].items())},
            "signals": manager_signals.facts,
        }
    return result
