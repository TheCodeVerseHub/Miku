"""Tests for the dashboard rate limiter (`dashboard/backend/security.py`).

Regression: the store was a `defaultdict(list)` that pruned timestamps but never
keys, so every new IP/path pair left a permanent entry behind - an
unauthenticated caller could grow the process's memory. Keys were also
per-path, which multiplied the allowance by the number of endpoints, and they
used `request.client.host`, i.e. the *proxy's* address in the documented
reverse-proxy deployment, putting every user in one bucket.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from dashboard.backend.security import RateLimiter, client_identity


class FakeClock:
    """Deterministic replacement for `time.monotonic`."""

    def __init__(self, start: float = 1000.0):
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def _request(host: str | None, forwarded: str | None = None) -> MagicMock:
    request = MagicMock()
    request.client = MagicMock(host=host) if host else None
    headers = {}
    if forwarded is not None:
        headers["x-forwarded-for"] = forwarded
    request.headers = headers
    return request


class TestRateLimiter:
    def test_allows_up_to_the_limit_then_blocks(self):
        clock = FakeClock()
        limiter = RateLimiter(max_requests=3, window_seconds=60, timer=clock)

        assert [limiter.check("k")[0] for _ in range(3)] == [True, True, True]

        allowed, retry_after = limiter.check("k")
        assert allowed is False
        assert retry_after == 60

    def test_window_slides(self):
        clock = FakeClock()
        limiter = RateLimiter(max_requests=1, window_seconds=60, timer=clock)

        assert limiter.check("k")[0] is True
        assert limiter.check("k")[0] is False

        clock.advance(61)
        assert limiter.check("k")[0] is True

    def test_retry_after_counts_down(self):
        clock = FakeClock()
        limiter = RateLimiter(max_requests=1, window_seconds=60, timer=clock)
        limiter.check("k")

        clock.advance(30)
        allowed, retry_after = limiter.check("k")
        assert allowed is False
        assert retry_after == 30

    def test_separate_callers_get_separate_buckets(self):
        clock = FakeClock()
        limiter = RateLimiter(max_requests=1, window_seconds=60, timer=clock)

        assert limiter.check("a")[0] is True
        assert limiter.check("b")[0] is True
        assert limiter.check("a")[0] is False

    def test_idle_callers_are_forgotten(self):
        """The memory leak: keys used to accumulate forever."""
        clock = FakeClock()
        limiter = RateLimiter(max_requests=5, window_seconds=60, timer=clock)

        for i in range(500):
            limiter.check(f"client-{i}")
        assert limiter.tracked_keys() == 500

        clock.advance(61)
        assert limiter.tracked_keys() == 0

    def test_store_never_exceeds_max_keys(self):
        clock = FakeClock()
        limiter = RateLimiter(max_requests=5, window_seconds=60, max_keys=10, timer=clock)

        for i in range(1000):
            limiter.check(f"client-{i}")

        assert limiter.tracked_keys() <= 10

    def test_reset_clears_a_caller(self):
        clock = FakeClock()
        limiter = RateLimiter(max_requests=1, window_seconds=60, timer=clock)
        limiter.check("k")

        limiter.reset("k")

        assert limiter.check("k")[0] is True


class TestClientIdentity:
    def test_uses_the_socket_address_by_default(self):
        assert client_identity(_request("10.0.0.9"), trusted_proxy=False) == "10.0.0.9"

    def test_ignores_forwarded_for_unless_a_proxy_is_declared(self):
        request = _request("10.0.0.9", forwarded="1.2.3.4")

        assert client_identity(request, trusted_proxy=False) == "10.0.0.9"

    def test_uses_the_first_hop_when_a_proxy_is_declared(self):
        request = _request("10.0.0.9", forwarded="1.2.3.4, 10.0.0.9")

        assert client_identity(request, trusted_proxy=True) == "1.2.3.4"

    def test_falls_back_when_the_header_is_missing_or_empty(self):
        assert client_identity(_request("10.0.0.9"), trusted_proxy=True) == "10.0.0.9"
        assert (
            client_identity(_request("10.0.0.9", forwarded="  "), trusted_proxy=True)
            == "10.0.0.9"
        )

    def test_survives_a_request_without_a_client(self):
        assert client_identity(_request(None), trusted_proxy=False) == "unknown"


@pytest.fixture
def client():
    from dashboard.backend.main import app

    return TestClient(app)


@pytest.fixture(autouse=True)
def fresh_limiters():
    """Keep limiter state (and patched limits) local to each test."""
    from dashboard.backend import security

    limiters = (security.auth_limiter, security.api_limiter)
    saved = [limiter.max_requests for limiter in limiters]
    for limiter in limiters:
        limiter._requests.clear()
    yield
    for limiter, max_requests in zip(limiters, saved, strict=True):
        limiter.max_requests = max_requests
        limiter._requests.clear()


class TestMiddlewareBuckets:
    def test_distinct_paths_share_one_allowance(self, client):
        """Spreading requests across endpoints must not multiply the limit."""
        from dashboard.backend import security

        security.api_limiter.max_requests = 3
        paths = [f"/api/guilds/{10**16 + i}/settings" for i in range(4)]

        statuses = [client.get(path).status_code for path in paths]

        assert statuses[:3] == [401, 401, 401]
        assert statuses[3] == 429

    def test_auth_endpoints_have_their_own_stricter_limit(self, client):
        from dashboard.backend import security

        security.auth_limiter.max_requests = 2

        # `/auth/login` redirects to Discord, so only check it is not a 429 yet.
        assert client.get("/auth/login").status_code != 429
        assert client.get("/auth/login").status_code != 429
        response = client.get("/auth/login")
        assert response.status_code == 429
        assert "Retry-After" in response.headers

        # The API bucket was not touched by the auth requests.
        assert client.get("/api/me").status_code == 401

    def test_forwarded_for_cannot_forge_a_fresh_bucket(self, client):
        from dashboard.backend import security

        security.api_limiter.max_requests = 1

        assert client.get("/api/me", headers={"X-Forwarded-For": "1.1.1.1"}).status_code == 401
        assert client.get("/api/me", headers={"X-Forwarded-For": "2.2.2.2"}).status_code == 429
