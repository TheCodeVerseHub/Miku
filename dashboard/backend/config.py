"""Dashboard configuration loaded from environment variables."""

import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()


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
            "DASHBOARD_SESSION_SECRET", "change-me-in-production"
        )
    )
    database_url: str = field(default_factory=lambda: os.getenv("DATABASE_URL", ""))
    bot_token: str = field(default_factory=lambda: os.getenv("DISCORD_BOT_TOKEN", ""))
    host: str = field(default_factory=lambda: os.getenv("DASHBOARD_HOST", "0.0.0.0"))
    port: int = field(default_factory=lambda: int(os.getenv("DASHBOARD_PORT", "8000")))


config = DashboardConfig()
