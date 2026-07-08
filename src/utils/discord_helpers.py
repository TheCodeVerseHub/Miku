"""Shared Discord helpers for hybrid commands (send, defer)."""

from __future__ import annotations

import logging
from typing import Any

import discord
from discord.ext import commands

logger = logging.getLogger("miku.helpers")

__all__ = ("send", "maybe_defer")


async def send(
    ctx: commands.Context, *args: Any, **kwargs: Any
) -> discord.Message | None:
    """Send a message handling both prefix and slash invocations.

    - Strips ``ephemeral`` in prefix mode.
    - Falls back to ``ctx.channel.send()`` on unknown interaction (10062).
    - Falls back to ``interaction.followup.send()`` on ``InteractionResponded``.
    """
    interaction = getattr(ctx, "interaction", None)
    if interaction is None:
        kwargs.pop("ephemeral", None)
    try:
        return await ctx.send(*args, **kwargs)
    except discord.NotFound as e:
        if (
            interaction is not None
            and getattr(e, "code", None) == 10062
            and getattr(ctx, "channel", None) is not None
        ):
            kwargs.pop("ephemeral", None)
            return await ctx.channel.send(*args, **kwargs)
        raise
    except discord.InteractionResponded:
        if interaction is not None:
            return await interaction.followup.send(*args, **kwargs)
        raise


async def maybe_defer(ctx: commands.Context, *, ephemeral: bool = False) -> None:
    """Defer the interaction only when invoked as a slash command."""
    interaction = getattr(ctx, "interaction", None)
    if interaction is None:
        return
    if interaction.response.is_done():
        return
    try:
        await ctx.defer(ephemeral=ephemeral)
    except discord.NotFound, discord.HTTPException:
        return
