from collections.abc import Iterator
from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient

from mygm_api.config import get_settings
from mygm_api.dependencies import get_store
from mygm_api.main import create_app
from mygm_api.store import ApiStore


@dataclass(frozen=True, slots=True)
class ApiHarness:
    client: TestClient
    store: ApiStore
    headers: dict[str, str]
    admin_headers: dict[str, str]


@pytest.fixture
def api_harness(monkeypatch: pytest.MonkeyPatch) -> Iterator[ApiHarness]:
    monkeypatch.setenv("MYGM_CREDENTIAL_KEY_V1", "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=")
    monkeypatch.setenv("MYGM_CREDENTIAL_KEY_ID", "test-key")
    monkeypatch.setenv("MYGM_ALLOWED_ORIGINS", '["http://127.0.0.1:3000"]')
    get_settings.cache_clear()
    api_store = ApiStore()
    app = create_app()
    app.dependency_overrides[get_store] = lambda: api_store
    with TestClient(app) as client:
        yield ApiHarness(
            client=client,
            store=api_store,
            headers={"Authorization": "Bearer alpha:user-1:user@example.com:user"},
            admin_headers={"Authorization": "Bearer alpha:admin-1:admin@example.com:admin"},
        )
    get_settings.cache_clear()
