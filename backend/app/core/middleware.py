import time
import uuid
import logging
from typing import Optional
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import get_settings

logger = logging.getLogger("taskpilot")
settings = get_settings()

_redis_client = None


def get_redis_client():
    global _redis_client
    if _redis_client is None:
        try:
            import redis.asyncio as aioredis
            _redis_client = aioredis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=0.5,
            )
        except Exception as e:
            logger.warning(f"Could not initialize Redis client for rate limiting: {e}")
            return None
    return _redis_client


class RequestContextMiddleware(BaseHTTPMiddleware):
    """
    Middleware that adds a unique request_id to each request,
    tracks response latency, and attaches X-Request-ID header to responses.
    """
    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id
        start_time = time.perf_counter()

        response = await call_next(request)

        duration = time.perf_counter() - start_time
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time"] = f"{duration:.4f}s"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-Permitted-Cross-Domain-Policies"] = "none"
        if settings.ENVIRONMENT == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response


class TenantRateLimitMiddleware(BaseHTTPMiddleware):
    """
    Per-tenant rate limiting middleware using Redis sliding-window minute counter.
    Protects multi-tenant workloads from noisy-neighbor saturation.
    Gracefully fails open if Redis is unavailable.
    """
    def __init__(self, app, max_requests_per_minute: int = 600):
        super().__init__(app)
        self.max_requests_per_minute = max_requests_per_minute

    async def dispatch(self, request: Request, call_next) -> Response:
        # Skip rate limiting for tests or health check
        if settings.ENVIRONMENT == "test" or request.url.path in ("/health", "/docs", "/redoc", "/openapi.json"):
            return await call_next(request)

        org_id = request.headers.get("X-Org-ID")
        # If no explicit header, attempt extracting org_id from bearer token claim
        if not org_id:
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                try:
                    import jwt
                    token = auth_header[7:]
                    unverified = jwt.decode(token, options={"verify_signature": False})
                    org_id = unverified.get("org_id")
                except Exception:
                    pass

        if org_id:
            redis = get_redis_client()
            if redis is not None:
                current_minute = int(time.time() // 60)
                key = f"ratelimit:{org_id}:{current_minute}"
                try:
                    count = await redis.incr(key)
                    if count == 1:
                        await redis.expire(key, 120)

                    if count > self.max_requests_per_minute:
                        return JSONResponse(
                            status_code=429,
                            content={
                                "error": {
                                    "code": "TENANT_RATE_LIMIT_EXCEEDED",
                                    "message": "Organization request limit exceeded. Please wait before retrying.",
                                    "extra": {
                                        "limit_per_minute": self.max_requests_per_minute,
                                        "current_count": count,
                                    },
                                }
                            },
                            headers={"Retry-After": "60"},
                        )
                except Exception as e:
                    logger.debug(f"Rate limiting check bypassed due to Redis error: {e}")

        return await call_next(request)
