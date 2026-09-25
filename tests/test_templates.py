"""Tests that dashboard templates escape untrusted values.

Regression: the Jinja environment was built as
``Environment(loader=FileSystemLoader(...))``, i.e. with autoescaping **off**.
Guild names are chosen by whoever controls a Discord server and are rendered
into these pages, so a server named ``<script>…</script>`` ran arbitrary script
in the dashboard session of anyone who opened that server's page - including
a session holding an OAuth token for every guild that user manages.

The templates also interpolated the name into Alpine ``x-text``/``:class``
JavaScript string literals, where HTML escaping alone does not save you (the
browser decodes entities before the JS parser sees the string), so that
context is gone too.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

PAYLOADS = [
    "<script>alert(1)</script>",
    '<img src=x onerror="alert(1)">',
    "'); alert('xss'); //",
    "\"><svg/onload=alert(1)>",
]

#: Pages that render a guild name, as (path, page-context) pairs.
PAGES = ["/guilds/123456789", "/guilds/123456789/leveling", "/guilds/123456789/settings"]


@pytest.fixture
def client():
    from dashboard.backend.main import app

    return TestClient(app)


def _get_page(client: TestClient, path: str, guild_name: str):
    guild = {"id": "123456789", "name": guild_name, "icon": None}

    with (
        patch(
            "dashboard.backend.main.require_guild_access",
            AsyncMock(return_value=({}, guild)),
        ),
        patch(
            "dashboard.backend.main.get_current_user",
            AsyncMock(return_value=None),
        ),
    ):
        return client.get(path)


def test_environment_autoescapes_html():
    from dashboard.backend.main import _jinja_env

    assert _jinja_env.autoescape("base.html") is True


@pytest.mark.parametrize("payload", PAYLOADS)
@pytest.mark.parametrize("path", PAGES)
def test_guild_name_is_escaped(client, path, payload):
    response = _get_page(client, path, payload)

    assert response.status_code == 200
    assert payload not in response.text, "untrusted guild name reached the page verbatim"
    assert "&#39;" in response.text or "&lt;" in response.text


def test_benign_guild_name_is_rendered(client):
    """Escaping must not break ordinary names."""
    response = _get_page(client, PAGES[0], "Miku & Friends")

    assert response.status_code == 200
    assert "Miku &amp; Friends" in response.text
