"""HTTP hardening: client IP resolution, rate limiting, security headers."""

from __future__ import annotations

import ipaddress
import time
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


class ClientIpResolver:
    """Honours X-Forwarded-For only when the direct peer is an explicitly trusted proxy."""

    def __init__(self, trusted: list[str]) -> None:
        self.trusted = [ipaddress.ip_network(n, strict=False) for n in trusted]

    def _is_trusted(self, ip: str) -> bool:
        try:
            a = ipaddress.ip_address(ip)
        except ValueError:
            return False
        return any(a in n for n in self.trusted if n.version == a.version)

    def resolve(self, request: Request) -> str:
        peer = request.client.host if request.client else "unknown"
        if not self.trusted or not self._is_trusted(peer):
            return peer
        xff = request.headers.get("x-forwarded-for", "")
        hops = [h.strip() for h in xff.split(",") if h.strip()]
        # walk from the right: the first address that is not a trusted proxy is the client
        for hop in reversed(hops):
            if not self._is_trusted(hop):
                try:
                    ipaddress.ip_address(hop)
                    return hop
                except ValueError:
                    return peer
        return peer


class SlidingWindowLimiter:
    def __init__(self, limit: int, window: float) -> None:
        self.limit = limit
        self.window = window
        self._hits: dict[str, deque] = defaultdict(deque)

    def hit(self, key: str) -> bool:
        now = time.monotonic()
        q = self._hits[key]
        while q and now - q[0] > self.window:
            q.popleft()
        if len(q) >= self.limit:
            return False
        q.append(now)
        if len(self._hits) > 10000:  # bound memory
            for k in list(self._hits)[:1000]:
                if not self._hits[k]:
                    del self._hits[k]
        return True

    def count(self, key: str) -> int:
        now = time.monotonic()
        q = self._hits.get(key) or deque()
        return sum(1 for t in q if now - t <= self.window)


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, limiter: SlidingWindowLimiter, resolver: ClientIpResolver) -> None:
        super().__init__(app)
        self.limiter = limiter
        self.resolver = resolver

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path
        if path.startswith("/api/") and path not in ("/api/v1/health", "/api/v1/stream"):
            ip = self.resolver.resolve(request)
            if not self.limiter.hit(ip):
                return JSONResponse({"detail": "rate limit exceeded"}, status_code=429,
                                    headers={"Retry-After": "60"})
        return await call_next(request)


CSP = (
    "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; "
    "connect-src 'self'; font-src 'self' data:; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        h = response.headers
        h.setdefault("X-Content-Type-Options", "nosniff")
        h.setdefault("X-Frame-Options", "DENY")
        h.setdefault("Referrer-Policy", "no-referrer")
        h.setdefault("Permissions-Policy", "geolocation=(), camera=(), microphone=()")
        if not request.url.path.startswith(("/api/docs", "/api/redoc")):
            h.setdefault("Content-Security-Policy", CSP)
        if request.url.path.startswith("/api/"):
            h.setdefault("Cache-Control", "no-store")
        if request.headers.get("x-forwarded-proto") == "https" or request.url.scheme == "https":
            h.setdefault("Strict-Transport-Security", "max-age=31536000")
        return response
