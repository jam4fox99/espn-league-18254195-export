from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from mygm_worker.analytics.team_logos import build_logo_index

if TYPE_CHECKING:
    from mygm_worker.analytics.models import JsonObject


@dataclass(frozen=True, slots=True)
class _FakeSeason:
    season: int


@dataclass(slots=True)
class _FakeReader:
    cores: dict[int, list[JsonObject]]

    def seasons(self) -> tuple[_FakeSeason, ...]:
        return tuple(_FakeSeason(season) for season in sorted(self.cores))

    def core(self, season: int) -> JsonObject:
        return {"teams": list(self.cores[season])}


def _team(owner: str, logo: str, *, team_id: int = 1) -> JsonObject:
    return {"id": team_id, "primaryOwner": owner, "logo": logo}


def test_main_logo_tracks_latest_season_owner_fielded_a_team() -> None:
    reader = _FakeReader(
        {
            2020: [_team("{OWNER-A}", "logo-2020.png")],
            2021: [_team("{OWNER-A}", "logo-2021.png")],
            2024: [_team("{OWNER-A}", "logo-2024.png")],
        },
    )

    index = build_logo_index(reader)  # pyright: ignore[reportArgumentType]

    logo = index["espn-owner:{OWNER-A}"]
    assert logo["mainSeason"] == 2024
    assert logo["main"] == "logo-2024.png"
    assert logo["bySeason"] == {
        "2020": "logo-2020.png",
        "2021": "logo-2021.png",
        "2024": "logo-2024.png",
    }


def test_departed_owner_keeps_their_final_season_logo() -> None:
    reader = _FakeReader(
        {
            2020: [_team("{GONE}", "gone-2020.png"), _team("{HERE}", "here-2020.png", team_id=2)],
            2021: [_team("{HERE}", "here-2021.png", team_id=2)],
        },
    )

    index = build_logo_index(reader)  # pyright: ignore[reportArgumentType]

    assert index["espn-owner:{GONE}"]["mainSeason"] == 2020
    assert index["espn-owner:{GONE}"]["main"] == "gone-2020.png"
    assert index["espn-owner:{HERE}"]["mainSeason"] == 2021


def test_unresolved_owner_receives_no_logo_entry() -> None:
    reader = _FakeReader(
        {
            2020: [
                {"id": 7, "logo": "orphan.png"},  # no primaryOwner / owners.
                _team("{REAL}", "real.png", team_id=8),
            ],
        },
    )

    index = build_logo_index(reader)  # pyright: ignore[reportArgumentType]

    assert set(index) == {"espn-owner:{REAL}"}


def test_owner_falls_back_to_first_owners_entry_when_primary_missing() -> None:
    reader = _FakeReader(
        {2020: [{"id": 3, "owners": ["{FALLBACK}"], "logo": "fb.png"}]},
    )

    index = build_logo_index(reader)  # pyright: ignore[reportArgumentType]

    assert index["espn-owner:{FALLBACK}"]["main"] == "fb.png"


def test_season_without_logo_is_omitted_from_by_season_but_counts_for_main() -> None:
    reader = _FakeReader(
        {
            2020: [_team("{OWNER}", "had-logo.png")],
            2021: [_team("{OWNER}", "")],  # empty logo string.
        },
    )

    index = build_logo_index(reader)  # pyright: ignore[reportArgumentType]

    logo = index["espn-owner:{OWNER}"]
    assert logo["mainSeason"] == 2021  # latest fielded season, even without a logo.
    assert logo["main"] is None
    assert logo["bySeason"] == {"2020": "had-logo.png"}
