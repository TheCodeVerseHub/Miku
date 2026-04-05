"""Fun Cog - Light, non-moderation entertainment commands.

All commands are hybrid (prefix + slash).
"""

from __future__ import annotations

import logging
import random
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

logger = logging.getLogger("miku.fun")

EMBED_COLOR = discord.Color.from_rgb(88, 101, 242)  # Discord blurple


class Fun(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        logger.info("Fun cog loaded")

    async def _send(self, ctx: commands.Context, *args, **kwargs):
        if getattr(ctx, "interaction", None) is None:
            kwargs.pop("ephemeral", None)
        return await ctx.send(*args, **kwargs)

    @commands.hybrid_command(name="8ball", description="Ask the magic 8-ball a question")
    @app_commands.describe(question="Your question")
    async def eight_ball(self, ctx: commands.Context, *, question: str) -> None:
        responses = [
            "It is certain.",
            "Without a doubt.",
            "Yes — definitely.",
            "You may rely on it.",
            "As I see it, yes.",
            "Most likely.",
            "Outlook good.",
            "Yes.",
            "Signs point to yes.",
            "Reply hazy, try again.",
            "Ask again later.",
            "Better not tell you now.",
            "Cannot predict now.",
            "Concentrate and ask again.",
            "Don't count on it.",
            "My reply is no.",
            "My sources say no.",
            "Outlook not so good.",
            "Very doubtful.",
        ]
        embed = discord.Embed(title="🎱 Magic 8-Ball", color=EMBED_COLOR)
        embed.add_field(name="Question", value=question[:1024], inline=False)
        embed.add_field(name="Answer", value=random.choice(responses), inline=False)
        await self._send(ctx, embed=embed)

    @commands.hybrid_command(name="coinflip", description="Flip a coin")
    async def coinflip(self, ctx: commands.Context) -> None:
        result = random.choice(["Heads", "Tails"])
        embed = discord.Embed(title="Coin Flip", description=f"**{result}**", color=EMBED_COLOR)
        await self._send(ctx, embed=embed)

    @commands.hybrid_command(name="roll", description="Roll a dice (default d6)")
    @app_commands.describe(sides="Number of sides on the dice (2-1000)")
    async def roll(self, ctx: commands.Context, sides: Optional[int] = 6) -> None:
        sides = sides or 6
        if sides < 2 or sides > 1000:
            await self._send(
                ctx,
                embed=discord.Embed(
                    title="Invalid dice",
                    description="Sides must be between **2** and **1000**.",
                    color=discord.Color.red(),
                ),
                ephemeral=True,
            )
            return
        value = random.randint(1, sides)
        embed = discord.Embed(title="🎲 Dice Roll", description=f"d{sides} → **{value}**", color=EMBED_COLOR)
        await self._send(ctx, embed=embed)

    @commands.hybrid_command(name="choose", description="Choose one option from a list")
    @app_commands.describe(options="Comma-separated options, e.g. pizza, burger, sushi")
    async def choose(self, ctx: commands.Context, *, options: str) -> None:
        parts = [p.strip() for p in options.split(",") if p.strip()]
        if len(parts) < 2:
            await self._send(
                ctx,
                embed=discord.Embed(
                    title="Not enough options",
                    description="Provide at least 2 comma-separated options.",
                    color=discord.Color.red(),
                ),
                ephemeral=True,
            )
            return
        pick = random.choice(parts)
        embed = discord.Embed(title="Choice", description=f"I choose: **{pick}**", color=EMBED_COLOR)
        await self._send(ctx, embed=embed)

    @commands.hybrid_command(name="rps", description="Play rock-paper-scissors")
    @app_commands.describe(choice="Your choice")
    async def rps(self, ctx: commands.Context, choice: str) -> None:
        choice_n = choice.strip().lower()
        valid = {"rock", "paper", "scissors"}
        if choice_n not in valid:
            await self._send(
                ctx,
                embed=discord.Embed(
                    title="Invalid choice",
                    description="Choose one of: rock, paper, scissors.",
                    color=discord.Color.red(),
                ),
                ephemeral=True,
            )
            return

        bot_choice = random.choice(sorted(valid))
        if choice_n == bot_choice:
            outcome = "It's a tie!"
        elif (
            (choice_n == "rock" and bot_choice == "scissors")
            or (choice_n == "paper" and bot_choice == "rock")
            or (choice_n == "scissors" and bot_choice == "paper")
        ):
            outcome = "You win!"
        else:
            outcome = "I win!"

        embed = discord.Embed(title="Rock Paper Scissors", color=EMBED_COLOR)
        embed.add_field(name="You", value=choice_n.title(), inline=True)
        embed.add_field(name="Miku", value=bot_choice.title(), inline=True)
        embed.add_field(name="Result", value=outcome, inline=False)
        await self._send(ctx, embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Fun(bot))
