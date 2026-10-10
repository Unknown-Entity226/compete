"""CompeteFastAPI Application Entrypoint."""
from contextlib import asynccontextmanager
from typing import AsyncGenerator
import logging

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.exceptions import (
    CompeteException,
    UserNotFoundError,
    UpstreamRateLimitError,
    UpstreamServiceError,
)
from app.api.router import api_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("compete")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan context manager for startup and shutdown events."""
    logger.info("Starting up CompeteFastAPI backend v%s", settings.VERSION)
    yield
    logger.info("Shutting down CompeteFastAPI backend")


app = FastAPI(
    title="Compete API",
    description="Head-to-head LeetCode competition backend and normalized GraphQL proxy.",
    version=settings.VERSION,
    lifespan=lifespan,
)

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


# Health check endpoint
@app.get("/health", tags=["Health"])
@app.get("/api/health", tags=["Health"])
async def health_check():
    """Health check endpoint for container probes and load balancers."""
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
    }


# Include /api router
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/", tags=["Root"])
async def root():
    """Root metadata endpoint."""
    return {
        "service": "CompeteFastAPI",
        "version": settings.VERSION,
        "docs": "/docs",
        "endpoints": {
            "user_profile": f"{settings.API_V1_STR}/users/{{username}}",
            "user_problems": f"{settings.API_V1_STR}/users/{{username}}/problems",
            "user_activity": f"{settings.API_V1_STR}/users/{{username}}/activity",
            "compare_users": f"{settings.API_V1_STR}/compare/{{user1}}/{{user2}}",
        },
    }

