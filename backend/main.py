"""
SmartSpend API — Main Application Entry Point

Security measures applied here:
- CORS locked to explicit allowed origins from environment
- Rate limiting via slowapi (60 req/min per IP by default)
- Global exception handler — stack traces never reach the client
- Request logging excludes body content (no PII in logs)
- /health endpoint for Render uptime monitoring + UptimeRobot
"""

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from config import get_settings
from database import create_db_and_tables
from ingestion.ingester import get_adapter
from models.schemas import HealthResponse

# Routers — import as they are built
from routers import profile

logger = logging.getLogger(__name__)
settings = get_settings()

# ── Rate Limiter ──────────────────────────────────────────────────────────────
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[f"{settings.rate_limit_per_minute}/minute"],
)


# ── Lifespan ──────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Runs on startup and shutdown.
    Startup: verify DB tables exist (dev only — prod uses Alembic).
    """
    logger.info(f"SmartSpend API starting — environment: {settings.environment}")

    if settings.environment == "development":
        # In dev, create tables if they don't exist
        # In production, Alembic handles this
        create_db_and_tables()
        logger.info("Database tables verified")

    yield

    logger.info("SmartSpend API shutting down")


# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="SmartSpend API",
    description=(
        "AI-powered budgeting and financial education. "
        "Personalized insights, goal tracking, and contextual credit education."
    ),
    version="1.0.0",
    lifespan=lifespan,
    # Disable default exception detail in production
    # (overridden by our global handler below)
)

# ── Middleware ────────────────────────────────────────────────────────────────

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# CORS — locked to explicit origins, never wildcard in production
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)

# ── Request Logging ───────────────────────────────────────────────────────────
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """
    Log method, path, and duration for every request.
    Deliberately excludes: headers, body, query params (may contain sensitive data).
    """
    start = time.time()
    response = await call_next(request)
    duration_ms = round((time.time() - start) * 1000)

    # Only log path without query string — query params may contain IDs
    logger.info(
        f"{request.method} {request.url.path} "
        f"→ {response.status_code} ({duration_ms}ms)"
    )
    return response


# ── Global Error Handler ──────────────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Catch-all handler — prevents stack traces from reaching clients.
    Logs the full exception server-side, returns a safe generic message.
    """
    logger.exception(f"Unhandled exception on {request.method} {request.url.path}: {exc}")

    # In development, include the error message for easier debugging
    if settings.environment == "development":
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": f"Internal server error: {str(exc)}"},
        )

    # In production, never expose internal details
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal error occurred. Please try again."},
    )


# ── Routers ───────────────────────────────────────────────────────────────────

from routers.transactions import router as transactions_router
from routers.education import router as education_router
from routers.health_history import router as health_history_router

from routers.remaining_routers import (
    insights_router,
    reports_router,
    goals_router,
    nudges_router,
    achievements_router,
    demo_router,
)

app.include_router(profile.router)
app.include_router(transactions_router)
app.include_router(education_router)
app.include_router(insights_router)
app.include_router(reports_router)
app.include_router(goals_router)
app.include_router(nudges_router)
app.include_router(achievements_router)
app.include_router(demo_router)
app.include_router(health_history_router)


# ── Core Endpoints ────────────────────────────────────────────────────────────

@app.get("/", include_in_schema=False)
def root():
    return {
        "app": "SmartSpend API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
    }


@app.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    tags=["system"],
)
def health_check():
    """
    Used by Render to verify the service is running.
    Also pinged by UptimeRobot every 10 minutes to prevent cold starts.
    """
    adapter = get_adapter()
    return HealthResponse(
        status="healthy",
        adapter=adapter.source_key,
        adapter_healthy=adapter.validate_connection(),
        environment=settings.environment,
    )
