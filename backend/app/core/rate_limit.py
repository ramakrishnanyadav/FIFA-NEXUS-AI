import time
from collections import defaultdict
from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

class RateLimiter:
    def __init__(self, limit: int, window: int = 60):
        self.limit = limit
        self.window = window
        self.requests: defaultdict[str, list[float]] = defaultdict(list)

    def is_allowed(self, key: str) -> bool:
        now = time.time()
        # Filter out expired timestamps
        self.requests[key] = [t for t in self.requests[key] if now - t < self.window]
        if len(self.requests[key]) >= self.limit:
            return False
        self.requests[key].append(now)
        return True

# Initialize limiters
# Write endpoints: 30/min
write_limiter = RateLimiter(limit=30, window=60)
# Read endpoints: 100/min
read_limiter = RateLimiter(limit=100, window=60)

class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # We only rate-limit /api/v1 endpoints
        if not request.url.path.startswith("/api/v1"):
            return await call_next(request)

        # Bypass rate limiting in development environment for local load-testing
        from backend.app.core.config import settings
        if settings.ENVIRONMENT == "development":
            return await call_next(request)

        # Get client IP or API key for tracking
        client_ip = request.client.host if request.client else "unknown"
        api_key = request.headers.get("X-API-Key", "")
        key = f"{client_ip}:{api_key}"

        # Determine if it's a write or read endpoint
        is_write = request.method in ("POST", "PUT", "DELETE", "PATCH")
        
        # Check /api/v1/events/stream separately to bypass rate-limiting
        if request.url.path == "/api/v1/events/stream":
            return await call_next(request)

        if is_write:
            if not write_limiter.is_allowed(key):
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={"detail": "Too many requests. Write limit is 30/minute."}
                )
        else:
            if not read_limiter.is_allowed(key):
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={"detail": "Too many requests. Read limit is 100/minute."}
                )

        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data:; "
            "connect-src 'self' wss://*.onrender.com"
        )
        return response
