from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from mygm_worker.analytics.identity import load_team_seasons
from mygm_worker.analytics.json_tools import float_value, int_value, string_value
from mygm_worker.analytics.vor import build_vor_model, position_for_lookup_entry

if TYPE_CHECKING:
    from mygm_worker.analytics.adp import AdpIndex
    from mygm_worker.analytics.models import JsonObject, ManagerIdentity, TeamSeason
    from mygm_worker.analytics.reader import FixtureReader
    from mygm_worker.analytics.vor import VorModel

# Half-width (in draft slots) of the pooled window used to fit the slot -> VOR curve.
_CURVE_WINDOW: Final = 8


@dataclass(frozen=True, slots=True)
class DraftPick:
    season: int
    overall_pick: int
    round_id: int
    round_pick: int
    player_id: int
    player_name: str
    team_id: int
    manager_key: str
    display_name: str
    keeper: bool
    season_points: float
    points_rank: int
    # overall_pick - points_rank: positive = outperformed slot (steal), negative = bust.
    steal_value: int
    # VOR-based draft grading (0.0 when no VOR model was supplied):
    season_vor: float = 0.0
    expected_vor: float = 0.0
    # surplus = season_vor - expected_vor for the slot; the slot-relative grade signal.
    surplus: float = 0.0
    # ADP reach FLAVOR only (never the grade baseline); None when ADP is unavailable.
    adp: float | None = None
    # adp - overall_pick: positive = drafted earlier than market (a reach), neg = value.
    reach: float | None = None


@dataclass(frozen=True, slots=True)
class SeasonDraft:
    season: int
    is_partial: bool
    pick_count: int
    picks: tuple[DraftPick, ...]
    best_steal: DraftPick | None
    biggest_bust: DraftPick | None


def season_drafts(
    reader: FixtureReader,
    managers: dict[str, ManagerIdentity],
    team_seasons: list[TeamSeason],
    *,
    vor_model: VorModel | None = None,
    position_by_player: dict[int, str] | None = None,
    adp_index: AdpIndex | None = None,
) -> tuple[SeasonDraft, ...]:
    team_lookup = {(row.season, row.team_id): row for row in team_seasons}
    names = {key: manager.display_name for key, manager in managers.items()}
    player_points = _season_player_points(reader)
    points_lookup = reader.player_lookup()
    model = vor_model if vor_model is not None else build_vor_model(reader)
    positions = position_by_player if position_by_player is not None else _positions(points_lookup)
    partial_by_season = {season.season: season.is_partial for season in reader.seasons()}
    season_basics: list[tuple[int, list[_PickBasics]]] = []
    for season in reader.seasons():
        raw_picks = _raw_picks(reader, season.season)
        if not raw_picks:
            continue
        sp = player_points.get(season.season, {})
        basics = [
            _pick_basics(
                raw, season.season, team_lookup, names, sp, points_lookup, model, positions
            )
            for raw in raw_picks
        ]
        season_basics.append((season.season, basics))
    curve = _expected_curve(
        [
            (b.overall_pick, b.season_vor)
            for _, basics in season_basics
            for b in basics
            if not b.keeper
        ]
    )
    drafts: list[SeasonDraft] = []
    for season, basics in season_basics:
        ranks = _points_ranks(basics)
        picks = tuple(
            _draft_pick(b, ranks[b.overall_pick], curve, adp_index)
            for b in sorted(basics, key=lambda item: item.overall_pick)
        )
        drafts.append(_season_draft(season, partial_by_season.get(season, False), picks))
    return tuple(drafts)


def _positions(points_lookup: JsonObject) -> dict[int, str]:
    return {
        int_value(pid): position_for_lookup_entry(player)
        for pid, player in points_lookup.items()
        if isinstance(player, dict)
    }


def _expected_curve(slot_vor: list[tuple[int, float]]) -> dict[int, float]:
    """Pooled draft-slot -> expected VOR curve, fit across every league draft.

    For each slot, average the season VOR of all picks within ``_CURVE_WINDOW`` slots
    of it (pooled across all seasons). This is robust, smooth, and ADP-free — so it
    grades every season including those with no vendored ADP.
    """
    if not slot_vor:
        return {}
    pairs = sorted(slot_vor)
    slots = sorted({slot for slot, _ in pairs})
    expected: dict[int, float] = {}
    for slot in slots:
        window = [vor for pick_slot, vor in pairs if abs(pick_slot - slot) <= _CURVE_WINDOW]
        expected[slot] = round(sum(window) / len(window), 4) if window else 0.0
    return expected


def _season_draft(season: int, is_partial: bool, picks: tuple[DraftPick, ...]) -> SeasonDraft:
    rankable = [pick for pick in picks if not pick.keeper and pick.season_points > 0.0]
    best_steal = max(rankable, key=lambda pick: pick.steal_value, default=None)
    biggest_bust = min(rankable, key=lambda pick: pick.steal_value, default=None)
    return SeasonDraft(
        season=season,
        is_partial=is_partial,
        pick_count=len(picks),
        picks=picks,
        best_steal=best_steal,
        biggest_bust=biggest_bust,
    )


@dataclass(frozen=True, slots=True)
class _PickBasics:
    season: int
    overall_pick: int
    round_id: int
    round_pick: int
    player_id: int
    player_name: str
    team_id: int
    manager_key: str
    display_name: str
    keeper: bool
    season_points: float
    season_vor: float


def _pick_basics(
    raw: JsonObject,
    season: int,
    team_lookup: dict[tuple[int, int], TeamSeason],
    names: dict[str, str],
    season_points: dict[int, float],
    points_lookup: JsonObject,
    vor_model: VorModel,
    position_by_player: dict[int, str],
) -> _PickBasics:
    team_id = int_value(raw.get("teamId"))
    player_id = int_value(raw.get("playerId"))
    team = team_lookup.get((season, team_id))
    manager_key = team.manager_key if team else f"unresolved:{season}:{team_id}"
    return _PickBasics(
        season=season,
        overall_pick=int_value(raw.get("overallPickNumber")),
        round_id=int_value(raw.get("roundId")),
        round_pick=int_value(raw.get("roundPickNumber")),
        player_id=player_id,
        player_name=_player_name(points_lookup, player_id),
        team_id=team_id,
        manager_key=manager_key,
        display_name=names.get(manager_key, manager_key),
        keeper=bool(raw.get("keeper")),
        season_points=round(season_points.get(player_id, 0.0), 4),
        season_vor=_player_season_vor(
            points_lookup, player_id, season, vor_model, position_by_player
        ),
    )


def _player_season_vor(
    points_lookup: JsonObject,
    player_id: int,
    season: int,
    vor_model: VorModel,
    position_by_player: dict[int, str],
) -> float:
    player = points_lookup.get(str(player_id))
    weekly = player.get("weekly_points") if isinstance(player, dict) else None
    season_weeks = weekly.get(str(season)) if isinstance(weekly, dict) else None
    if not isinstance(season_weeks, dict):
        return 0.0
    vor, _ = vor_model.value_for_weeks(season, position_by_player.get(player_id, ""), season_weeks)
    return vor


def _points_ranks(picks: list[_PickBasics]) -> dict[int, int]:
    ordered = sorted(picks, key=lambda item: (-item.season_points, item.overall_pick))
    return {pick.overall_pick: rank for rank, pick in enumerate(ordered, start=1)}


def _draft_pick(
    basics: _PickBasics,
    points_rank: int,
    curve: dict[int, float],
    adp_index: AdpIndex | None,
) -> DraftPick:
    expected = curve.get(basics.overall_pick, 0.0)
    adp = adp_index.adp(basics.season, basics.player_name) if adp_index is not None else None
    reach = round(adp - basics.overall_pick, 1) if adp is not None else None
    return DraftPick(
        season=basics.season,
        overall_pick=basics.overall_pick,
        round_id=basics.round_id,
        round_pick=basics.round_pick,
        player_id=basics.player_id,
        player_name=basics.player_name,
        team_id=basics.team_id,
        manager_key=basics.manager_key,
        display_name=basics.display_name,
        keeper=basics.keeper,
        season_points=basics.season_points,
        points_rank=points_rank,
        steal_value=basics.overall_pick - points_rank,
        season_vor=basics.season_vor,
        expected_vor=expected,
        surplus=round(basics.season_vor - expected, 4),
        adp=adp,
        reach=reach,
    )


def _raw_picks(reader: FixtureReader, season: int) -> list[JsonObject]:
    core = reader.core(season)
    draft_detail = core.get("draftDetail")
    if not isinstance(draft_detail, dict):
        return []
    picks = draft_detail.get("picks")
    if not isinstance(picks, list):
        return []
    return [pick for pick in picks if isinstance(pick, dict)]


def _season_player_points(reader: FixtureReader) -> dict[int, dict[int, float]]:
    players = reader.player_lookup()
    totals: dict[int, dict[int, float]] = {}
    for player_id_text, player in players.items():
        if not isinstance(player, dict):
            continue
        player_id = int_value(player_id_text)
        weekly = player.get("weekly_points")
        if not isinstance(weekly, dict):
            continue
        for season_text, weeks in weekly.items():
            if not isinstance(weeks, dict):
                continue
            season = int_value(season_text)
            total = sum(float_value(points) for points in weeks.values())
            totals.setdefault(season, {})[player_id] = total
    return totals


def _player_name(players: JsonObject, player_id: int) -> str:
    player = players.get(str(player_id))
    if isinstance(player, dict):
        name = string_value(player.get("name"))
        if name:
            return name
    return f"Player {player_id}"


@dataclass(frozen=True, slots=True)
class DraftGrades:
    # (manager_key, season) -> Σ VOR surplus over that manager's non-keeper picks.
    surplus_by_manager_season: dict[tuple[str, int], float]
    # manager_key -> career Σ surplus across included seasons.
    career_surplus: dict[str, float]
    best_pick_by_manager: dict[str, DraftPick]
    worst_pick_by_manager: dict[str, DraftPick]


def draft_grades(
    drafts: tuple[SeasonDraft, ...],
    included_seasons: tuple[int, ...],
) -> DraftGrades:
    """Aggregate per-pick VOR surplus into season + career draft grades per manager."""
    included = set(included_seasons)
    season_totals: dict[tuple[str, int], float] = {}
    career: dict[str, float] = {}
    best: dict[str, DraftPick] = {}
    worst: dict[str, DraftPick] = {}
    for draft in drafts:
        if draft.season not in included or draft.is_partial:
            continue
        for pick in draft.picks:
            if pick.keeper or pick.manager_key.startswith("unresolved:"):
                continue
            key = (pick.manager_key, draft.season)
            season_totals[key] = round(season_totals.get(key, 0.0) + pick.surplus, 4)
            career[pick.manager_key] = round(career.get(pick.manager_key, 0.0) + pick.surplus, 4)
            if pick.manager_key not in best or pick.surplus > best[pick.manager_key].surplus:
                best[pick.manager_key] = pick
            if pick.manager_key not in worst or pick.surplus < worst[pick.manager_key].surplus:
                worst[pick.manager_key] = pick
    return DraftGrades(
        surplus_by_manager_season=season_totals,
        career_surplus=career,
        best_pick_by_manager=best,
        worst_pick_by_manager=worst,
    )


def season_drafts_for_fixture(reader: FixtureReader) -> tuple[SeasonDraft, ...]:
    managers, team_seasons = load_team_seasons(reader)
    return season_drafts(reader, managers, team_seasons)
