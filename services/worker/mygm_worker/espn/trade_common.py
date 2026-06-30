from __future__ import annotations

# pyright: reportAny=false, reportArgumentType=false, reportAttributeAccessIssue=false, reportCallIssue=false, reportExplicitAny=false, reportImplicitStringConcatenation=false, reportImportCycles=false, reportOperatorIssue=false, reportUnannotatedClassAttribute=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnnecessaryIsInstance=false, reportUnusedCallResult=false
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

GRADE_THRESHOLDS = [
    (60, "A+"),
    (40, "A"),
    (25, "B+"),
    (10, "B"),
    (-10, "C"),
    (-25, "D"),
    (-40, "D-"),
]


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def season_from_dir(path: Path) -> int:
    return int(path.name.split("_", 1)[1])


def ms_to_iso(value: Any) -> str | None:
    if value is None:
        return None
    try:
        return datetime.fromtimestamp(int(value) / 1000, tz=UTC).isoformat()
    except (TypeError, ValueError, OSError):
        return None


def grade_for_net(net_points: float | None) -> str | None:
    if net_points is None:
        return None
    for threshold, grade in GRADE_THRESHOLDS:
        if net_points > threshold:
            return grade
    return "F"


def team_display_name(team: dict[str, Any]) -> str:
    name = team.get("name")
    if name:
        return str(name).strip()
    location = team.get("location")
    nickname = team.get("nickname")
    if location or nickname:
        return " ".join(str(part).strip() for part in [location, nickname] if part).strip()
    abbrev = team.get("abbrev")
    if abbrev:
        return str(abbrev).strip()
    team_id = team.get("id")
    return f"Team {team_id}" if team_id is not None else "Unknown Team"
