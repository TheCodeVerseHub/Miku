"""
Dashboard configuration loaded from environment variables.

All sensitive values should be set via environment variables or .env file.
The defaults here are intentionally insecure to prompt you to set real values.
"""

import os
import logging
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("dashboard.config")


@dataclass
class DashboardConfig:
    discord_client_id: str = field(
        default_factory=lambda: os.getenv("DASHBOARD_CLIENT_ID", "")
    )
    discord_client_secret: str = field(
        default_factory=lambda: os.getenv("DASHBOARD_CLIENT_SECRET", "")
    )
    discord_redirect_uri: str = field(
        default_factory=lambda: os.getenv(
            "DASHBOARD_REDIRECT_URI", "http://localhost:8000/auth/callback"
        )
    )
    session_secret: str = field(
        default_factory=lambda: os.getenv(
            "DASHBOARD_SESSION_SECRET", ""
        )
    )
    database_url: str = field(
        default_factory=lambda: os.getenv("DATABASE_URL", "")
    )
    bot_token: str = field(
        default_factory=lambda: os.getenv("DISCORD_BOT_TOKEN", "")
    )
    host: str = field(default_factory=lambda: os.getenv("DASHBOARD_HOST", "0.0.0.0"))
    port: int = field(
        default_factory=lambda: int(os.getenv("DASHBOARD_PORT", "8000"))
    )


config = DashboardConfig()


def validate_config() -> None:
    """Validate that critical configuration values are set.

    Call this at startup to fail fast instead of crashing later.
    """
    errors = []

    if not config.discord_client_id:
        errors.append("DASHBOARD_CLIENT_ID is not set")
    if not config.discord_client_secret:
        errors.append("DASHBOARD_CLIENT_SECRET is not set")
    if not config.database_url:
        errors.append("DATABASE_URL is not set")
    if not config.discord_redirect_uri:
        errors.append("DASHBOARD_REDIRECT_URI is not set")
    if not config.session_secret:
        errors.append("DASHBOARD_SESSION_SECRET is not set. Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\"")
    elif len(config.session_secret) < 32:
        # Short secrets weaken session signing — this is a hard requirement.
        errors.append(
            f"DASHBOARD_SESSION_SECRET is too short ({len(config.session_secret)} chars, minimum 32)."
        )
    if not config.bot_token:
        errors.append("DISCORD_BOT_TOKEN is not set")

    if errors:
        for err in errors:
            logger.error("Configuration error: %s", err)
        raise RuntimeError(
            f"Dashboard configuration is incomplete: {'; '.join(errors)}"
        )

    logger.info("Dashboard configuration validated successfully")
