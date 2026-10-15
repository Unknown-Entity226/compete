"""SlowAPI Rate Limiter configuration."""
from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings


def get_client_ip(request: Request) -> str:
    """Extract the real client IP address, respecting reverse proxy headers.

    Checks X-Forwarded-For (first IP in chain) and X-Real-IP headers before
    falling back to the direct socket address. Required for correct per-client
    rate limiting when deployed behind Nginx, Docker bridge networking,
    AWS ALB, or Cloudflare.
    """
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # X-Forwarded-For may be a comma-separated list; the first IP is the real client
        return forwarded_for.split(",")[0].strip()
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    return get_remote_address(request)


limiter = Limiter(
    key_func=get_client_ip,
    default_limits=[settings.DEFAULT_RATE_LIMIT],
    headers_enabled=False,
)
