"""
Tests for the GitHub API client (src/utils/github_client.py).
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_client_initialization():
    """Test GitHubClient initializes without token."""
    from src.utils.github_client import GitHubClient

    client = GitHubClient()
    assert client._token is None
    assert client._http is None  # Lazy init

    await client.close()


@pytest.mark.asyncio
async def test_client_with_token():
    """Test GitHubClient initializes with token."""
    from src.utils.github_client import GitHubClient

    client = GitHubClient(token="ghp_test_token")
    assert client._token == "ghp_test_token"

    await client.close()


class MockResponse:
    """Mock aiohttp response."""

    def __init__(self, data, status=200, headers=None):
        self._data = data
        self.status = status
        self.headers = headers or {}

    async def json(self):
        return self._data

    async def text(self):
        return str(self._data)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


@pytest.mark.asyncio
async def test_get_repo_success():
    """Test successful repo fetch."""
    from src.utils.github_client import GitHubClient

    client = GitHubClient()
    mock_data = {
        "full_name": "python/cpython",
        "description": "Python programming language",
        "stargazers_count": 60000,
        "forks_count": 30000,
        "language": "Python",
    }

    with patch.object(client, "_request", AsyncMock(return_value=mock_data)):
        data = await client.get_repo("python", "cpython")
        assert data["full_name"] == "python/cpython"
        assert data["language"] == "Python"

    await client.close()


@pytest.mark.asyncio
async def test_get_user_success():
    """Test successful user fetch."""
    from src.utils.github_client import GitHubClient

    client = GitHubClient()
    mock_data = {
        "login": "octocat",
        "name": "The Octocat",
        "bio": "GitHub mascot",
        "public_repos": 8,
        "followers": 10000,
    }

    with patch.object(client, "_request", AsyncMock(return_value=mock_data)):
        data = await client.get_user("octocat")
        assert data["login"] == "octocat"

    await client.close()


@pytest.mark.asyncio
async def test_search_repos():
    """Test repository search."""
    from src.utils.github_client import GitHubClient

    client = GitHubClient()
    mock_data = {
        "total_count": 2,
        "items": [
            {"full_name": "repo1", "description": "First repo"},
            {"full_name": "repo2", "description": "Second repo"},
        ],
    }

    with patch.object(client, "_request", AsyncMock(return_value=mock_data)):
        data = await client.search_repos("discord bot")
        assert data["total_count"] == 2
        assert len(data["items"]) == 2

    await client.close()


@pytest.mark.asyncio
async def test_error_handling():
    """Test error handling for API failures."""
    from src.utils.github_client import (
        GitHubClient,
        GitHubNotFoundError,
        GitHubRateLimitError,
        GitHubAPIError,
    )

    client = GitHubClient()

    # Test 404
    with patch.object(client, "_request", AsyncMock(side_effect=GitHubNotFoundError("Not found", status=404))):
        with pytest.raises(GitHubNotFoundError):
            await client.get_repo("nonexistent", "repo")

    # Test rate limit
    with patch.object(client, "_request", AsyncMock(side_effect=GitHubRateLimitError("Rate limited", status=403))):
        with pytest.raises(GitHubRateLimitError):
            await client.get_user("test")

    # Test generic error
    with patch.object(client, "_request", AsyncMock(side_effect=GitHubAPIError("Server error", status=500))):
        with pytest.raises(GitHubAPIError):
            await client.search_repos("test")

    await client.close()
