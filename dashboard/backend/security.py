"""
Security middleware for the Miku Dashboard.

Provides:
- CSRF protection for state-changing requests
- Rate limiting (in-memory, per-IP)
- Security headers middleware
- Input validation helpers
"""

import hashlib
import hmac
import logging
import os
import time
from collections.abc import Callable

from cachetools import TTLCache
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("dashboard.security")


# ──────────────────────────────────────────────────────────────────────
# Rate Limiter
# ──────────────────────────────────────────────────────────────────────


class RateLimiter:
    """In-memory sliding-window rate limiter with a bounded store.

    The store is a `TTLCache`: a client that goes quiet for a whole window is
    forgotten, and a hard `maxsize` caps how many clients can be remembered at
    once. The previous `defaultdict(list)` pruned timestamps but never keys, so
    every new IP/path pair added a permanent entry - an unauthenticated caller
    could grow the process's memory without ever authenticating.
    """

    def __init__(
        self,
        max_requests: int = 60,
        window_seconds: int = 60,
        max_keys: int = 10_000,
        timer: Callable[[], float] = time.monotonic,
    ):
        self.max_requests = max_requests
        self.window = window_seconds
        self._timer = timer
        # `ttl == window` is safe: when an idle key expires, everything it holds
        # is already outside the sliding window, so no history is really lost.
        self._requests: TTLCache = TTLCache(
            maxsize=max_keys, ttl=window_seconds, timer=timer
        )

    def check(self, key: str) -> tuple[bool, int]:
        """Check if *key* is rate-limited.

        Returns:
            (allowed: bool, retry_after_seconds: int)
        """
        now = self._timer()
        window_start = now - self.window

        self._requests.expire()  # drop clients that have gone quiet
        timestamps = [t for t in self._requests.get(key, ()) if t > window_start]

        if len(timestamps) >= self.max_requests:
            # Re-insert so an active (but blocked) client does not lose the
            # history that is still keeping it blocked.
            self._requests[key] = timestamps
            retry_after = int(self.window - (now - timestamps[0]))
            return False, max(1, retry_after)

        timestamps.append(now)
        self._requests[key] = timestamps
        return True, 0

    def reset(self, key: str) -> None:
        self._requests.pop(key, None)

    def tracked_keys(self) -> int:
        """Number of clients currently remembered (for tests/metrics)."""
        self._requests.expire()
        return len(self._requests)


def client_identity(request: Request, trusted_proxy: bool = False) -> str:
    """Identify the caller for rate-limiting purposes.

    Behind the reverse proxy this dashboard is documented to run behind,
    `request.client.host` is the *proxy's* address, so every user shares one
    bucket: one client could exhaust it for everybody. `X-Forwarded-For` is only
    believed when the operator has declared a proxy in front (`TRUSTED_PROXY`),
    because otherwise a client can hand itself a fresh bucket per request.
    """
    if trusted_proxy:
        forwarded = request.headers.get("x-forwarded-for", "")
        first = forwarded.split(",")[0].strip()
        if first:
            return first
    return request.client.host if request.client else "unknown"


# Global rate limiter instances
auth_limiter = RateLimiter(max_requests=10, window_seconds=60)  # 10 auth req/min
api_limiter = RateLimiter(max_requests=120, window_seconds=60)  # 120 API req/min


# ──────────────────────────────────────────────────────────────────────
# CSRF Protection
# ──────────────────────────────────────────────────────────────────────


#: Name of the cookie that carries the token, and of the header that must
#: repeat it. The cookie is deliberately *not* HttpOnly: the dashboard's
#: JavaScript has to read it to echo it back in the header (double submit).
CSRF_COOKIE_NAME = "csrf"
CSRF_HEADER_NAME = "X-CSRF-Token"
#: Same lifetime as the session cookie it is paired with.
CSRF_MAX_AGE_SECONDS = 86400 * 7

#: Methods that need a token: they change state.
UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
#: The OAuth callback/redirect flow is protected by the `state` parameter.
CSRF_EXEMPT_PREFIXES = ("/auth/",)


def generate_csrf_token(secret: str) -> str:
    """Generate a CSRF token using HMAC."""
    data = f"{os.urandom(32).hex()}:{int(time.time())}"
    sig = hmac.new(secret.encode(), data.encode(), hashlib.sha256).hexdigest()[:16]
    return f"{data}:{sig}"


def validate_csrf_token(token: str, secret: str, max_age: int = 3600) -> bool:
    """Validate a CSRF token."""
    try:
        parts = token.split(":")
        if len(parts) != 3:
            return False
        data = f"{parts[0]}:{parts[1]}"
        expected_sig = hmac.new(secret.encode(), data.encode(), hashlib.sha256).hexdigest()[:16]
        if not hmac.compare_digest(parts[2], expected_sig):
            return False
        timestamp = int(parts[1])
        return not time.time() - timestamp > max_age
    except (ValueError, IndexError):
        return False


# ──────────────────────────────────────────────────────────────────────
# Security Headers Middleware
# ──────────────────────────────────────────────────────────────────────


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        # Content-Security-Policy — relaxed for Alpine.js and Chart.js CDN
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' https://cdn.jsdelivr.net 'unsafe-inline' 'unsafe-eval'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' https://cdn.discordapp.com data:; "
            "connect-src 'self'; "
            "font-src 'self'; "
            "object-src 'none'"
        )
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response


# ──────────────────────────────────────────────────────────────────────
# Input Validation
# ──────────────────────────────────────────────────────────────────────


def sanitize_search_query(query: str, max_length: int = 100) -> str:
    """Sanitize a search query to prevent injection."""
    # Only allow alphanumeric, spaces, hyphens, underscores, @, #, .
    import re
    clean = re.sub(r'[^a-zA-Z0-9\s\-_@#.]', '', query)
    return clean[:max_length]


def validate_guild_id(guild_id: int) -> bool:
    """Validate a Discord guild/snowflake ID."""
    return 10**16 <= guild_id < 10**20  # Discord snowflakes are 17-19 digits


def validate_user_id(user_id: int) -> bool:
    """Validate a Discord user/snowflake ID."""
    return 10**16 <= user_id < 10**20


def validate_level(level: int) -> bool:
    """Validate a level value (0-100000)."""
    return 0 <= level <= 100000


def validate_xp_amount(amount: int) -> bool:
    """Validate an XP amount (-10M to 10M)."""
    return -10_000_000 <= amount <= 10_000_000


# ──────────────────────────────────────────────────────────────────────
# Setup function
# ──────────────────────────────────────────────────────────────────────


def csrf_token_is_valid(cookie_token: str, header_token: str, secret: str) -> bool:
    """True if the header repeats the signed cookie token.

    The cookie is compared against the header (a cross-site attacker can make
    the browser *send* the cookie but cannot read it), and the cookie is checked
    against its signature (an attacker on a sibling subdomain can *set* a cookie
    but cannot sign one). Both halves are needed for the double-submit pattern
    to mean anything.
    """
    if not cookie_token or not header_token:
        return False
    if not hmac.compare_digest(cookie_token, header_token):
        return False
    return validate_csrf_token(cookie_token, secret, max_age=CSRF_MAX_AGE_SECONDS)


def setup_security(
    app: FastAPI, session_secret: str, trusted_proxy: bool = False
) -> None:
    """Register all security middleware on the FastAPI app."""
    app.add_middleware(SecurityHeadersMiddleware)

    @app.middleware("http")
    async def rate_limit_middleware(request: Request, call_next: Callable) -> Response:
        path = request.url.path
        identity = client_identity(request, trusted_proxy)

        # Stricter rate limiting for auth endpoints. One bucket per caller:
        # keying on the path as well let a client multiply its allowance simply
        # by spreading requests over different endpoints.
        if path.startswith("/auth/"):
            allowed, retry_after = auth_limiter.check(f"auth:{identity}")
            if not allowed:
                return JSONResponse(
                    status_code=429,
                    content={"error": f"Too many requests. Try again in {retry_after}s."},
                    headers={"Retry-After": str(retry_after)},
                )

        if path.startswith("/api/"):
            allowed, retry_after = api_limiter.check(f"api:{identity}")
            if not allowed:
                return JSONResponse(
                    status_code=429,
                    content={"error": f"API rate limit exceeded. Try again in {retry_after}s."},
                    headers={"Retry-After": str(retry_after)},
                )

        return await call_next(request)

    # CSRF: a signed token in a readable cookie, repeated in a header.
    #
    # `SameSite=strict` on the session cookie already stops the classic
    # cross-site form POST, and the OAuth flow is protected by `state`. But the
    # old middleware only *logged* the absence of a token while the (dead)
    # `generate_csrf_token`/`validate_csrf_token` pair sat unused next to it, so
    # the protection disappeared the moment anything weakened the cookie flags
    # (a reverse proxy rewrite, `secure=False` for local development, an old
    # browser that ignores SameSite). It is enforced now.
    @app.middleware("http")
    async def csrf_middleware(request: Request, call_next: Callable) -> Response:
        """Enforce the double-submit token on session-carrying writes."""
        path = request.url.path
        csrf_cookie = request.cookies.get(CSRF_COOKIE_NAME, "")
        exempt = path.startswith(CSRF_EXEMPT_PREFIXES)
        # Requests without a session have nothing to forge, and rejecting them
        # here would turn a clear 401 into a 403.
        has_session = bool(request.cookies.get("session"))

        if (
            request.method in UNSAFE_METHODS
            and not exempt
            and (has_session or csrf_cookie)
            and not csrf_token_is_valid(
                csrf_cookie,
                request.headers.get(CSRF_HEADER_NAME, ""),
                session_secret,
            )
        ):
            logger.warning(
                "Rejected %s %s: missing or invalid CSRF token", request.method, path
            )
            return JSONResponse(
                status_code=403,
                content={"error": "Invalid or missing CSRF token", "code": "csrf_failed"},
            )

        response = await call_next(request)

        # Make sure every page load that carries a session also carries a token,
        # so the JavaScript on that page has one to echo back.
        if has_session and (
            not csrf_cookie
            or not validate_csrf_token(csrf_cookie, session_secret, max_age=CSRF_MAX_AGE_SECONDS)
        ):
            response.set_cookie(
                CSRF_COOKIE_NAME,
                generate_csrf_token(session_secret),
                max_age=CSRF_MAX_AGE_SECONDS,
                httponly=False,
                secure=True,
                samesite="strict",
            )
        return response

    logger.info("Security middleware configured: CSRF, rate limiting, security headers")
