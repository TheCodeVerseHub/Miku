"""Initial database schema

This migration creates all tables that Miku currently defines in
src/utils/database.py's init_db() function. Subsequent migrations should
be created with `alembic revision --autogenerate -m "description"`.

Revision ID: 0001
Revises: None
Create Date: 2026-07-16
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── User Levels ──────────────────────────────────────────────────
    op.create_table(
        "user_levels",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("xp", sa.BigInteger(), server_default="0"),
        sa.Column("level", sa.Integer(), server_default="0"),
        sa.Column("messages", sa.Integer(), server_default="0"),
        sa.Column(
            "last_message_time",
            sa.Double(precision=53),
            server_default="0",
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(),
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(),
            server_default=sa.text("NOW()"),
        ),
        sa.PrimaryKeyConstraint("user_id", "guild_id"),
    )
    op.create_index(
        "idx_user_levels_guild_xp",
        "user_levels",
        ["guild_id", sa.text("xp DESC")],
    )

    # ── Guild Settings ───────────────────────────────────────────────
    op.create_table(
        "guild_settings",
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("levelup_channel_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "xp_enabled",
            sa.Boolean(),
            server_default=sa.text("TRUE"),
        ),
        sa.Column("min_xp", sa.Integer(), server_default="15"),
        sa.Column("max_xp", sa.Integer(), server_default="25"),
        sa.Column("cooldown_seconds", sa.Integer(), server_default="60"),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(),
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(),
            server_default=sa.text("NOW()"),
        ),
        sa.PrimaryKeyConstraint("guild_id"),
    )

    # ── Role Rewards ─────────────────────────────────────────────────
    op.create_table(
        "role_rewards",
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("level", sa.Integer(), nullable=False),
        sa.Column("role_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(),
            server_default=sa.text("NOW()"),
        ),
        sa.PrimaryKeyConstraint("guild_id", "level"),
    )
    op.create_index(
        "idx_role_rewards_guild",
        "role_rewards",
        ["guild_id"],
    )

    # ── XP Settings ──────────────────────────────────────────────────
    op.create_table(
        "xp_settings",
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "formula_name",
            sa.String(64),
            server_default="quadratic",
        ),
        sa.Column("min_xp", sa.Integer(), server_default="15"),
        sa.Column("max_xp", sa.Integer(), server_default="25"),
        sa.Column("cooldown_seconds", sa.Integer(), server_default="60"),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(),
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(),
            server_default=sa.text("NOW()"),
        ),
        sa.PrimaryKeyConstraint("guild_id"),
    )

    # ── XP Multipliers ───────────────────────────────────────────────
    op.create_table(
        "xp_multipliers",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("target_type", sa.String(32), nullable=False),
        sa.Column("target_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "multiplier",
            sa.Numeric(5, 2),
            server_default=sa.text("1.00"),
            nullable=False,
        ),
        sa.Column("label", sa.String(128), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(),
            server_default=sa.text("NOW()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("guild_id", "target_type", "target_id"),
    )
    op.create_index(
        "idx_xp_multipliers_guild",
        "xp_multipliers",
        ["guild_id"],
    )

    # ── XP Restrictions ──────────────────────────────────────────────
    op.create_table(
        "xp_restrictions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("restriction_type", sa.String(32), nullable=False),
        sa.Column("target_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(),
            server_default=sa.text("NOW()"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_xp_restrictions_guild",
        "xp_restrictions",
        ["guild_id"],
    )

    # ── XP Log ───────────────────────────────────────────────────────
    op.create_table(
        "xp_log",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("reason", sa.String(512), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(),
            server_default=sa.text("NOW()"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_xp_log_guild",
        "xp_log",
        [sa.text("guild_id"), sa.text("created_at DESC")],
    )
    op.create_index(
        "idx_xp_log_user",
        "xp_log",
        [sa.text("guild_id"), sa.text("user_id"), sa.text("created_at DESC")],
    )

    # ── Audit Log ────────────────────────────────────────────────────
    op.create_table(
        "audit_log",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("admin_id", sa.BigInteger(), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column(
            "details",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(),
            server_default=sa.text("NOW()"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_audit_log_guild",
        "audit_log",
        [sa.text("guild_id"), sa.text("created_at DESC")],
    )


def downgrade() -> None:
    """Drop all tables (reversible)."""
    op.drop_table("audit_log")
    op.drop_table("xp_log")
    op.drop_table("xp_restrictions")
    op.drop_table("xp_multipliers")
    op.drop_table("xp_settings")
    op.drop_table("role_rewards")
    op.drop_table("guild_settings")
    op.drop_table("user_levels")
