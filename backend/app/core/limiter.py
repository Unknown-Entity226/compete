"""SlowAPI Rate Limiter configuration."""
import ipaddress
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
    if not client_host:
        return get_remote_address(request)

    try:
        direct_ip = ipaddress.ip_address(client_host)
    except ValueError:
        return get_remote_address(request)

    def is_trusted(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
        for configured_proxy in settings.TRUSTED_PROXIES:
            try:
                if address in ipaddress.ip_network(configured_proxy, strict=False):
                    return True
            except ValueError:
                try:
                    if address == ipaddress.ip_address(configured_proxy):
                        return True
                except ValueError:
                    continue
        return False

    if is_trusted(direct_ip):
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            try:
                chain = [
                    ipaddress.ip_address(part.strip())
                    for part in forwarded_for.split(",")
                    if part.strip()
                ]
            except ValueError:
                return get_remote_address(request)

            # Walk from the trusted proxy toward the client. This prevents a
            # client-supplied leftmost X-Forwarded-For value from being trusted.
            for address in reversed(chain):
                if not is_trusted(address):
                    return address.compressed
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            try:
                return ipaddress.ip_address(real_ip.strip()).compressed
            except ValueError:
                return get_remote_address(request)
    return get_remote_address(request)


limiter = Limiter(
    key_func=get_client_ip,
    default_limits=[settings.DEFAULT_RATE_LIMIT],
    storage_uri=settings.REDIS_URL,
    headers_enabled=False,
)
