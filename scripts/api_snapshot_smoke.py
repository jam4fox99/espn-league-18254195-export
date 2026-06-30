#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "cryptography>=42.0.0",
#     "fastapi>=0.128.0",
#     "httpx>=0.27.0",
#     "orjson>=3.10.0",
#     "pydantic>=2.8.0",
#     "pydantic-settings>=2.4.0",
# ]
# ///

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from http import HTTPStatus
from pathlib import Path
from typing import Literal, Protocol
from urllib.parse import quote
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
API_SRC = ROOT / "services" / "api" / "src"
sys.path.insert(0, str(API_SRC))
os.environ["MYGM_CREDENTIAL_KEY_V1"] = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
os.environ["MYGM_CREDENTIAL_KEY_ID"] = "smoke-key"
os.environ["MYGM_ALLOWED_ORIGINS"] = '["http://127.0.0.1:3000"]'
os.chdir(ROOT / "services" / "api")

from fastapi.testclient import TestClient  # noqa: E402

from mygm_api.dependencies import get_store  # noqa: E402
from mygm_api.main import create_app  # noqa: E402
from mygm_api.models import VersionId  # noqa: E402
from mygm_api.schemas import LeagueAnalyticsSnapshotResponse  # noqa: E402
from mygm_api.store import ApiStore  # noqa: E402

type Scenario = Literal["core", "missing-snapshot", "recompute"]
type JsonValue = None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]
type JsonObject = dict[str, JsonValue]

USER_HEADERS = {"Authorization": "Bearer alpha:local-alpha-user:alpha@example.com:admin"}


class JsonResponse(Protocol):
    status_code: int

    def json(self) -> JsonValue: ...


class ClientProtocol(Protocol):
    def request(
        self,
        method: str,
        path: str,
        *,
        headers: dict[str, str],
        params: dict[str, str] | None,
        json: JsonObject | None,
    ) -> JsonResponse: ...


@dataclass(frozen=True, slots=True)
class CliArgs:
    fixture_root: Path
    evidence: Path | None
    scenario: Scenario


@dataclass(frozen=True, slots=True)
class SeededApi:
    client: ClientProtocol
    store: ApiStore
    league_id: str
    version_id: VersionId | None
    snapshot: LeagueAnalyticsSnapshotResponse | None


@dataclass(frozen=True, slots=True)
class RequestSpec:
    method: str
    path: str
    expected: HTTPStatus
    json_body: JsonObject | None = None
    headers: dict[str, str] | None = None
    params: dict[str, str] | None = None


@dataclass(slots=True)
class Transcript:
    lines: list[str]

    def add(self, line: str) -> None:
        self.lines.append(line)

    def request(
        self,
        client: ClientProtocol,
        spec: RequestSpec,
    ) -> JsonObject:
        request_headers = USER_HEADERS if spec.headers is None else spec.headers
        response = client.request(
            spec.method,
            spec.path,
            headers=request_headers,
            params=spec.params,
            json=spec.json_body,
        )
        self.add(f"> {spec.method} {spec.path}")
        if spec.params is not None:
            self.add(f"> query {json.dumps(spec.params, sort_keys=True)}")
        if spec.json_body is not None:
            self.add(f"> body {json.dumps(spec.json_body, sort_keys=True)}")
        self.add(f"< HTTP {response.status_code}")
        payload = response.json()
        self.add(f"< body {json.dumps(payload, sort_keys=True)[:1200]}")
        if response.status_code != spec.expected:
            msg = (
                f"{spec.method} {spec.path} returned {response.status_code}, "
                f"expected {spec.expected}"
            )
            raise RuntimeError(msg)
        if not isinstance(payload, dict):
            msg = f"{spec.method} {spec.path} returned non-object JSON"
            raise TypeError(msg)
        return payload

    def write(self, evidence: Path | None) -> None:
        text = "\n".join(self.lines) + "\n"
        if evidence is not None:
            evidence.parent.mkdir(parents=True, exist_ok=True)
            _ = evidence.write_text(text)
        _ = sys.stdout.write(text)


def main() -> None:
    args = parse_cli_args(sys.argv[1:])
    scenario: Scenario = args.scenario
    fixture_root = args.fixture_root
    if not fixture_root.is_absolute():
        fixture_root = ROOT / fixture_root
    evidence = args.evidence
    if evidence is not None and not evidence.is_absolute():
        evidence = ROOT / evidence
    transcript = Transcript(lines=[f"# scenario {scenario}"])
    match scenario:
        case "core":
            run_core(fixture_root, transcript)
        case "missing-snapshot":
            run_missing_snapshot(fixture_root, transcript)
        case "recompute":
            run_recompute(fixture_root, transcript, denied_evidence_for(evidence))
    transcript.write(evidence)


def parse_cli_args(argv: list[str]) -> CliArgs:
    fixture_root: Path | None = None
    evidence: Path | None = None
    scenario: Scenario = "core"
    index = 0
    while index < len(argv):
        option = argv[index]
        match option:
            case "--fixture-root":
                index += 1
                fixture_root = Path(argv[index])
            case "--evidence":
                index += 1
                evidence = Path(argv[index])
            case "--scenario":
                index += 1
                scenario = parse_scenario(argv[index])
            case _:
                msg = f"unknown argument: {option}"
                raise ValueError(msg)
        index += 1
    if fixture_root is None:
        msg = "--fixture-root is required"
        raise ValueError(msg)
    return CliArgs(fixture_root=fixture_root, evidence=evidence, scenario=scenario)


def parse_scenario(raw: str) -> Scenario:
    match raw:
        case "core":
            return "core"
        case "missing-snapshot":
            return "missing-snapshot"
        case "recompute":
            return "recompute"
        case _:
            msg = f"unknown scenario: {raw}"
            raise ValueError(msg)


def run_core(fixture_root: Path, transcript: Transcript) -> None:
    seeded = seed_api(fixture_root, with_snapshot=True, transcript=transcript)
    assert seeded.snapshot is not None
    manager_key = seeded.snapshot.managers[0].manager_key
    trade_id = seeded.snapshot.trades.items[0].trade_id
    waiver_id = seeded.snapshot.waivers.items[0].move_id
    head_to_head = seeded.snapshot.head_to_head.pairs[0]
    encoded_manager = quote(manager_key, safe="")
    encoded_trade = quote(trade_id, safe="")
    encoded_waiver = quote(waiver_id, safe="")

    dashboard = transcript.request(
        seeded.client,
        RequestSpec(
            method="GET",
            path=f"/v1/leagues/{seeded.league_id}/dashboard",
            expected=HTTPStatus.OK,
        ),
    )
    leaderboard = transcript.request(
        seeded.client,
        RequestSpec(
            method="GET",
            path=f"/v1/leagues/{seeded.league_id}/leaderboard",
            expected=HTTPStatus.OK,
        ),
    )
    manager = transcript.request(
        seeded.client,
        RequestSpec(
            method="GET",
            path=f"/v1/leagues/{seeded.league_id}/gms/{encoded_manager}",
            expected=HTTPStatus.OK,
        ),
    )
    trades = transcript.request(
        seeded.client,
        RequestSpec(
            method="GET",
            path=f"/v1/leagues/{seeded.league_id}/trades",
            expected=HTTPStatus.OK,
        ),
    )
    _ = transcript.request(
        seeded.client,
        RequestSpec(
            method="GET",
            path=f"/v1/leagues/{seeded.league_id}/trades/{encoded_trade}",
            expected=HTTPStatus.OK,
        ),
    )
    _ = transcript.request(
        seeded.client,
        RequestSpec(
            method="GET",
            path=f"/v1/leagues/{seeded.league_id}/waivers/{encoded_waiver}",
            expected=HTTPStatus.OK,
        ),
    )
    waivers = transcript.request(
        seeded.client,
        RequestSpec(
            method="GET",
            path=f"/v1/leagues/{seeded.league_id}/waivers",
            expected=HTTPStatus.OK,
        ),
    )
    _ = transcript.request(
        seeded.client,
        RequestSpec(
            method="GET",
            path=f"/v1/leagues/{seeded.league_id}/records",
            expected=HTTPStatus.OK,
        ),
    )
    _ = transcript.request(
        seeded.client,
        RequestSpec(
            method="GET",
            path=f"/v1/leagues/{seeded.league_id}/head-to-head",
            expected=HTTPStatus.OK,
            params={
                "season": "all",
                "managerA": head_to_head.manager_a_key,
                "managerB": head_to_head.manager_b_key,
            },
        ),
    )
    _ = transcript.request(
        seeded.client,
        RequestSpec(
            method="GET",
            path=f"/v1/leagues/{seeded.league_id}/head-to-head",
            expected=HTTPStatus.OK,
            params={
                "season": "2025",
                "managerA": head_to_head.manager_a_key,
                "managerB": head_to_head.manager_b_key,
            },
        ),
    )
    _ = transcript.request(
        seeded.client,
        RequestSpec(
            method="GET",
            path=f"/v1/leagues/{seeded.league_id}/formula",
            expected=HTTPStatus.OK,
        ),
    )
    _ = transcript.request(
        seeded.client,
        RequestSpec(
            method="GET",
            path=f"/v1/leagues/{seeded.league_id}/data-health",
            expected=HTTPStatus.OK,
        ),
    )
    _ = transcript.request(
        seeded.client,
        RequestSpec(
            method="GET",
            path=f"/v1/leagues/{seeded.league_id}/seasons",
            expected=HTTPStatus.OK,
        ),
    )
    dashboard_source_counts = json_object_field(dashboard, "sourceCounts")
    leaderboard_rows = json_list_field(leaderboard, "rows")
    trade_rows = json_list_field(trades, "rows")
    waiver_rows = json_list_field(waivers, "rows")
    require(
        condition="trades" in dashboard_source_counts,
        message="dashboard source counts missing",
    )
    require(condition=len(leaderboard_rows) > 1, message="leaderboard did not return real rows")
    require(
        condition=json_string_field(manager, "managerKey") == manager_key,
        message="manager profile key mismatch",
    )
    require(condition=len(trade_rows) > 1, message="trade list did not return real rows")
    require(condition=len(waiver_rows) > 1, message="waiver list did not return real rows")


def run_missing_snapshot(fixture_root: Path, transcript: Transcript) -> None:
    seeded = seed_api(fixture_root, with_snapshot=False, transcript=transcript)
    response = transcript.request(
        seeded.client,
        RequestSpec(
            method="GET",
            path=f"/v1/leagues/{seeded.league_id}/dashboard",
            expected=HTTPStatus.CONFLICT,
        ),
    )
    require(
        condition=json_string_field(response, "detail") == "analytics snapshot required",
        message="missing snapshot detail mismatch",
    )


def run_recompute(
    fixture_root: Path,
    transcript: Transcript,
    denied_evidence: Path | None,
) -> None:
    seeded = seed_api(fixture_root, with_snapshot=True, transcript=transcript)
    first_import = transcript.request(
        seeded.client,
        RequestSpec(
            method="POST",
            path=f"/v1/leagues/{seeded.league_id}/import-runs",
            expected=HTTPStatus.ACCEPTED,
            json_body={
                "startYear": 2020,
                "endYear": 2025,
                "includeActivity": True,
                "forceRefresh": False,
            },
        ),
    )
    reprocess_body: JsonObject = {
        "sourceImportRunId": json_string_field(first_import, "runId"),
        "targets": ["analyticsSnapshot"],
        "formulaVersion": "mygm-retrospective-v1",
    }
    created = transcript.request(
        seeded.client,
        RequestSpec(
            method="POST",
            path=f"/v1/leagues/{seeded.league_id}/reprocess-runs",
            expected=HTTPStatus.ACCEPTED,
            json_body=reprocess_body,
        ),
    )
    status_response = transcript.request(
        seeded.client,
        RequestSpec(
            method="GET",
            path=f"/v1/reprocess-runs/{json_string_field(created, 'runId')}",
            expected=HTTPStatus.OK,
        ),
    )
    duplicate = transcript.request(
        seeded.client,
        RequestSpec(
            method="POST",
            path=f"/v1/leagues/{seeded.league_id}/reprocess-runs",
            expected=HTTPStatus.CONFLICT,
            json_body=reprocess_body,
        ),
    )
    dashboard = transcript.request(
        seeded.client,
        RequestSpec(
            method="GET",
            path=f"/v1/leagues/{seeded.league_id}/dashboard",
            expected=HTTPStatus.OK,
        ),
    )
    require(
        condition=json_string_field(duplicate, "detail") == "analytics recompute already queued",
        message="duplicate recompute detail mismatch",
    )
    require(
        condition=json_string_field(status_response, "status") == "queued",
        message="reprocess status mismatch",
    )
    require(
        condition=len(json_object_field(status_response, "sourceCounts")) > 0,
        message="reprocess source counts missing",
    )
    require(
        condition=len(json_list_field(status_response, "caveats")) > 0,
        message="reprocess caveats missing",
    )
    require(
        condition=json_string_field(dashboard, "version") == str(seeded.version_id),
        message="current pointer changed",
    )
    write_recompute_denied_evidence(seeded, reprocess_body, denied_evidence)


def write_recompute_denied_evidence(
    seeded: SeededApi,
    reprocess_body: JsonObject,
    evidence: Path | None,
) -> None:
    denied = Transcript(lines=["# scenario recompute-denied"])
    _ = denied.request(
        seeded.client,
        RequestSpec(
            method="POST",
            path=f"/v1/leagues/{seeded.league_id}/reprocess-runs",
            expected=HTTPStatus.UNAUTHORIZED,
            json_body=reprocess_body,
            headers={},
        ),
    )
    outsider_headers = {"Authorization": "Bearer alpha:outside-user:outside@example.com:user"}
    _ = denied.request(
        seeded.client,
        RequestSpec(
            method="POST",
            path="/v1/alpha-invites/accept",
            expected=HTTPStatus.OK,
            json_body={"email": "outside@example.com", "inviteCode": "alpha"},
            headers=outsider_headers,
        ),
    )
    _ = denied.request(
        seeded.client,
        RequestSpec(
            method="POST",
            path=f"/v1/leagues/{seeded.league_id}/reprocess-runs",
            expected=HTTPStatus.FORBIDDEN,
            json_body=reprocess_body,
            headers=outsider_headers,
        ),
    )
    denied.write(evidence)


def denied_evidence_for(evidence: Path | None) -> Path | None:
    if evidence is None:
        return None
    return evidence.with_name("recompute-denied.txt")


def seed_api(fixture_root: Path, *, with_snapshot: bool, transcript: Transcript) -> SeededApi:
    store = ApiStore()
    app = create_app()
    app.dependency_overrides[get_store] = lambda: store
    client = TestClient(app)
    invite = transcript.request(
        client,
        RequestSpec(
            method="POST",
            path="/v1/alpha-invites/accept",
            expected=HTTPStatus.OK,
            json_body={"email": "alpha@example.com", "inviteCode": "alpha"},
        ),
    )
    league = transcript.request(
        client,
        RequestSpec(
            method="POST",
            path="/v1/leagues",
            expected=HTTPStatus.CREATED,
            json_body={
                "espnLeagueId": fixture_root.name.removeprefix("league_"),
                "name": "Smoke League",
            },
        ),
    )
    league_id = str(league["leagueId"])
    transcript.add(f"# invite organization {invite['organizationId']}")
    _ = transcript.request(
        client,
        RequestSpec(
            method="POST",
            path=f"/v1/leagues/{league_id}/credentials",
            expected=HTTPStatus.OK,
            json_body={
                "leagueId": league_id,
                "SWID": "{SMOKE-SWID}",
                "espn_s2": "smoke-token",
                "consentVersion": "alpha-consent-v1",
                "startYear": 2020,
                "endYear": 2025,
            },
        ),
    )
    if not with_snapshot:
        return SeededApi(
            client=client,
            store=store,
            league_id=league_id,
            version_id=None,
            snapshot=None,
        )
    snapshot = load_snapshot(fixture_root, transcript)
    version_id = VersionId(uuid4())
    parsed_league_id = next(key for key in store.leagues if str(key) == league_id)
    store.analytics_snapshots[(parsed_league_id, version_id)] = snapshot
    store.current_analytics_version_by_league[parsed_league_id] = version_id
    transcript.add(f"# seeded snapshot version {version_id}")
    transcript.add(
        f"# seeded managers={len(snapshot.managers)} trades={len(snapshot.trades.items)}",
    )
    return SeededApi(
        client=client,
        store=store,
        league_id=league_id,
        version_id=version_id,
        snapshot=snapshot,
    )


def load_snapshot(
    fixture_root: Path,
    transcript: Transcript,
) -> LeagueAnalyticsSnapshotResponse:
    candidates = (
        fixture_root / "analytics_snapshot.json",
        fixture_root / "fixture-out" / "analytics_snapshot.json",
        ROOT / ".omo/evidence/task-6-mygm-espn-full-dashboard/fixture-out/analytics_snapshot.json",
    )
    for candidate in candidates:
        if candidate.exists():
            transcript.add(f"# snapshot source {candidate}")
            return LeagueAnalyticsSnapshotResponse.model_validate_json(candidate.read_text())
    msg = f"analytics_snapshot.json not found under {fixture_root}"
    raise FileNotFoundError(msg)


def json_object_field(payload: JsonObject, field_name: str) -> JsonObject:
    value = payload[field_name]
    if not isinstance(value, dict):
        msg = f"{field_name} must be a JSON object"
        raise TypeError(msg)
    return value


def json_list_field(payload: JsonObject, field_name: str) -> list[JsonValue]:
    value = payload[field_name]
    if not isinstance(value, list):
        msg = f"{field_name} must be a JSON array"
        raise TypeError(msg)
    return value


def json_string_field(payload: JsonObject, field_name: str) -> str:
    value = payload[field_name]
    if not isinstance(value, str):
        msg = f"{field_name} must be a string"
        raise TypeError(msg)
    return value


def require(*, condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


if __name__ == "__main__":
    main()
