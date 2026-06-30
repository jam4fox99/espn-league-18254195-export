from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING

from mygm_worker.analytics.identity import load_team_seasons
from mygm_worker.analytics.json_tools import as_array, float_value, int_value, string_value
from mygm_worker.analytics.trade_events import trade_event_rows
from mygm_worker.analytics.vor import build_vor_model, position_for_lookup_entry
from mygm_worker.analytics.waiver_moves import waiver_move_rows

if TYPE_CHECKING:
    from mygm_worker.analytics.models import (
        JsonObject,
        JsonValue,
        ManagerIdentity,
        TeamSeason,
    )
    from mygm_worker.analytics.reader import FixtureReader
    from mygm_worker.analytics.vor import VorModel

_NO_PARTNERS: dict[str, list[float]] = {}


@dataclass(frozen=True, slots=True)
class ManagerSeasonValue:
    manager_key: str
    season: int
    trade_net_points: float
    trade_count: int
    waiver_net_points: float
    waiver_count: int


@dataclass(frozen=True, slots=True)
class TradePartner:
    manager_key: str
    display_name: str
    trade_count: int
    net_points: float


@dataclass(frozen=True, slots=True)
class ManagerTradeLedger:
    manager_key: str
    display_name: str
    trade_count: int
    net_points: float
    received_points: float
    sent_points: float
    best_trade: JsonObject | None
    worst_trade: JsonObject | None
    partners: tuple[TradePartner, ...]


@dataclass(frozen=True, slots=True)
class ManagerWaiverLedger:
    manager_key: str
    display_name: str
    eligible_moves: int
    net_points: float
    added_points: float
    dropped_points: float
    best_pickup: JsonObject | None
    worst_drop: JsonObject | None


@dataclass(frozen=True, slots=True)
class ManagerValueResult:
    season_values: tuple[ManagerSeasonValue, ...]
    trade_ledgers: tuple[ManagerTradeLedger, ...]
    waiver_ledgers: tuple[ManagerWaiverLedger, ...]


@dataclass(slots=True)
class _TradeTotals:
    trade_count: int = 0
    net_points: float = 0.0
    received_points: float = 0.0
    sent_points: float = 0.0


@dataclass(slots=True)
class _WaiverTotals:
    eligible_moves: int = 0
    net_points: float = 0.0
    added_points: float = 0.0
    dropped_points: float = 0.0


def manager_value(
    reader: FixtureReader,
    managers: dict[str, ManagerIdentity],
    team_seasons: list[TeamSeason],
    *,
    vor_model: VorModel | None = None,
) -> ManagerValueResult:
    model = vor_model if vor_model is not None else build_vor_model(reader)
    position_by_player = {
        int_value(pid): position_for_lookup_entry(player)
        for pid, player in reader.player_lookup().items()
        if isinstance(player, dict)
    }
    team_lookup = {(row.season, row.team_id): row.manager_key for row in team_seasons}
    names = {key: manager.display_name for key, manager in managers.items()}
    trade_data = _trade_values(reader, team_lookup, names, model, position_by_player)
    waiver_data = _waiver_values(reader, names, model)
    season_values = _season_values(trade_data.per_season, waiver_data.per_season)
    return ManagerValueResult(
        season_values=season_values,
        trade_ledgers=trade_data.ledgers,
        waiver_ledgers=waiver_data.ledgers,
    )


@dataclass(slots=True)
class _TradeData:
    per_season: dict[tuple[str, int], tuple[float, int]]
    ledgers: tuple[ManagerTradeLedger, ...]


@dataclass(slots=True)
class _WaiverData:
    per_season: dict[tuple[str, int], tuple[float, int]]
    ledgers: tuple[ManagerWaiverLedger, ...]


def _trade_values(
    reader: FixtureReader,
    team_lookup: dict[tuple[int, int], str],
    names: dict[str, str],
    vor_model: VorModel,
    position_by_player: dict[int, str],
) -> _TradeData:
    per_season: defaultdict[tuple[str, int], list[float]] = defaultdict(lambda: [0.0, 0.0])
    totals: defaultdict[str, _TradeTotals] = defaultdict(_TradeTotals)
    partner_totals: defaultdict[str, defaultdict[str, list[float]]] = defaultdict(
        lambda: defaultdict(lambda: [0.0, 0.0])
    )
    best: dict[str, JsonObject] = {}
    worst: dict[str, JsonObject] = {}
    for row in trade_event_rows(reader):
        if row.get("scoreEligible") is not True:
            continue
        season = int_value(row.get("season"))
        nets = _trade_net_by_manager(row, season, team_lookup, vor_model, position_by_player)
        managers_in_trade = list(nets)
        for manager_key, (net, received, sent) in nets.items():
            bucket = per_season[(manager_key, season)]
            bucket[0] += net
            bucket[1] += 1
            total = totals[manager_key]
            total.trade_count += 1
            total.net_points += net
            total.received_points += received
            total.sent_points += sent
            _track_extreme(best, worst, manager_key, row, season, net, team_lookup)
            for other in managers_in_trade:
                if other != manager_key:
                    partner = partner_totals[manager_key][other]
                    partner[0] += net
                    partner[1] += 1
    ledgers = tuple(
        _trade_ledger(manager_key, totals[manager_key], names, partner_totals, best, worst)
        for manager_key in sorted(totals)
    )
    return _TradeData(
        per_season={key: (round(value[0], 4), int(value[1])) for key, value in per_season.items()},
        ledgers=ledgers,
    )


def _trade_net_by_manager(
    row: JsonObject,
    season: int,
    team_lookup: dict[tuple[int, int], str],
    vor_model: VorModel,
    position_by_player: dict[int, str],
) -> dict[str, tuple[float, float, float]]:
    received: defaultdict[str, float] = defaultdict(float)
    sent: defaultdict[str, float] = defaultdict(float)
    for side in as_array(row.get("sides"), "sides"):
        if not isinstance(side, dict):
            continue
        for asset in as_array(side.get("receivedAssets"), "receivedAssets"):
            if not isinstance(asset, dict):
                continue
            # Value the asset in VOR over its trade window, not raw points — this is
            # what stops a streamed QB from dominating trade ledgers.
            position = position_by_player.get(int_value(asset.get("playerId")), "")
            weekly = asset.get("weeklyPoints")
            if not isinstance(weekly, dict):
                continue
            value, _ = vor_model.value_for_weeks(season, position, weekly)
            to_manager = team_lookup.get((season, int_value(asset.get("toTeamId"))))
            from_manager = team_lookup.get((season, int_value(asset.get("fromTeamId"))))
            if to_manager:
                received[to_manager] += value
            if from_manager:
                sent[from_manager] += value
    managers = set(received) | set(sent)
    return {
        manager: (
            round(received[manager] - sent[manager], 4),
            round(received[manager], 4),
            round(sent[manager], 4),
        )
        for manager in managers
    }


def _track_extreme(
    best: dict[str, JsonObject],
    worst: dict[str, JsonObject],
    manager_key: str,
    row: JsonObject,
    season: int,
    net: float,
    team_lookup: dict[tuple[int, int], str],
) -> None:
    entry: JsonObject = {
        "tradeId": string_value(row.get("tradeId")),
        "season": season,
        "netPoints": net,
        "summary": _trade_summary(row, manager_key, team_lookup),
    }
    if manager_key not in best or net > float_value(best[manager_key].get("netPoints")):
        best[manager_key] = entry
    if manager_key not in worst or net < float_value(worst[manager_key].get("netPoints")):
        worst[manager_key] = entry


def _trade_summary(
    row: JsonObject,
    manager_key: str,
    team_lookup: dict[tuple[int, int], str],
) -> str:
    # Receipt from THIS manager's perspective: only the assets *their own side* received.
    # Previously this collected receivedAssets across every side, so both sides of a
    # trade listed the same players (the "both acquired the same four" bug).
    season = int_value(row.get("season"))
    received = [
        string_value(asset.get("name"), "Unknown Player")
        for side in as_array(row.get("sides"), "sides")
        if isinstance(side, dict)
        if team_lookup.get((season, int_value(side.get("teamId")))) == manager_key
        for asset in as_array(side.get("receivedAssets"), "receivedAssets")
        if isinstance(asset, dict)
    ]
    label = ", ".join(received[:4]) if received else "assets"
    return f"{season}: acquired {label}" if manager_key else label


def _trade_ledger(
    manager_key: str,
    totals: _TradeTotals,
    names: dict[str, str],
    partner_totals: dict[str, defaultdict[str, list[float]]],
    best: dict[str, JsonObject],
    worst: dict[str, JsonObject],
) -> ManagerTradeLedger:
    partners = tuple(
        TradePartner(
            manager_key=other,
            display_name=names.get(other, other),
            trade_count=int(value[1]),
            net_points=round(value[0], 4),
        )
        for other, value in sorted(
            partner_totals.get(manager_key, _NO_PARTNERS).items(),
            key=lambda item: (-item[1][1], item[0]),
        )
    )
    return ManagerTradeLedger(
        manager_key=manager_key,
        display_name=names.get(manager_key, manager_key),
        trade_count=totals.trade_count,
        net_points=round(totals.net_points, 4),
        received_points=round(totals.received_points, 4),
        sent_points=round(totals.sent_points, 4),
        best_trade=best.get(manager_key),
        worst_trade=worst.get(manager_key),
        partners=partners,
    )


def _waiver_values(
    reader: FixtureReader,
    names: dict[str, str],
    vor_model: VorModel,
) -> _WaiverData:
    per_season: defaultdict[tuple[str, int], list[float]] = defaultdict(lambda: [0.0, 0.0])
    totals: defaultdict[str, _WaiverTotals] = defaultdict(_WaiverTotals)
    best: dict[str, JsonObject] = {}
    worst: dict[str, JsonObject] = {}
    for row in waiver_move_rows(reader, vor_model):
        if row.get("scoreEligible") is not True:
            continue
        manager_key = string_value(row.get("managerKey"))
        if not manager_key:
            continue
        season = int_value(row.get("season"))
        # Waiver value is measured in VOR, consistent with trade value and the grades.
        net = float_value(row.get("netVor"))
        added = float_value(row.get("addedRestOfSeasonVor"))
        dropped = float_value(row.get("droppedRestOfSeasonVor"))
        bucket = per_season[(manager_key, season)]
        bucket[0] += net
        bucket[1] += 1
        total = totals[manager_key]
        total.eligible_moves += 1
        total.net_points += net
        total.added_points += added
        total.dropped_points += dropped
        _track_waiver_extreme(best, worst, manager_key, row, season, added, dropped)
    ledgers = tuple(
        _waiver_ledger(manager_key, totals[manager_key], names, best, worst)
        for manager_key in sorted(totals)
    )
    return _WaiverData(
        per_season={key: (round(value[0], 4), int(value[1])) for key, value in per_season.items()},
        ledgers=ledgers,
    )


def _track_waiver_extreme(
    best: dict[str, JsonObject],
    worst: dict[str, JsonObject],
    manager_key: str,
    row: JsonObject,
    season: int,
    added: float,
    dropped: float,
) -> None:
    added_names = _player_names(row.get("addedPlayers"))
    dropped_names = _player_names(row.get("droppedPlayers"))
    move_id = f"waiver:{season}:{string_value(row.get('sourceTransactionId'))}"
    if manager_key not in best or added > float_value(best[manager_key].get("points")):
        best[manager_key] = {
            "moveId": move_id,
            "season": season,
            "points": round(added, 4),
            "summary": f"{season}: added {added_names}",
        }
    if manager_key not in worst or dropped > float_value(worst[manager_key].get("points")):
        worst[manager_key] = {
            "moveId": move_id,
            "season": season,
            "points": round(dropped, 4),
            "summary": f"{season}: dropped {dropped_names}",
        }


def _player_names(value: JsonValue) -> str:
    if not isinstance(value, list):
        return "players"
    names = [
        string_value(player.get("name"), "Unknown Player")
        for player in value
        if isinstance(player, dict)
    ]
    return ", ".join(names[:3]) if names else "players"


def _waiver_ledger(
    manager_key: str,
    totals: _WaiverTotals,
    names: dict[str, str],
    best: dict[str, JsonObject],
    worst: dict[str, JsonObject],
) -> ManagerWaiverLedger:
    return ManagerWaiverLedger(
        manager_key=manager_key,
        display_name=names.get(manager_key, manager_key),
        eligible_moves=totals.eligible_moves,
        net_points=round(totals.net_points, 4),
        added_points=round(totals.added_points, 4),
        dropped_points=round(totals.dropped_points, 4),
        best_pickup=best.get(manager_key),
        worst_drop=worst.get(manager_key),
    )


def _season_values(
    trade_per_season: dict[tuple[str, int], tuple[float, int]],
    waiver_per_season: dict[tuple[str, int], tuple[float, int]],
) -> tuple[ManagerSeasonValue, ...]:
    keys = set(trade_per_season) | set(waiver_per_season)
    rows = [
        ManagerSeasonValue(
            manager_key=manager_key,
            season=season,
            trade_net_points=trade_per_season.get((manager_key, season), (0.0, 0))[0],
            trade_count=trade_per_season.get((manager_key, season), (0.0, 0))[1],
            waiver_net_points=waiver_per_season.get((manager_key, season), (0.0, 0))[0],
            waiver_count=waiver_per_season.get((manager_key, season), (0.0, 0))[1],
        )
        for manager_key, season in sorted(keys)
    ]
    return tuple(rows)


def manager_value_for_fixture(reader: FixtureReader) -> ManagerValueResult:
    managers, team_seasons = load_team_seasons(reader)
    return manager_value(reader, managers, team_seasons)
