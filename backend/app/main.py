"""FastAPI application entry point."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.core.config import Settings, get_settings
from app.core.exceptions import (
    DatabaseExecutionError,
    DatabaseUnavailableError,
    DateRangeError,
    FireNotFoundError,
    RegionNotFoundError,
)
from app.db.database import Database

logger = logging.getLogger(__name__)
DOCS_DIR = Path(__file__).parent / "static"


def create_app(settings: Settings | None = None) -> FastAPI:
    """Application factory, useful for tests and alternate deployments."""
    app_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        database = await Database.connect(app_settings)
        application.state.database = database
        try:
            yield
        finally:
            application.state.database = None
            await database.close()

    application = FastAPI(
        title=app_settings.app_name,
        version=app_settings.app_version,
        description=(
            "Read-only API for exploring harmonized MODIS and VIIRS active-fire "
            "detections from NASA FIRMS. Queries use parameterized raw SQL over "
            "public.fire_hotspots with PostGIS spatial filtering."
        ),
        lifespan=lifespan,
        # Serve the same generated OpenAPI reference with FireLens styling.
        docs_url=None,
        redoc_url=app_settings.redoc_url,
    )

    application.mount(
        "/docs-assets",
        StaticFiles(directory=DOCS_DIR),
        name="docs-assets",
    )

    @application.get(app_settings.docs_url, include_in_schema=False)
    async def swagger_docs() -> HTMLResponse:
        """Serve the custom FireLens view backed by the live OpenAPI schema."""
        page = (DOCS_DIR / "docs.html").read_text(encoding="utf-8")
        page = page.replace("__OPENAPI_URL__", application.openapi_url or "/openapi.json")
        return HTMLResponse(page)

    # Keep route dependencies on the same settings instance used by lifespan.
    application.dependency_overrides[get_settings] = lambda: app_settings

    origins = app_settings.cors_origin_list
    application.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials="*" not in origins,
        allow_methods=["GET", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["Content-Disposition"],
    )

    @application.exception_handler(RegionNotFoundError)
    async def handle_region_not_found(
        _: Request, exc: RegionNotFoundError
    ) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @application.exception_handler(FireNotFoundError)
    async def handle_fire_not_found(_: Request, exc: FireNotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @application.exception_handler(DateRangeError)
    async def handle_date_range(_: Request, exc: DateRangeError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @application.exception_handler(DatabaseUnavailableError)
    async def handle_database_unavailable(
        _: Request, exc: DatabaseUnavailableError
    ) -> JSONResponse:
        logger.error("Database unavailable: %s", type(exc).__name__)
        return JSONResponse(
            status_code=503,
            content={"detail": "Database is unavailable."},
        )

    @application.exception_handler(DatabaseExecutionError)
    async def handle_database_execution(
        _: Request, exc: DatabaseExecutionError
    ) -> JSONResponse:
        logger.error("Database query failed: %s", type(exc).__name__)
        return JSONResponse(
            status_code=500,
            content={"detail": "A database query failed."},
        )

    @application.exception_handler(Exception)
    async def handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error."},
        )

    application.include_router(api_router, prefix=app_settings.api_v1_prefix)

    @application.get("/", include_in_schema=False)
    async def root() -> dict[str, Any]:
        return {
            "name": app_settings.app_name,
            "version": app_settings.app_version,
            "docs": app_settings.docs_url,
            "health": f"{app_settings.api_v1_prefix}/health",
            "api": app_settings.api_v1_prefix,
        }

    @application.get("/health", include_in_schema=False)
    async def root_liveness() -> dict[str, str]:
        """Unversioned liveness alias for container platforms."""
        return {"status": "ok"}

    @application.get("/health/ready", include_in_schema=False)
    async def root_readiness(request: Request) -> dict[str, str]:
        """Unversioned readiness alias for container platforms."""
        database = getattr(request.app.state, "database", None)
        if database is None:
            raise DatabaseUnavailableError("Database is unavailable.")
        await database.check()
        return {"status": "ready", "database": "connected"}

    return application


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
