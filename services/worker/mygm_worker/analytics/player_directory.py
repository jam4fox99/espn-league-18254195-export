from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Final

from mygm_worker.analytics.json_tools import (
    as_object,
    int_value,
    object_field,
    read_json,
    string_value,
)

if TYPE_CHECKING:
    from pathlib import Path

    from mygm_worker.analytics.models import JsonObject, JsonValue
    from mygm_worker.analytics.reader import FixtureReader

# ESPN proTeamId -> NFL abbreviation. 0 means "no team" / free agent.
PRO_TEAM_ABBREV: Final[dict[int, str]] = {
    0: "",
    1: "ATL",
    2: "BUF",
    3: "CHI",
    4: "CIN",
    5: "CLE",
    6: "DAL",
    7: "DEN",
    8: "DET",
    9: "GB",
    10: "TEN",
    11: "IND",
    12: "KC",
    13: "LV",
    14: "LAR",
    15: "MIA",
    16: "MIN",
    17: "NE",
    18: "NO",
    19: "NYG",
    20: "NYJ",
    21: "PHI",
    22: "ARI",
    23: "PIT",
    24: "LAC",
    25: "SF",
    26: "SEA",
    27: "TB",
    28: "WSH",
    29: "CAR",
    30: "JAX",
    33: "BAL",
    34: "HOU",
}

# ESPN defaultPositionId -> fantasy position label.
POSITIONS: Final[dict[int, str]] = {1: "QB", 2: "RB", 3: "WR", 4: "TE", 5: "K", 16: "D/ST"}

# NFL team nickname -> abbreviation, used as a last-resort fallback for D/ST entries
# whose proTeamId never surfaces in the box scores or the encoded id.
_NICKNAME_ABBREV: Final[dict[str, str]] = {
    "FALCONS": "ATL",
    "BILLS": "BUF",
    "BEARS": "CHI",
    "BENGALS": "CIN",
    "BROWNS": "CLE",
    "COWBOYS": "DAL",
    "BRONCOS": "DEN",
    "LIONS": "DET",
    "PACKERS": "GB",
    "TITANS": "TEN",
    "COLTS": "IND",
    "CHIEFS": "KC",
    "RAIDERS": "LV",
    "RAMS": "LAR",
    "DOLPHINS": "MIA",
    "VIKINGS": "MIN",
    "PATRIOTS": "NE",
    "SAINTS": "NO",
    "GIANTS": "NYG",
    "JETS": "NYJ",
    "EAGLES": "PHI",
    "CARDINALS": "ARI",
    "STEELERS": "PIT",
    "CHARGERS": "LAC",
    "49ERS": "SF",
    "SEAHAWKS": "SEA",
    "BUCCANEERS": "TB",
    "COMMANDERS": "WSH",
    "FOOTBALL": "WSH",
    "PANTHERS": "CAR",
    "JAGUARS": "JAX",
    "RAVENS": "BAL",
    "TEXANS": "HOU",
}

# ESPN encodes team defenses as negative ids of the form -(16000 + proTeamId).
_DST_ID_BASE: Final = 16000


@dataclass(frozen=True, slots=True)
class PlayerDirectoryEntry:
    player_id: int
    name: str
    position: str
    pro_team_abbrev: str
    latest_season: int
    is_dst: bool
    # Career "signature" label (see analytics/player_badges.py); "" when none.
    badge: str = ""


@dataclass(slots=True)
class _PlayerAccumulator:
    player_id: int
    box_name: str = ""
    box_position_id: int = 0
    box_pro_team_id: int = 0
    box_latest_key: tuple[int, int] = (-1, -1)
    flat_name: str = ""
    flat_position_id: int = 0
    flat_position_text: str = ""
    flat_latest_key: tuple[int, int] = (-1, -1)
    latest_season: int = 0
    seasons: set[int] = field(default_factory=set)


def build_player_directory(reader: FixtureReader) -> dict[int, PlayerDirectoryEntry]:
    accumulators: dict[int, _PlayerAccumulator] = {}
    for season in reader.seasons():
        for row in _box_score_player_rows(reader.root, season.season):
            _absorb_box_row(accumulators, row)
    for row in _flat_lookup_rows(reader.root):
        _absorb_flat_row(accumulators, row)
    return {
        player_id: _finalize(acc)
        for player_id, acc in sorted(accumulators.items())
    }


def player_directory_json(directory: dict[int, PlayerDirectoryEntry]) -> JsonObject:
    return {
        str(entry.player_id): _entry_json(entry)
        for entry in sorted(directory.values(), key=lambda item: item.player_id)
    }


def _entry_json(entry: PlayerDirectoryEntry) -> JsonObject:
    row: JsonObject = {
        "playerId": entry.player_id,
        "name": entry.name,
        "position": entry.position,
        "proTeamAbbrev": entry.pro_team_abbrev,
        "latestSeason": entry.latest_season,
        "isDST": entry.is_dst,
    }
    if entry.badge:
        row["badge"] = entry.badge
    return row


def enrich_player_row(
    row: JsonObject,
    directory: dict[int, PlayerDirectoryEntry],
) -> JsonObject:
    """Attach proTeamAbbrev/isDST/position to a row that already carries ``playerId``."""
    player_id = row.get("playerId")
    if not isinstance(player_id, int) or isinstance(player_id, bool):
        return row
    entry = directory.get(player_id)
    row["proTeamAbbrev"] = "" if entry is None else entry.pro_team_abbrev
    row["isDST"] = player_id < 0 if entry is None else entry.is_dst
    existing = row.get("position")
    if not (isinstance(existing, str) and existing):
        row["position"] = "" if entry is None else entry.position
    if entry is not None and entry.badge:
        row["badge"] = entry.badge
    return row


@dataclass(frozen=True, slots=True)
class _BoxRow:
    player_id: int
    name: str
    position_id: int
    pro_team_id: int
    season: int
    week: int


@dataclass(frozen=True, slots=True)
class _FlatRow:
    player_id: int
    name: str
    position_id: int
    position_text: str
    season: int
    week: int


def _absorb_box_row(accumulators: dict[int, _PlayerAccumulator], row: _BoxRow) -> None:
    acc = accumulators.setdefault(row.player_id, _PlayerAccumulator(player_id=row.player_id))
    acc.seasons.add(row.season)
    acc.latest_season = max(acc.latest_season, row.season)
    key = (row.season, row.week)
    if key >= acc.box_latest_key:
        acc.box_latest_key = key
        acc.box_name = row.name or acc.box_name
        acc.box_position_id = row.position_id or acc.box_position_id
        acc.box_pro_team_id = row.pro_team_id


def _absorb_flat_row(accumulators: dict[int, _PlayerAccumulator], row: _FlatRow) -> None:
    acc = accumulators.setdefault(row.player_id, _PlayerAccumulator(player_id=row.player_id))
    acc.seasons.add(row.season)
    acc.latest_season = max(acc.latest_season, row.season)
    key = (row.season, row.week)
    if key >= acc.flat_latest_key:
        acc.flat_latest_key = key
        acc.flat_name = row.name or acc.flat_name
        acc.flat_position_id = row.position_id or acc.flat_position_id
        acc.flat_position_text = row.position_text or acc.flat_position_text


def _finalize(acc: _PlayerAccumulator) -> PlayerDirectoryEntry:
    is_dst = acc.player_id < 0
    name = acc.box_name or acc.flat_name or f"Player {acc.player_id}"
    position_id = acc.box_position_id or acc.flat_position_id
    position = POSITIONS.get(position_id, "")
    if not position:
        position = acc.flat_position_text or ("D/ST" if is_dst else "")
    return PlayerDirectoryEntry(
        player_id=acc.player_id,
        name=name,
        position=position,
        pro_team_abbrev=_resolve_abbrev(acc, is_dst=is_dst),
        latest_season=acc.latest_season,
        is_dst=is_dst,
    )


def _resolve_abbrev(acc: _PlayerAccumulator, *, is_dst: bool) -> str:
    if acc.box_pro_team_id:
        return PRO_TEAM_ABBREV.get(acc.box_pro_team_id, "")
    if is_dst:
        return _dst_abbrev(acc.player_id, acc.box_name or acc.flat_name)
    return ""


def _dst_abbrev(player_id: int, name: str) -> str:
    encoded = abs(player_id) - _DST_ID_BASE
    abbrev = PRO_TEAM_ABBREV.get(encoded)
    if abbrev:
        return abbrev
    for token in name.upper().replace("/", " ").split():
        nickname = _NICKNAME_ABBREV.get(token)
        if nickname:
            return nickname
    return ""


def _box_score_player_rows(root: Path, season: int) -> list[_BoxRow]:
    season_dir = root / f"season_{season}"
    if not season_dir.is_dir():
        return []
    rows: list[_BoxRow] = []
    for week_path in sorted((season_dir / "box_scores").glob("week_*.json")):
        week = _week_from_path(week_path.stem)
        payload = as_object(read_json(week_path), str(week_path))
        data = object_field(payload, "data")
        schedules = data.get("schedule")
        if not isinstance(schedules, list):
            continue
        for matchup in schedules:
            if isinstance(matchup, dict):
                rows.extend(_matchup_player_rows(matchup, season, week))
    return rows


def _matchup_player_rows(matchup: JsonObject, season: int, week: int) -> list[_BoxRow]:
    rows: list[_BoxRow] = []
    for side_name in ("home", "away"):
        side = matchup.get(side_name)
        if not isinstance(side, dict):
            continue
        roster = side.get("rosterForCurrentScoringPeriod")
        if not isinstance(roster, dict):
            continue
        entries = roster.get("entries")
        if not isinstance(entries, list):
            continue
        for raw in entries:
            row = _box_entry_row(raw, season, week)
            if row is not None:
                rows.append(row)
    return rows


def _box_entry_row(raw: JsonValue, season: int, week: int) -> _BoxRow | None:
    if not isinstance(raw, dict):
        return None
    pool = raw.get("playerPoolEntry")
    if not isinstance(pool, dict):
        return None
    player = pool.get("player")
    if not isinstance(player, dict):
        return None
    player_id = int_value(player.get("id"))
    if player_id == 0:
        return None
    return _BoxRow(
        player_id=player_id,
        name=string_value(player.get("fullName")),
        position_id=int_value(player.get("defaultPositionId")),
        pro_team_id=int_value(player.get("proTeamId")),
        season=season,
        week=week,
    )


def _flat_lookup_rows(root: Path) -> list[_FlatRow]:
    path = root / "player_lookup" / "player_weekly_points_flat.json"
    if not path.exists():
        return []
    value = read_json(path)
    if not isinstance(value, list):
        return []
    rows: list[_FlatRow] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        player_id = int_value(item.get("playerId"))
        if player_id == 0:
            continue
        rows.append(
            _FlatRow(
                player_id=player_id,
                name=string_value(item.get("name")),
                position_id=int_value(item.get("defaultPositionId")),
                position_text=string_value(item.get("defaultPosition")),
                season=int_value(item.get("season")),
                week=int_value(item.get("week")),
            )
        )
    return rows


def _week_from_path(stem: str) -> int:
    _, _, tail = stem.partition("_")
    return int_value(tail)
