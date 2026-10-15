"""SlowAPI Rate Limiter configuration."""
from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings


def get_client_ip(request: Request) -> str:
    """Extract the real client IP address, sanitizing reverse proxy headers.

    Only respects X-Forwarded-For and X-Real-IP if the direct client connection
    originates from a trusted reverse proxy (e.g. localhost, internal docker/ALB proxy).
    Otherwise returns the direct socket address to prevent rate limiter spoofing.
    """
    client_host = request.client.host if request.client else None
    if client_host and client_host in settings.TRUSTED_PROXIES:
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # X-Forwarded-For may be a comma-separated list; first IP is client
            return forwarded_for.split(",")[0].strip()
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip.strip()
    return get_remote_address(request)


limiter = Limiter(
    key_func=get_client_ip,
    default_limits=[settings.DEFAULT_RATE_LIMIT],
    storage_uri=settings.REDIS_URL,
    headers_enabled=False,
)
