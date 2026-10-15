"""CompeteFastAPI Application Entrypoint."""
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
BASE_DIR = Path(__file__).resolve().parent.parent
env_file = BASE_DIR / ".env"
if env_file.exists():
    load_dotenv(dotenv_path=env_file)
else:
    load_dotenv()

from contextlib import asynccontextmanager
from typing import AsyncGenerator
import logging
import time

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text

from app.core.config import settings
from app.core.limiter import limiter
from app.core.exceptions import (
    CompeteException,
    UserNotFoundError,
    UpstreamRateLimitError,
    UpstreamServiceError,
)
from app.api.deps import get_cache_service
from app.api.router import api_router
from app.db.session import async_session_factory
from app.workers.scheduler import (
    start_scheduler,
    stop_scheduler,
    get_scheduler_status,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("compete")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan context manager for startup and shutdown events."""
    logger.info("Starting up CompeteFastAPI backend version %s", settings.APP_VERSION)
    
    # Initialize cache
    cache = get_cache_service()
    cache_info = await cache.health_check()
    logger.info("Cache service ready (%s on %s)", cache_info["status"], cache_info["backend"])

    # Initialize background scheduler if enabled
    if settings.ENABLE_BACKGROUND_SCHEDULER:
        try:
            start_scheduler()
        except Exception as exc:
            logger.warning("Could not start background scheduler: %s", exc)

    yield

    logger.info("Shutting down CompeteFastAPI backend")
    stop_scheduler()
    await cache.close()


app = FastAPI(
    title="Compete API",
    description="Head-to-head LeetCode competition backend and normalized GraphQL proxy.",
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

# Attach SlowAPI Limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Request Timing & Profiling Middleware
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.perf_counter()
    response = await call_next(request)
    process_time = time.perf_counter() - start_time
    response.headers["X-Process-Time"] = f"{process_time:.4f}s"
    return response

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global Exception Handlers
@app.exception_handler(UserNotFoundError)
async def user_not_found_handler(request: Request, exc: UserNotFoundError):
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"error": "Not Found", "message": exc.message, "username": exc.username},
    )


@app.exception_handler(UpstreamRateLimitError)
async def upstream_rate_limit_handler(request: Request, exc: UpstreamRateLimitError):
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={"error": "Rate Limit Exceeded", "message": exc.message},
    )


@app.exception_handler(UpstreamServiceError)
async def upstream_service_error_handler(request: Request, exc: UpstreamServiceError):
    return JSONResponse(
        status_code=status.HTTP_502_BAD_GATEWAY,
        content={"error": "Bad Gateway", "message": exc.message},
    )


@app.exception_handler(CompeteException)
async def compete_exception_handler(request: Request, exc: CompeteException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": "Application Error", "message": exc.message},
    )


# Deep Health check endpoint
@app.get("/health", tags=["Health"])
@app.get("/api/health", tags=["Health"])
async def health_check():
    """Comprehensive health check endpoint probing DB, Cache, and Scheduler."""
    # 1. Probe Cache
    cache = get_cache_service()
    cache_info = await cache.health_check()

    # 2. Probe Database
    db_status = "unhealthy"
    db_latency_ms = None
    try:
        start = time.perf_counter()
        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
        db_latency_ms = round((time.perf_counter() - start) * 1000, 2)
        db_status = "healthy"
    except Exception as exc:
        logger.debug("Database probe failed during healthcheck: %s", exc)

    # 3. Probe Scheduler
    scheduler_info = get_scheduler_status()

    # Evaluate overall system health
    if db_status == "healthy" and cache_info.get("status") == "healthy":
        overall_status = "healthy"
    elif db_status == "healthy":
        overall_status = "degraded"
    else:
        overall_status = "unhealthy"

    return {
        "status": overall_status,
        "service": settings.PROJECT_NAME,
        "version": settings.APP_VERSION,
        "database": {
            "status": db_status,
            "latencyMs": db_latency_ms,
        },
        "cache": cache_info,
        "scheduler": scheduler_info,
    }


# Include api router
app.include_router(api_router, prefix=settings.API_PREFIX)


@app.get("/", tags=["Root"])
async def root():
    """Root metadata endpoint."""
    return {
        "service": "CompeteFastAPI",
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "endpoints": {
            "health": f"{settings.API_PREFIX}/health",
            "user_profile": f"{settings.API_PREFIX}/users/{{username}}",
            "user_problems": f"{settings.API_PREFIX}/users/{{username}}/problems",
            "user_activity": f"{settings.API_PREFIX}/users/{{username}}/activity",
            "user_history": f"{settings.API_PREFIX}/users/{{username}}/history",
            "compare_users": f"{settings.API_PREFIX}/compare/{{first_user}}/{{second_user}}",
        },
    }
