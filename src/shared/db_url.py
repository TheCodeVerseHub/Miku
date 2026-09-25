"""Normalisation of the `DATABASE_URL` DSN for each driver that consumes it.

The project has one `DATABASE_URL` env var but three consumers that want it in
different shapes:

- **asyncpg** (`utils/database.py`, `dashboard/backend/database.py`,
  `tests/conftest.py`) wants a plain ``postgresql://`` DSN. It raises
  ``ValueError: invalid URI scheme: postgresql+asyncpg`` for anything else, so
  the scheme used in ``.env.example``, ``docker-compose.yml``, the README and CI
  crashed the bot at startup with a message that says nothing about the DSN.
- **SQLAlchemy's async engine** (``alembic/env.py``, the legacy ``bot/``
  package) needs the explicit ``postgresql+asyncpg://`` driver suffix.
- plain ``postgres://`` (Heroku/Railway style) is accepted by neither as-is.

Rather than pick one blessed spelling and let the other two fail, everything
goes through these two functions, so any of the three spellings works.
"""

from __future__ import annotations

__all__ = ["to_async_sqlalchemy_url", "to_asyncpg_dsn"]

_POSTGRES_ALIASES = {"postgres": "postgresql"}


def _split(url: str) -> tuple[str, str] | None:
    """Split ``scheme://rest``, or return ``None`` for a malformed URL."""
    scheme, sep, rest = url.partition("://")
    if not sep or not scheme or not rest:
        return None
    # Credentials may contain '://'; partition() already handles that by taking
    # the first separator only.
    return scheme, rest


def to_asyncpg_dsn(url: str) -> str:
    """Return the URL in the form ``asyncpg`` accepts.

    >>> to_asyncpg_dsn("postgresql+asyncpg://u:p@db:5432/miku")
    'postgresql://u:p@db:5432/miku'
    >>> to_asyncpg_dsn("postgres://u:p@db:5432/miku")
    'postgresql://u:p@db:5432/miku'
    """
    if not url:
        return url
    split = _split(url)
    if split is None:
        return url
    scheme, rest = split
    base = _POSTGRES_ALIASES.get(scheme.split("+", 1)[0], scheme.split("+", 1)[0])
    return f"{base}://{rest}"


def to_async_sqlalchemy_url(url: str) -> str:
    """Return the URL in the form SQLAlchemy's async engine needs.

    The asyncpg driver is forced, because every caller of this function creates
    an asyncpg-backed engine. A sync driver suffix (e.g. ``+psycopg2``) is
    replaced rather than honoured.

    >>> to_async_sqlalchemy_url("postgresql://u:p@db:5432/miku")
    'postgresql+asyncpg://u:p@db:5432/miku'
    """
    if not url:
        return url
    split = _split(url)
    if split is None:
        return url
    scheme, rest = split
    base = scheme.split("+", 1)[0]
    base = _POSTGRES_ALIASES.get(base, base)
    return f"{base}+asyncpg://{rest}"
