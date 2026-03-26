"""
Async GitHub REST API v3 client for Miku Bot.

Provides methods to fetch repository info, user profiles, and search
GitHub — all using aiohttp (already a bot dependency).

Usage inside a cog:
    client = GitHubClient(token=os.getenv("GITHUB_TOKEN"))
    data   = await client.get_repo("python", "cpython")
    await client.close()
"""

import asyncio
import logging
import os
import time
from typing import Any

import aiohttp
from cachetools import TTLCache

logger = logging.getLogger("miku.github")

# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------


class GitHubAPIError(Exception):
    """Base exception for GitHub API errors."""

    def __init__(self, message: str, status: int = 0) -> None:
        self.status = status
        super().__init__(message)


class GitHubNotFoundError(GitHubAPIError):
    """Raised when the requested resource does not exist (HTTP 404)."""


class GitHubRateLimitError(GitHubAPIError):
    """Raised when the GitHub API rate limit has been exceeded."""


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class GitHubClient:
    """Async GitHub REST API v3 client with optional authentication and caching."""

    BASE_URL = "https://api.github.com"

    def __init__(self, *, token: str | None = None) -> None:
        self._token = token
        self._http: aiohttp.ClientSession | None = None
        self._cache: TTLCache[str, dict | list] = TTLCache(maxsize=256, ttl=120)

        if not self._token:
            logger.warning(
                "No GITHUB_TOKEN set — using unauthenticated requests (60 req/hr). "
                "Set GITHUB_TOKEN in .env for 5 000 req/hr."
            )

    # -- session management --------------------------------------------------

    def _get_session(self) -> aiohttp.ClientSession:
        """Return the shared session, creating it lazily on first use."""
        if self._http is None or self._http.closed:
            headers: dict[str, str] = {
                "Accept": "application/vnd.github+json",
                "User-Agent": "Miku-Discord-Bot",
            }
            if self._token:
                headers["Authorization"] = f"Bearer {self._token}"
            self._http = aiohttp.ClientSession(
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=15),
            )
        return self._http

    async def close(self) -> None:
        """Close the underlying HTTP session."""
        if self._http and not self._http.closed:
            await self._http.close()

    # -- core request --------------------------------------------------------

    async def _request(
        self,
        endpoint: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> dict | list:
        """Perform a GET request against the GitHub API.

        Args:
            endpoint: API path (e.g. ``/repos/python/cpython``).
            params: Optional query-string parameters.

        Returns:
            Parsed JSON response.

        Raises:
            GitHubNotFoundError: If the resource was not found (404).
            GitHubRateLimitError: If the rate limit has been exceeded.
            GitHubAPIError: For any other API / network error.
        """
        cache_key = f"{endpoint}?{params}" if params else endpoint
        if cache_key in self._cache:
            return self._cache[cache_key]

        session = self._get_session()

        try:
            async with session.get(f"{self.BASE_URL}{endpoint}", params=params) as resp:
                # Rate-limit check
                remaining = resp.headers.get("X-RateLimit-Remaining")
                reset_at = resp.headers.get("X-RateLimit-Reset")

                if resp.status == 404:
                    raise GitHubNotFoundError("Resource not found", status=404)

                if resp.status == 403 and remaining == "0":
                    reset_ts = int(reset_at) if reset_at else 0
                    wait = max(reset_ts - int(time.time()), 0)
                    raise GitHubRateLimitError(
                        f"GitHub API rate limit exceeded. Resets in {wait // 60}m {wait % 60}s.",
                        status=403,
                    )

                if resp.status != 200:
                    text = await resp.text()
                    raise GitHubAPIError(
                        f"GitHub API returned {resp.status}: {text[:200]}",
                        status=resp.status,
                    )

                data = await resp.json()
                self._cache[cache_key] = data
                return data

        except (GitHubAPIError, GitHubNotFoundError, GitHubRateLimitError):
            raise
        except asyncio.TimeoutError:
            raise GitHubAPIError("Request to GitHub timed out", status=0)
        except aiohttp.ClientError as exc:
            raise GitHubAPIError(f"HTTP error: {exc}", status=0)

    # -- high-level methods --------------------------------------------------

    async def get_repo(self, owner: str, repo: str) -> dict:
        """Fetch repository information.

        Args:
            owner: Repository owner (user or org).
            repo: Repository name.

        Returns:
            Repository data dict from the GitHub API.
        """
        return await self._request(f"/repos/{owner}/{repo}")

    async def get_user(self, username: str) -> dict:
        """Fetch a user or organization profile.

        Args:
            username: GitHub login handle.

        Returns:
            User data dict from the GitHub API.
        """
        return await self._request(f"/users/{username}")

    async def search_repos(self, query: str, *, per_page: int = 5) -> dict:
        """Search repositories.

        Args:
            query: Free-text search query.
            per_page: Max results to return (default 5).

        Returns:
            Search result dict with ``total_count`` and ``items``.
        """
        return await self._request(
            "/search/repositories",
            params={"q": query, "per_page": per_page},
        )

    async def search_users(self, query: str, *, per_page: int = 5) -> dict:
        """Search users and organizations.

        Args:
            query: Free-text search query.
            per_page: Max results to return (default 5).

        Returns:
            Search result dict with ``total_count`` and ``items``.
        """
        return await self._request(
            "/search/users",
            params={"q": query, "per_page": per_page},
        )
