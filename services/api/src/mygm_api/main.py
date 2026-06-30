import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from mygm_api.config import get_settings
from mygm_api.routers import analytics, membership, operations, share


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
    )
    app.include_router(membership.router, prefix="/v1")
    app.include_router(operations.router, prefix="/v1")
    app.include_router(analytics.router, prefix="/v1")
    app.include_router(share.router, prefix="/v1")
    app.add_api_route("/healthz", healthz, methods=["GET"], operation_id="healthz")
    if os.environ.get("MYGM_SEED_DEMO"):
        # Public read-only demo: seed the in-memory store so the alpha session can view
        # a fully populated league without live ESPN credentials. Must never break boot.
        try:
            from mygm_api.dependencies import store  # noqa: PLC0415
            from mygm_api.seed_demo import seed_demo_league  # noqa: PLC0415

            seed_demo_league(store)  # pragma: no cover - best-effort demo seed
        except Exception:  # noqa: BLE001, S110
            pass
    return app


async def healthz() -> dict[str, str]:
    return {"status": "ok"}


app = create_app()
