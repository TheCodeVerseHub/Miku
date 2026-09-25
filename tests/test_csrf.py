"""Tests for the dashboard CSRF middleware (`dashboard/backend/security.py`).

Regression: `generate_csrf_token`/`validate_csrf_token` existed but nothing
called them - the middleware only wrote a `logger.debug` line when a
state-changing request arrived without a token. The entire protection rested on
the session cookie being `SameSite=strict`, so any deployment that weakened or
lost that flag (or a browser that ignores it) had no CSRF defence at all, with
signed admin endpoints like `/setlevel` and `/addxp` behind it.

The token is now a real double submit: a signed token in a JS-readable cookie,
repeated in the `X-CSRF-Token` header. The middleware rejects the request
unless the two match *and* the cookie verifies against the session secret.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from dashboard.backend.config import config
from dashboard.backend.security import (
    CSRF_COOKIE_NAME,
    CSRF_HEADER_NAME,
    generate_csrf_token,
)

SECRET = config.session_secret
GUILD_ID = 123456789012345678
USER_ID = 876543210987654321
WRITE_PATH = f"/api/guilds/{GUILD_ID}/users/{USER_ID}/setlevel"


@pytest.fixture
def client():
    from dashboard.backend.main import app

    return TestClient(app)


@pytest.fixture
def token() -> str:
    return generate_csrf_token(SECRET)


def test_signed_token_round_trips():
    from dashboard.backend.security import validate_csrf_token

    assert validate_csrf_token(generate_csrf_token(SECRET), SECRET)
    assert not validate_csrf_token(f"{generate_csrf_token(SECRET)}x", SECRET)
    assert not validate_csrf_token("nonsense", SECRET)


class TestWritesRequireAToken:
    def test_session_without_a_token_is_rejected(self, client):
        client.cookies.set("session", "some-session")

        response = client.post(WRITE_PATH, json={"level": 5})

        assert response.status_code == 403
        assert response.json()["code"] == "csrf_failed"

    def test_cookie_without_the_header_is_rejected(self, client, token):
        client.cookies.set("session", "some-session")
        client.cookies.set(CSRF_COOKIE_NAME, token)

        assert client.post(WRITE_PATH, json={"level": 5}).status_code == 403

    def test_header_must_match_the_cookie(self, client, token):
        client.cookies.set("session", "some-session")
        client.cookies.set(CSRF_COOKIE_NAME, token)

        response = client.post(
            WRITE_PATH,
            json={"level": 5},
            headers={CSRF_HEADER_NAME: generate_csrf_token(SECRET)},
        )

        assert response.status_code == 403

    def test_unsigned_cookie_is_rejected_even_when_repeated(self, client):
        """An attacker on a sibling subdomain can set this cookie but not sign it."""
        client.cookies.set("session", "some-session")
        client.cookies.set(CSRF_COOKIE_NAME, "forged:token:value")

        response = client.post(
            WRITE_PATH,
            json={"level": 5},
            headers={CSRF_HEADER_NAME: "forged:token:value"},
        )

        assert response.status_code == 403

    def test_delete_is_guarded_too(self, client):
        client.cookies.set("session", "some-session")

        response = client.delete(f"/api/guilds/{GUILD_ID}/levels")

        assert response.status_code == 403

    def test_matching_token_passes_the_csrf_layer(self, client, token):
        """The request gets past CSRF and fails later, at authentication."""
        client.cookies.set("session", "not-a-real-session")
        client.cookies.set(CSRF_COOKIE_NAME, token)

        response = client.post(
            WRITE_PATH,
            json={"level": 5},
            headers={CSRF_HEADER_NAME: token},
        )

        assert response.status_code == 401


class TestTokenIssuanceAndExemptions:
    def test_page_load_hands_out_a_token(self, client):
        client.cookies.set("session", "some-session")

        response = client.get("/dashboard")

        assert CSRF_COOKIE_NAME in response.cookies

    def test_anonymous_page_load_gets_no_token(self, client):
        response = client.get("/")

        assert CSRF_COOKIE_NAME not in response.cookies

    def test_reads_are_never_blocked(self, client):
        client.cookies.set("session", "some-session")

        response = client.get("/api/me")

        assert response.status_code == 401
        assert response.json().get("code") != "csrf_failed"

    def test_auth_flow_is_exempt(self, client):
        """The OAuth callback is protected by `state`, not by a token."""
        client.cookies.set("session", "some-session")

        response = client.post("/auth/callback?code=x&state=y")

        assert response.status_code != 403

    def test_anonymous_writes_still_report_401(self, client):
        """No session means nothing to forge - do not mask it as 403."""
        response = client.post(WRITE_PATH, json={"level": 5})

        assert response.status_code == 401
