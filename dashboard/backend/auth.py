"""Discord OAuth2 authentication for the dashboard."""

import logging
from urllib.parse import urlencode


import httpx

from .config import config

logger = logging.getLogger("dashboard.auth")

DISCORD_API = "https://discord.com/api/v10"

SCOPES = ["identify", "guilds"]


def get_oauth_url(state: str) -> str:
    params = {
        "client_id": config.discord_client_id,
        "redirect_uri": config.discord_redirect_uri,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "state": state,
    }
    return f"{DISCORD_API}/oauth2/authorize?{urlencode(params)}"


async def exchange_code(code: str) -> dict | None:
    data = {
        "client_id": config.discord_client_id,
        "client_secret": config.discord_client_secret,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": config.discord_redirect_uri,
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{DISCORD_API}/oauth2/token", data=data, headers=headers
        )
        if resp.status_code != 200:
            logger.error("Token exchange failed: %s %s", resp.status_code, resp.text)
            return None
        return resp.json()


async def refresh_token(refresh_token: str) -> dict | None:
    data = {
        "client_id": config.discord_client_id,
        "client_secret": config.discord_client_secret,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{DISCORD_API}/oauth2/token", data=data, headers=headers
        )
        if resp.status_code != 200:
            logger.error("Token refresh failed: %s", resp.status_code)
            return None
        return resp.json()


async def get_current_user(access_token: str) -> dict | None:
    headers = {"Authorization": f"Bearer {access_token}"}
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{DISCORD_API}/users/@me", headers=headers)
        if resp.status_code != 200:
            return None
        return resp.json()


async def get_user_guilds(access_token: str) -> list[dict]:
    headers = {"Authorization": f"Bearer {access_token}"}
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{DISCORD_API}/users/@me/guilds", headers=headers
        )
        if resp.status_code != 200:
            return []
        return resp.json()
