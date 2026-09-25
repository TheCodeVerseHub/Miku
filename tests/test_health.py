"""Tests for the dashboard's public endpoints (`health.py`, `/api/bot/stats`).

Two problems are pinned down here:

1. `/health/db` returned HTTP 200 with `{"status": "error", "error": "<str(e)>"}`,
   so a naive monitor saw a healthy service *and* every caller got the raw
   database error - which for asyncpg can include host, port, role and DSN.
2. `/api/bot/stats` had no authentication at all, exposing the bot's global user
   count, XP total and message volume to anyone who could reach the port.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# A realistic asyncpg failure: the message names the host, port and role.
DB_ERROR = (
    'password authentication failed for user "miku" '
    "(host=postgres port=5432 database=miku)"
)


def _fake_pool(conn: MagicMock) -> MagicMock:
    """A stand-in for `asyncpg.Pool` usable as `async with pool.acquire()`."""
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock(return_value=False)
    pool = MagicMock()
    pool.acquire.return_value = cm
    return pool


@pytest.fixture
def client():
    from dashboard.backend.main import app

    return TestClient(app)


@pytest.fixture
def working_db():
    conn = MagicMock()
    conn.fetchval = AsyncMock(return_value=1)
    pool = _fake_pool(conn)
    with patch(
        "dashboard.backend.database.get_db", AsyncMock(return_value=pool)
    ) as get_db:
        yield get_db


@pytest.fixture
def broken_db():
    with patch(
        "dashboard.backend.database.get_db",
        AsyncMock(side_effect=RuntimeError(DB_ERROR)),
    ):
        yield


class TestHealthEndpoints:
    def test_liveness_stays_public(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_db_check_reports_success(self, client, working_db):
        response = client.get("/health/db")
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "database": "connected"}

    def test_db_check_fails_with_503(self, client, broken_db):
        response = client.get("/health/db")
        assert response.status_code == 503
        assert response.json()["database"] == "disconnected"

    def test_db_check_does_not_leak_the_error(self, client, broken_db):
        body = client.get("/health/db").text
        assert "password authentication failed" not in body
        assert "postgres" not in body
        assert "miku" not in body
        # The exception type is still reported, because it is genuinely useful
        # to an operator and reveals nothing about the deployment.
        assert "RuntimeError" in body

    def test_readiness_returns_503_when_the_database_is_down(self, client, broken_db):
        response = client.get("/health/ready")
        assert response.status_code == 503
        assert response.json()["status"] == "not_ready"

    def test_readiness_is_ready_when_the_database_answers(self, client, working_db):
        response = client.get("/health/ready")
        assert response.status_code == 200
        assert response.json()["status"] == "ready"


class TestBotStatsRequiresAuth:
    # `main.py` binds `get_db` at import time, so the endpoint's own reference is
    # what has to be patched to observe whether the database was touched.
    def test_anonymous_request_is_rejected(self, client):
        with patch("dashboard.backend.main.get_db", AsyncMock()) as get_db:
            response = client.get("/api/bot/stats")

        assert response.status_code == 401
        assert response.json()["detail"] == "Not authenticated"
        # It must not even reach the database.
        get_db.assert_not_awaited()

    def test_expired_session_is_rejected(self, client):
        client.cookies.set("session", "not-a-valid-token")
        with patch("dashboard.backend.main.get_db", AsyncMock()) as get_db:
            response = client.get("/api/bot/stats")

        assert response.status_code == 401
        get_db.assert_not_awaited()

    def test_authenticated_request_still_gets_the_stats(self, client):
        """Requiring a session must not break the statistics themselves."""
        conn = MagicMock()
        conn.fetchval = AsyncMock(side_effect=[3, 42, 9000, 5000])

        with (
            patch("dashboard.backend.main.require_auth", AsyncMock(return_value={})),
            patch(
                "dashboard.backend.main.get_db",
                AsyncMock(return_value=_fake_pool(conn)),
            ),
        ):
            response = client.get("/api/bot/stats")

        assert response.status_code == 200
        assert response.json() == {
            "guild_count": 3,
            "user_count": 42,
            "total_xp": 9000,
            "total_messages": 5000,
        }
