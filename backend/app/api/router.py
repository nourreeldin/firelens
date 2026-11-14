"""Versioned API router."""

from fastapi import APIRouter

from app.api.routes import analytics, calendar, exports, fires, health, regions

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(fires.router)
api_router.include_router(regions.router)
api_router.include_router(calendar.router)
api_router.include_router(analytics.router)
api_router.include_router(exports.router)
