from dataclasses import dataclass
from typing import cast
from uuid import UUID

from mygm_api.models import LeagueId, VersionId
from mygm_api.schemas import (
    AvailableSeasonsResponse,
    DashboardResponse,
    HistoryChampionResponse,
    HistorySeasonResponse,
    LeagueAnalyticsSnapshotResponse,
    LeagueHistoryResponse,
    LeagueNewsResponse,
    ManagerDirectoryEntry,
    ManagerDirectoryResponse,
    ManagerHubResponse,
    ManagerProfileResponse,
    PlayerLeaderboardsResponse,
    RivalryMatrixResponse,
    SeasonHubResponse,
    SnapshotDataHealthResponse,
    SnapshotDetailResponse,
    SnapshotFormulaResponse,
    SnapshotHeadToHeadResponse,
    SnapshotJsonObject,
    SnapshotJsonValue,
    SnapshotLeaderboardsResponse,
    SnapshotManagerResponse,
    SnapshotRowsResponse,
)
from mygm_api.score_models import CURRENT_VERSION_ALIAS
from mygm_api.store import ApiStore


@dataclass(frozen=True, slots=True)
class LeagueAnalyticsSnapshot:
    version_id: VersionId
    snapshot: LeagueAnalyticsSnapshotResponse


class SnapshotAnalyticsRepository:
    def get(
        self,
        api_store: ApiStore,
        league_id: LeagueId,
        requested_version: str,
    ) -> LeagueAnalyticsSnapshot | None:
        version_id = self._resolve_version(api_store, league_id, requested_version)
        if version_id is None:
            return None
        snapshot = api_store.analytics_snapshots.get((league_id, version_id))
        if snapshot is None:
            return None
        return LeagueAnalyticsSnapshot(version_id=version_id, snapshot=snapshot)

    def dashboard(self, current: LeagueAnalyticsSnapshot, league_uuid: UUID) -> DashboardResponse:
        snapshot = current.snapshot
        labels = self._label_map(snapshot)
        return DashboardResponse(
            leagueId=league_uuid,
            version=str(current.version_id),
            payloadVersion=snapshot.meta.snapshot_version,
            productLabel=snapshot.meta.product_label,
            importStatus=snapshot.meta.import_status,
            compositeScore=self._composite_score(snapshot),
            sourceCounts=snapshot.data_health.source_counts,
            careerExcludedSeasons=snapshot.data_health.career_excluded_seasons,
            leaderboard=[
                self._labelled(row.model_dump(by_alias=True), row.manager_key, labels)
                for row in snapshot.leaderboards.all_time
            ],
        )

    def available_seasons(self, current: LeagueAnalyticsSnapshot) -> AvailableSeasonsResponse:
        return AvailableSeasonsResponse(
            seasons=[season.season for season in current.snapshot.seasons],
        )

    def history(self, current: LeagueAnalyticsSnapshot) -> LeagueHistoryResponse:
        raw_seasons = [season.model_dump(by_alias=True) for season in current.snapshot.seasons]
        years = [_require_int(season.get("season")) for season in raw_seasons]
        span = ""
        if years:
            span = (
                str(min(years))
                if min(years) == max(years)
                else f"{min(years)}\u2013{max(years)}"
            )
        ordered = sorted(
            raw_seasons,
            key=lambda season: _require_int(season.get("season")),
            reverse=True,
        )
        return LeagueHistoryResponse(
            span=span,
            seasonCount=len(raw_seasons),
            seasons=[self._history_season(season) for season in ordered],
            champions=self._champion_counts(raw_seasons),
        )

    def player_leaderboards(
        self,
        current: LeagueAnalyticsSnapshot,
    ) -> PlayerLeaderboardsResponse:
        extra = current.snapshot.model_extra or {}
        boards = extra.get("playerLeaderboards")
        typed = cast("SnapshotJsonObject", boards) if isinstance(boards, dict) else {}
        efficiency = extra.get("lineupEfficiency")
        efficiency_typed = (
            cast("SnapshotJsonObject", efficiency) if isinstance(efficiency, dict) else {}
        )
        return PlayerLeaderboardsResponse(
            topWeeks=_as_dict_list(typed.get("topWeeks")),
            topSeasons=_as_dict_list(typed.get("topSeasons")),
            lineupEfficiency=_as_dict_list(efficiency_typed.get("seasons")),
            playerDirectory=_as_dict_map(extra.get("playerDirectory")),
        )

    def rivalries(self, current: LeagueAnalyticsSnapshot) -> RivalryMatrixResponse:
        extra = current.snapshot.model_extra or {}
        section = extra.get("rivalries")
        if not isinstance(section, dict):
            return RivalryMatrixResponse()
        typed = cast("SnapshotJsonObject", section)
        return RivalryMatrixResponse(
            managers=_as_dict_list(typed.get("managers")),
            edges=_as_dict_list(typed.get("edges")),
            summaries=_as_dict_list(typed.get("summaries")),
        )

    def season_hub(
        self,
        current: LeagueAnalyticsSnapshot,
        season_year: int,
    ) -> SeasonHubResponse:
        raw = next(
            (
                season.model_dump(by_alias=True)
                for season in current.snapshot.seasons
                if season.season == season_year
            ),
            None,
        )
        if raw is None:
            raise KeyError(season_year)
        raw = cast("SnapshotJsonObject", raw)
        labels = self._label_map(current.snapshot)
        ratings = [
            self._labelled(row.model_dump(by_alias=True), row.manager_key, labels)
            for row in current.snapshot.leaderboards.by_season
            if row.season == season_year
        ]
        standings = _as_dict_list(raw.get("finalStandings"))
        draft_recap = self._draft_recap_summary(raw.get("draftRecap"))
        superlatives = _as_dict_list(raw.get("superlatives"))
        champion = _as_dict(raw.get("champion"))
        runner_up = _as_dict(raw.get("runnerUp"))
        is_partial = bool(raw.get("isPartial", False))
        return SeasonHubResponse(
            season=season_year,
            isPartial=is_partial,
            finalWeek=_as_int(raw.get("finalWeek")),
            transactionCount=_as_int(raw.get("transactionCount")),
            playoffTeamCount=_as_int(raw.get("playoffTeamCount")),
            champion=champion,
            runnerUp=runner_up,
            finalStandings=standings,
            draftRecap=draft_recap,
            superlatives=superlatives,
            ratings=ratings,
            review=_season_review(
                is_partial=is_partial,
                champion=champion,
                runner_up=runner_up,
                standings=standings,
                draft_recap=draft_recap,
                transaction_count=_as_int(raw.get("transactionCount")),
            ),
        )

    def _draft_recap_summary(self, recap: object) -> SnapshotJsonObject:
        if not isinstance(recap, dict):
            return {}
        typed = cast("SnapshotJsonObject", recap)
        return {
            "bestSteal": typed.get("bestSteal"),
            "biggestBust": typed.get("biggestBust"),
            "pickCount": typed.get("pickCount"),
            "isPartial": typed.get("isPartial"),
        }

    def managers_directory(self, current: LeagueAnalyticsSnapshot) -> ManagerDirectoryResponse:
        rating = {row.manager_key: row for row in current.snapshot.leaderboards.all_time}
        entries: list[ManagerDirectoryEntry] = []
        for manager in current.snapshot.managers:
            career = self._manager_section(manager, "career")
            row = rating.get(manager.manager_key)
            extra = manager.model_extra or {}
            entries.append(
                ManagerDirectoryEntry(
                    managerKey=manager.manager_key,
                    displayName=manager.display_name,
                    latestTeamName=_latest_team_name(manager),
                    seasonsPlayed=_as_int(career.get("seasonsPlayed")),
                    titles=_as_int(career.get("titles")),
                    winPct=_as_float(career.get("winPct")),
                    bestFinish=_as_int(career.get("bestFinish")),
                    careerRating=row.score if row is not None else None,
                    logo=_as_dict(extra.get("logo")),
                    signaturePlayer=_as_dict(extra.get("signaturePlayer")),
                ),
            )
        entries.sort(
            key=lambda entry: (entry.career_rating is None, -(entry.career_rating or 0.0)),
        )
        return ManagerDirectoryResponse(managers=entries)

    def manager_hub(
        self,
        current: LeagueAnalyticsSnapshot,
        manager_key: str,
    ) -> ManagerHubResponse:
        manager = self._manager(current.snapshot, manager_key)
        row = next(
            (
                item
                for item in current.snapshot.leaderboards.all_time
                if item.manager_key == manager_key
            ),
            None,
        )
        components = _component_breakdown(row.components) if row is not None else {}
        return ManagerHubResponse(
            managerKey=manager.manager_key,
            displayName=manager.display_name,
            teamAliases=[alias.model_dump(by_alias=True) for alias in manager.team_aliases],
            scoreEligible=manager.score_eligible,
            caveats=manager.caveats,
            careerRating=row.score if row is not None else None,
            ratingComponents=components,
            career=self._manager_section(manager, "career"),
            value=self._manager_section(manager, "value"),
            rivalry=self._manager_section(manager, "rivalry"),
            archetype=self._manager_section(manager, "archetype"),
            draftCard=self._manager_section(manager, "draftCard"),
            rosterHistory=self._manager_section(manager, "rosterHistory"),
        )

    def _manager_section(
        self,
        manager: SnapshotManagerResponse,
        key: str,
    ) -> SnapshotJsonObject:
        extra = manager.model_extra or {}
        section = extra.get(key)
        if isinstance(section, dict):
            return cast("SnapshotJsonObject", section)
        return {}

    def _history_season(self, season: SnapshotJsonObject) -> HistorySeasonResponse:
        champion = season.get("champion")
        champion = champion if isinstance(champion, dict) else None
        runner_up = season.get("runnerUp")
        runner_up = runner_up if isinstance(runner_up, dict) else None
        superlatives = season.get("superlatives")
        sup_list = (
            [item for item in superlatives if isinstance(item, dict)]
            if isinstance(superlatives, list)
            else []
        )
        is_partial = bool(season.get("isPartial", False))
        return HistorySeasonResponse(
            season=_require_int(season.get("season")),
            isPartial=is_partial,
            finalWeek=_as_int(season.get("finalWeek")),
            transactionCount=_as_int(season.get("transactionCount")),
            champion=champion,
            runnerUp=runner_up,
            headline=_history_headline(is_partial, champion, _as_int(season.get("finalWeek"))),
            superlatives=sup_list,
        )

    def _champion_counts(
        self,
        raw_seasons: list[SnapshotJsonObject],
    ) -> list[HistoryChampionResponse]:
        counts: dict[str, dict[str, str | int]] = {}
        for season in raw_seasons:
            champion = season.get("champion")
            if not isinstance(champion, dict):
                continue
            key = champion.get("managerKey")
            if not isinstance(key, str):
                continue
            display = champion.get("displayName")
            entry = counts.setdefault(
                key,
                {"displayName": display if isinstance(display, str) else key, "titles": 0},
            )
            entry["titles"] = int(entry["titles"]) + 1
        return [
            HistoryChampionResponse(
                managerKey=key,
                displayName=str(value["displayName"]),
                titles=int(value["titles"]),
            )
            for key, value in sorted(
                counts.items(),
                key=lambda item: (-int(item[1]["titles"]), str(item[1]["displayName"])),
            )
        ]

    def leaderboard(
        self,
        current: LeagueAnalyticsSnapshot,
        scope: str,
        formula: str | None = None,
    ) -> SnapshotRowsResponse:
        leaderboards = self._leaderboards_for(current.snapshot, formula)
        rows = leaderboards.all_time
        if scope != "all_time":
            rows = leaderboards.by_season
        labels = self._label_map(current.snapshot)
        return self._rows(
            current,
            model_name="leaderboard",
            rows=[
                self._labelled(row.model_dump(by_alias=True), row.manager_key, labels)
                for row in rows
            ],
        )

    def season(
        self,
        current: LeagueAnalyticsSnapshot,
        season_year: int,
        formula: str | None = None,
    ) -> SnapshotRowsResponse:
        labels = self._label_map(current.snapshot)
        leaderboards = self._leaderboards_for(current.snapshot, formula)
        rows = [
            self._labelled(row.model_dump(by_alias=True), row.manager_key, labels)
            for row in leaderboards.by_season
            if row.season == season_year
        ]
        return self._rows(current, model_name="season", rows=rows)

    def manager(
        self,
        current: LeagueAnalyticsSnapshot,
        manager_key: str,
        formula: str | None = None,
    ) -> ManagerProfileResponse:
        manager = self._manager(current.snapshot, manager_key)
        leaderboards = self._leaderboards_for(current.snapshot, formula)
        row = next(
            (row for row in leaderboards.all_time if row.manager_key == manager_key),
            None,
        )
        return ManagerProfileResponse(
            managerKey=manager.manager_key,
            displayName=manager.display_name,
            teamAliases=manager.team_aliases,
            scoreEligible=manager.score_eligible,
            caveats=manager.caveats,
            compositeScore=row.score if row is not None else None,
            confidence=row.confidence if row is not None else None,
            componentBreakdown=_component_breakdown(row.components) if row is not None else {},
            archetype=self._manager_section(manager, "archetype"),
        )

    def trades(self, current: LeagueAnalyticsSnapshot) -> SnapshotRowsResponse:
        labels = self._label_map(current.snapshot)
        return self._rows(
            current,
            model_name="trades",
            rows=[
                self._labelled_managers(row.model_dump(by_alias=True), row.manager_keys, labels)
                for row in current.snapshot.trades.items
            ],
        )

    def trade_detail(
        self,
        current: LeagueAnalyticsSnapshot,
        trade_id: str,
    ) -> SnapshotDetailResponse | None:
        for row in current.snapshot.trades.items:
            if row.trade_id == trade_id:
                return SnapshotDetailResponse(item=row.model_dump(by_alias=True))
        return None

    def waivers(self, current: LeagueAnalyticsSnapshot) -> SnapshotRowsResponse:
        labels = self._label_map(current.snapshot)
        return self._rows(
            current,
            model_name="waivers",
            rows=[
                self._labelled(row.model_dump(by_alias=True), row.manager_key, labels)
                for row in current.snapshot.waivers.items
            ],
            waiver_superlatives=_waiver_superlatives(current.snapshot),
        )

    def waiver_detail(
        self,
        current: LeagueAnalyticsSnapshot,
        waiver_id: str,
    ) -> SnapshotDetailResponse | None:
        for row in current.snapshot.waivers.items:
            if row.move_id == waiver_id:
                return SnapshotDetailResponse(item=row.model_dump(by_alias=True))
        return None

    def records(self, current: LeagueAnalyticsSnapshot) -> SnapshotRowsResponse:
        labels = self._label_map(current.snapshot)
        return self._rows(
            current,
            model_name="records",
            rows=[
                self._labelled(row.model_dump(by_alias=True), row.manager_key, labels)
                for row in current.snapshot.records.items
            ],
        )

    def head_to_head(
        self,
        current: LeagueAnalyticsSnapshot,
        season: str,
        manager_a: str,
        manager_b: str,
    ) -> SnapshotHeadToHeadResponse:
        pairs = [
            pair
            for pair in current.snapshot.head_to_head.pairs
            if {pair.manager_a_key, pair.manager_b_key} == {manager_a, manager_b}
        ]
        if season == "all":
            return SnapshotHeadToHeadResponse(pairs=pairs)
        season_year = int(season)
        filtered = [
            pair.model_copy(
                update={
                    "matchups": [
                        matchup
                        for matchup in pair.matchups
                        if matchup.get("season") == season_year
                    ],
                },
            )
            for pair in pairs
        ]
        return SnapshotHeadToHeadResponse(pairs=filtered)

    def data_health(self, current: LeagueAnalyticsSnapshot) -> SnapshotDataHealthResponse:
        return current.snapshot.data_health

    def formula(self, current: LeagueAnalyticsSnapshot) -> SnapshotFormulaResponse:
        return current.snapshot.formula

    def formula_weights(self, current: LeagueAnalyticsSnapshot) -> dict[str, float]:
        return dict(current.snapshot.formula.weights)

    def component_labels(self, current: LeagueAnalyticsSnapshot) -> dict[str, str]:
        extra = current.snapshot.formula.model_extra or {}
        labels = extra.get("componentLabels")
        if isinstance(labels, dict):
            return {str(key): str(value) for key, value in labels.items()}
        return {}

    def news(self, current: LeagueAnalyticsSnapshot) -> LeagueNewsResponse:
        extra = current.snapshot.model_extra or {}
        raw = extra.get("leagueNews")
        if not isinstance(raw, dict):
            return LeagueNewsResponse(season=0)
        news = cast("SnapshotJsonObject", raw)
        season = news.get("season", 0)
        return LeagueNewsResponse(
            season=int(season) if isinstance(season, (int, float)) else 0,
            items=_as_objects(news.get("items")),
            teamStrength=_as_objects(news.get("teamStrength")),
            waiverSuggestions=_as_objects(news.get("waiverSuggestions")),
        )

    def available_formulas(self, current: LeagueAnalyticsSnapshot) -> list[SnapshotJsonObject]:
        extra = current.snapshot.model_extra or {}
        formulas = extra.get("formulas")
        available = formulas.get("available") if isinstance(formulas, dict) else None
        if not isinstance(available, list):
            return []
        summaries: list[SnapshotJsonObject] = []
        for item in available:
            if not isinstance(item, dict):
                continue
            summaries.append(
                {
                    "formulaVersion": item.get("formulaVersion"),
                    "label": item.get("label"),
                    "weights": item.get("weights", {}),
                    "componentLabels": item.get("componentLabels", {}),
                    "deprecated": bool(item.get("deprecated", False)),
                    "caveat": item.get("caveat"),
                },
            )
        return summaries

    def _resolve_version(
        self,
        api_store: ApiStore,
        league_id: LeagueId,
        requested_version: str,
    ) -> VersionId | None:
        if requested_version == CURRENT_VERSION_ALIAS:
            return api_store.current_analytics_version_by_league.get(league_id)
        return VersionId(UUID(requested_version))

    def _rows(
        self,
        current: LeagueAnalyticsSnapshot,
        model_name: str,
        rows: list[SnapshotJsonObject],
        waiver_superlatives: dict[str, SnapshotJsonObject] | None = None,
    ) -> SnapshotRowsResponse:
        return SnapshotRowsResponse(
            modelName=model_name,
            modelVersion=str(current.version_id),
            rows=rows,
            waiverSuperlatives=waiver_superlatives or {},
        )

    def _leaderboards_for(
        self,
        snapshot: LeagueAnalyticsSnapshotResponse,
        formula: str | None,
    ) -> SnapshotLeaderboardsResponse:
        if not formula or formula == snapshot.meta.formula_version:
            return snapshot.leaderboards
        extra = snapshot.model_extra or {}
        formulas = extra.get("formulas")
        available = formulas.get("available") if isinstance(formulas, dict) else None
        if isinstance(available, list):
            for item in available:
                if isinstance(item, dict) and item.get("formulaVersion") == formula:
                    leaderboards = item.get("leaderboards")
                    if isinstance(leaderboards, dict):
                        return SnapshotLeaderboardsResponse.model_validate(leaderboards)
        return snapshot.leaderboards

    def _manager(
        self,
        snapshot: LeagueAnalyticsSnapshotResponse,
        manager_key: str,
    ) -> SnapshotManagerResponse:
        for manager in snapshot.managers:
            if manager.manager_key == manager_key:
                return manager
        raise KeyError(manager_key)

    def _composite_score(self, snapshot: LeagueAnalyticsSnapshotResponse) -> float:
        if not snapshot.leaderboards.all_time:
            return 0.0
        return snapshot.leaderboards.all_time[0].score

    def _label_map(
        self,
        snapshot: LeagueAnalyticsSnapshotResponse,
    ) -> dict[str, dict[str, str | None]]:
        """Map each managerKey to its human display name and latest team name."""
        labels: dict[str, dict[str, str | None]] = {}
        for manager in snapshot.managers:
            team_name: str | None = None
            if manager.team_aliases:
                latest = max(manager.team_aliases, key=lambda alias: alias.season)
                team_name = latest.team_name
            labels[manager.manager_key] = {
                "displayName": manager.display_name,
                "teamName": team_name,
            }
        return labels

    def _labelled(
        self,
        row: SnapshotJsonObject,
        manager_key: str,
        labels: dict[str, dict[str, str | None]],
    ) -> SnapshotJsonObject:
        info = labels.get(manager_key)
        name = info["displayName"] if info else _humanize_manager_key(manager_key)
        row["managerName"] = name
        row["displayName"] = name
        team_name = info["teamName"] if info else None
        if team_name:
            row["teamName"] = team_name
        components = row.pop("components", None)
        if isinstance(components, dict):
            row["componentBreakdown"] = _component_breakdown(components)
        return row

    def _labelled_managers(
        self,
        row: SnapshotJsonObject,
        manager_keys: list[str],
        labels: dict[str, dict[str, str | None]],
    ) -> SnapshotJsonObject:
        names = [
            (labels[key]["displayName"] if key in labels else _humanize_manager_key(key))
            for key in manager_keys
        ]
        row["managerNames"] = names
        sides = row.get("sides")
        if isinstance(sides, list):
            for side in sides:
                if not isinstance(side, dict):
                    continue
                key = side.get("managerKey")
                info = labels.get(key) if isinstance(key, str) else None
                side["managerName"] = (
                    info["displayName"] if info else _humanize_manager_key(key or "")
                )
                if info and info["teamName"]:
                    side["teamName"] = info["teamName"]
        return row


def _humanize_manager_key(manager_key: str) -> str:
    if manager_key.startswith("unresolved"):
        return "Unresolved manager"
    return "League manager"


def _as_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return None


def _require_int(value: object) -> int:
    return _as_int(value) or 0


def _as_float(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _latest_team_name(manager: SnapshotManagerResponse) -> str | None:
    if not manager.team_aliases:
        return None
    latest = max(manager.team_aliases, key=lambda alias: alias.season)
    return latest.team_name


def _as_dict_list(value: object) -> list[SnapshotJsonObject]:
    if not isinstance(value, list):
        return []
    items = cast("list[SnapshotJsonValue]", value)
    return [item for item in items if isinstance(item, dict)]


def _as_dict(value: object) -> SnapshotJsonObject | None:
    return cast("SnapshotJsonObject", value) if isinstance(value, dict) else None


def _as_dict_map(value: object) -> dict[str, SnapshotJsonObject]:
    if not isinstance(value, dict):
        return {}
    typed = cast("dict[str, SnapshotJsonValue]", value)
    return {key: entry for key, entry in typed.items() if isinstance(entry, dict)}


def _waiver_superlatives(
    snapshot: LeagueAnalyticsSnapshotResponse,
) -> dict[str, SnapshotJsonObject]:
    waivers_extra = snapshot.waivers.model_extra or {}
    section = waivers_extra.get("superlatives")
    if section is None:
        section = (snapshot.model_extra or {}).get("waiverSuperlatives")
    return _as_dict_map(section)


def _str_field(source: SnapshotJsonObject, key: str) -> str | None:
    value = source.get(key)
    return value if isinstance(value, str) and value else None


def _record_line(standings: list[SnapshotJsonObject], manager_key: str | None) -> str | None:
    if not manager_key:
        return None
    for row in standings:
        if row.get("managerKey") == manager_key:
            wins = _as_int(row.get("wins")) or 0
            losses = _as_int(row.get("losses")) or 0
            ties = _as_int(row.get("ties")) or 0
            return f"{wins}-{losses}-{ties}" if ties else f"{wins}-{losses}"
    return None


def _top_scorer_line(standings: list[SnapshotJsonObject]) -> str | None:
    best: SnapshotJsonObject | None = None
    best_points = float("-inf")
    for row in standings:
        points = _as_float(row.get("pointsFor"))
        if points is not None and points > best_points:
            best_points = points
            best = row
    if best is None:
        return None
    name = _str_field(best, "displayName")
    return f"{name} led the league with {best_points:.1f} points for." if name else None


def _season_review(
    *,
    is_partial: bool,
    champion: SnapshotJsonObject | None,
    runner_up: SnapshotJsonObject | None,
    standings: list[SnapshotJsonObject],
    draft_recap: SnapshotJsonObject,
    transaction_count: int | None,
) -> list[str]:
    lines: list[str] = []
    if is_partial:
        lines.append("Season in progress; final standings are not yet set.")
        if transaction_count:
            lines.append(f"{transaction_count} roster moves logged so far.")
        return lines
    champion_line = _champion_review_line(champion, standings)
    if champion_line:
        lines.append(champion_line)
    if runner_up is not None:
        runner_name = _str_field(runner_up, "displayName")
        if runner_name:
            lines.append(f"{runner_name} finished runner-up.")
    top = _top_scorer_line(standings)
    if top:
        lines.append(top)
    steal_line = _draft_line(
        draft_recap.get("bestSteal"),
        "Draft steal: {drafter} landed {player} at pick {pick}.",
    )
    if steal_line:
        lines.append(steal_line)
    bust_line = _draft_line(
        draft_recap.get("biggestBust"),
        "Draft letdown: {drafter} used pick {pick} on {player}.",
    )
    if bust_line:
        lines.append(bust_line)
    if transaction_count:
        lines.append(f"{transaction_count} roster moves logged across the season.")
    return lines


def _champion_review_line(
    champion: SnapshotJsonObject | None,
    standings: list[SnapshotJsonObject],
) -> str | None:
    if champion is None:
        return None
    name = _str_field(champion, "displayName") or "The champion"
    team = _str_field(champion, "teamName")
    manager_key = champion.get("managerKey")
    record = _record_line(standings, manager_key if isinstance(manager_key, str) else None)
    base = f"{name} won the championship"
    if team:
        base += f" with {team}"
    if record:
        base += f" ({record})"
    return f"{base}."


def _draft_line(entry: object, template: str) -> str | None:
    if not isinstance(entry, dict):
        return None
    typed = cast("SnapshotJsonObject", entry)
    player = _str_field(typed, "playerName")
    drafter = _str_field(typed, "displayName")
    pick = _as_int(typed.get("overallPick"))
    if player and drafter and pick is not None:
        return template.format(drafter=drafter, player=player, pick=pick)
    return None


def _history_headline(
    is_partial: bool,  # noqa: FBT001
    champion: SnapshotJsonObject | None,
    final_week: int | None,
) -> str:
    if is_partial:
        return f"In progress through week {final_week}" if final_week else "Season in progress"
    if champion is not None:
        name = champion.get("displayName")
        name = name if isinstance(name, str) else "Champion"
        team = champion.get("teamName")
        if isinstance(team, str) and team:
            return f"{name} won the championship with {team}"
        return f"{name} won the championship"
    return "Season completed"


_COMPONENT_LABELS: dict[str, str] = {
    # v3 (mygm-historian-v3) components
    "draftValue": "Draft value (VOR surplus)",
    "luck": "Luck",
    # v2 (mygm-historian-v2) components
    "tradeValue": "Trade value",
    "waiverValue": "Waiver/FA value",
    "lineupEfficiency": "Lineup efficiency",
    "recordAndPoints": "Record & points",
    # v1 (mygm-retrospective-v1) components, kept for the formula toggle
    "tradePerformance": "Trade performance",
    "waiverPerformance": "Waiver performance",
    "luckAdjusted": "Luck-adjusted",
}


def _as_objects(value: SnapshotJsonValue | None) -> list[SnapshotJsonObject]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _component_breakdown(components: dict[str, float]) -> dict[str, dict[str, str | float]]:
    return {
        key: {"label": _COMPONENT_LABELS.get(key, key), "value": value}
        for key, value in components.items()
    }


snapshot_analytics_repository = SnapshotAnalyticsRepository()
