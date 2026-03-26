"""
Leveling Cog - XP tracking and leveling system
Complete rewrite for Miku Bot
"""

import discord
from discord.ext import commands
from discord import app_commands
import time
import random
import logging
from typing import Optional
from io import BytesIO

from utils import database as db
from utils.rank_card import RankCardGenerator

logger = logging.getLogger('miku.leveling')

class Leveling(commands.Cog):
    """XP and leveling system for Discord servers"""
    
    EMBED_COLOR = discord.Color.from_rgb(88, 101, 242)  # Discord blurple
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.xp_cooldown = {}  # Track cooldowns per user per guild
        self.rank_card_generator = RankCardGenerator()
    
    async def cog_load(self):
        """Called when cog is loaded"""
        logger.info("Leveling cog loaded")
    
    async def cog_unload(self):
        """Called when cog is unloaded"""
        logger.info("Leveling cog unloaded")
        # Best-effort cleanup for rank card generator HTTP session
        try:
            close = getattr(self.rank_card_generator, "close", None)
            if close:
                result = close()
                if result is not None:
                    await result
        except Exception:
            logger.exception("Failed to close RankCardGenerator")

    async def _send(self, ctx: commands.Context, *args, **kwargs):
        """Send helper that works for both prefix and interaction invocations.

        For interactions, responses must be sent within ~3s unless deferred.
        If an interaction has expired (error 10062), we fall back to a normal
        channel message as a last resort.
        """
        interaction = getattr(ctx, "interaction", None)

        if interaction is None:
            kwargs.pop("ephemeral", None)

        try:
            return await ctx.send(*args, **kwargs)
        except discord.NotFound as e:
            # Slash interaction expired/invalid (common if not deferred quickly).
            # Fall back to a plain channel send (cannot be ephemeral).
            if interaction is not None and getattr(e, "code", None) == 10062 and getattr(ctx, "channel", None) is not None:
                kwargs.pop("ephemeral", None)
                return await ctx.channel.send(*args, **kwargs)  # type: ignore[union-attr]
            raise
        except discord.InteractionResponded:
            # If something already responded via interaction, use follow-up.
            if interaction is not None:
                return await interaction.followup.send(*args, **kwargs)
            raise

    async def _maybe_defer(self, ctx: commands.Context, *, ephemeral: bool = False):
        """Defer only when invoked as a slash command and not already acknowledged."""
        interaction = getattr(ctx, "interaction", None)
        if interaction is None:
            return

        # Avoid double-acknowledging the interaction.
        if interaction.response.is_done():
            return

        try:
            await ctx.defer(ephemeral=ephemeral)
        except discord.NotFound:
            # Interaction already expired; caller should rely on _send() fallback.
            return
        except discord.HTTPException:
            return
    
    # ========================================================================
    # Leveling Formula
    # ========================================================================
    
    def calculate_level(self, xp: int) -> int:
        """Calculate level from total XP using Arcane/MEE6-style formula"""
        # We model leveling as: every level requires some XP, and total XP is the
        # sum of all previous level requirements.
        # Formula per-level: xp_needed = 5*(level^2) + 50*level + 100
        level = 0
        xp_needed = 0
        while xp_needed <= xp:
            level += 1
            xp_needed += 5 * (level ** 2) + (50 * level) + 100
        return max(0, level - 1)
    
    def calculate_xp_for_level(self, level: int) -> int:
        """Calculate total XP needed to reach a level"""
        total_xp = 0
        for lvl in range(1, level + 1):
            total_xp += 5 * (lvl ** 2) + (50 * lvl) + 100
        return total_xp
    
    def calculate_xp_to_next_level(self, current_xp: int, current_level: int) -> tuple:
        """Calculate XP progress for next level
        Returns: (xp_needed, xp_progress, xp_required_for_level)
        """
        xp_for_current = self.calculate_xp_for_level(current_level)
        xp_for_next = self.calculate_xp_for_level(current_level + 1)
        xp_needed = xp_for_next - current_xp
        xp_progress = current_xp - xp_for_current
        xp_required_for_level = xp_for_next - xp_for_current
        return xp_needed, xp_progress, xp_required_for_level
    
    # ========================================================================
    # XP Tracking
    # ========================================================================
    
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Award XP for messages"""
        # Ignore bots and DMs
        if message.author.bot or not message.guild:
            return

        # High-level flow:
        # 1) Cooldown check (to avoid farming XP by spamming messages)
        # 2) Read current user row from DB (or treat as new user)
        # 3) Add random XP and recompute level
        # 4) Upsert DB row
        # 5) If level increased -> announce + role rewards
        
        user_id = message.author.id
        guild = message.guild
        guild_id = guild.id
        current_time = time.time()
        
        # Cooldown is kept in-memory (resets when the bot restarts).
        # Persistent anti-spam would be implemented at the DB layer.
        # Check cooldown (60 seconds default)
        cooldown_key = f"{user_id}_{guild_id}"
        if cooldown_key in self.xp_cooldown:
            if current_time - self.xp_cooldown[cooldown_key] < 60:
                return
        
        # Update cooldown
        self.xp_cooldown[cooldown_key] = current_time
        
        # DB returns a dict with keys: xp, level, messages, last_message_time, ...
        user_data = await db.get_user_data(user_id, guild_id)
        
        if user_data:
            current_xp = user_data['xp']
            current_level = user_data['level']
            messages = user_data['messages']
        else:
            current_xp = 0
            current_level = 0
            messages = 0
        
        # Award random XP (15-25 per message)
        xp_gain = random.randint(15, 25)
        new_xp = current_xp + xp_gain
        new_level = self.calculate_level(new_xp)
        messages += 1
        
        # Single write that INSERTs new users or UPDATEs existing ones.
        await db.update_user_xp(user_id, guild_id, new_xp, new_level, messages, current_time)
        
        # Check for level up
        if new_level > current_level:
            await self.handle_level_up(message, new_level)
    
    async def handle_level_up(self, message: discord.Message, new_level: int):
        """Handle level up event"""
        if message.guild is None:
            return

        user = message.author
        guild = message.guild
        
        # Create level up embed
        embed = discord.Embed(
            title=" Level Up!",
            description=f"Congratulations {user.mention}! You've reached **Level {new_level}**!",
            color=self.EMBED_COLOR
        )
        embed.set_thumbnail(url=user.display_avatar.url)
        
        # Get custom levelup channel or use current channel
        guild_settings = await db.get_guild_settings(guild.id)
        target_channel: discord.abc.Messageable = message.channel
        used_custom_channel = False
        
        if guild_settings and guild_settings.get('levelup_channel_id'):
            custom_channel = guild.get_channel(guild_settings['levelup_channel_id'])
            # Only accept channels that can actually send messages
            if custom_channel is not None and hasattr(custom_channel, "send"):
                target_channel = custom_channel  # type: ignore[assignment]
                used_custom_channel = True
        
        # Send level up message
        try:
            if used_custom_channel:
                # If a dedicated level-up channel is configured, keep the message.
                await target_channel.send(embed=embed)
            else:
                # If no dedicated channel is set, announce in the same channel
                # but auto-delete shortly to avoid clutter.
                await target_channel.send(embed=embed, delete_after=random.uniform(3, 5))
        except Exception:
            if target_channel != message.channel:
                try:
                    await message.channel.send(embed=embed, delete_after=random.uniform(3, 5))
                except Exception:
                    pass
        
        # Assign role rewards
        if isinstance(user, discord.Member):
            await self.assign_role_reward(guild, user, new_level)
    
    async def assign_role_reward(self, guild: discord.Guild, user: discord.Member, level: int):
        """Assign role reward for reaching a level"""
        role_id = await db.get_role_for_level(guild.id, level)
        
        if role_id:
            role = guild.get_role(role_id)
            if role and role < guild.me.top_role:
                try:
                    await user.add_roles(role, reason=f"Level {level} reward")
                    logger.info(f"Assigned role {role.name} to {user} for reaching level {level}")
                except Exception as e:
                    logger.error(f"Failed to assign role reward: {e}")
    
    # ========================================================================
    # User Commands
    # ========================================================================
    
    @commands.hybrid_command(
        name='rank',
        aliases=['level', 'lvl'],
        description='View your or another user\'s rank card'
    )
    @commands.guild_only()
    @app_commands.describe(user='The user to check (leave empty for yourself)')
    async def rank(self, ctx: commands.Context, user: Optional[discord.Member] = None):
        """Display rank card for a user"""
        if ctx.guild is None:
            return

        target = user or ctx.author
        
        if target.bot:
            await self._send(ctx, "Bots don't have ranks!", ephemeral=True)
            return

        await self._maybe_defer(ctx)
        
        # Get user data
        user_data = await db.get_user_data(target.id, ctx.guild.id)
        
        if not user_data:
            await self._send(ctx, f"{target.mention} hasn't earned any XP yet!")
            return
        
        xp = user_data['xp']
        level = user_data['level']
        messages = user_data['messages']
        rank = await db.get_user_rank(target.id, ctx.guild.id)
        
        if rank is None:
            rank = 0
        
        xp_needed, xp_progress, xp_required = self.calculate_xp_to_next_level(xp, level)
        
        # Generate rank card
        try:
            card_image = await self.rank_card_generator.generate_rank_card(
                avatar_url=target.display_avatar.url,
                username=target.display_name,
                rank=rank,
                level=level,
                current_xp=xp_progress,
                required_xp=xp_required,
                total_xp=xp,
                messages=messages,
                accent_color=(88, 101, 242)
            )

            # Support both implementations:
            # - return value is bytes (preferred)
            # - return value is PIL Image, requiring save_to_bytes
            if isinstance(card_image, (bytes, bytearray, memoryview)):
                file = discord.File(fp=BytesIO(bytes(card_image)), filename='rank_card.png')
            else:
                image_bytes = self.rank_card_generator.save_to_bytes(card_image)
                file = discord.File(fp=image_bytes, filename='rank_card.png')

            await self._send(ctx, file=file)
            
        except Exception as e:
            logger.error(f"Rank card generation failed: {e}")
            
            # Fallback to embed
            embed = discord.Embed(
                title=f" {target.display_name}'s Rank",
                color=self.EMBED_COLOR
            )
            embed.set_thumbnail(url=target.display_avatar.url)
            embed.add_field(name="Rank", value=f"#{rank}", inline=True)
            embed.add_field(name="Level", value=f"{level}", inline=True)
            embed.add_field(name="Messages", value=f"{messages:,}", inline=True)
            embed.add_field(
                name="XP Progress",
                value=f"{xp_progress:,} / {xp_required:,} ({xp_needed:,} to level {level + 1})",
                inline=False
            )
            embed.set_footer(text=f"Total XP: {xp:,}")
            await self._send(ctx, embed=embed)
    
    @commands.hybrid_command(
        name='leaderboard',
        aliases=['lb', 'top'],
        description='View the server leaderboard'
    )
    @commands.guild_only()
    @app_commands.describe(page='Page number to view')
    async def leaderboard(self, ctx: commands.Context, page: int = 1):
        """Display server leaderboard"""
        if ctx.guild is None:
            return

        await self._maybe_defer(ctx)

        if page < 1:
            page = 1
        
        per_page = 10
        offset = (page - 1) * per_page
        
        # Get leaderboard data
        lb_data = await db.get_leaderboard(ctx.guild.id, limit=per_page, offset=offset)
        
        if not lb_data:
            await self._send(ctx, "No one has earned any XP yet! Start chatting to level up!", ephemeral=True)
            return
        
        # Get total users for page count
        total_users = await db.get_total_users(ctx.guild.id)
        total_pages = max(1, (total_users + per_page - 1) // per_page)
        page = min(page, total_pages)
        
        # Build leaderboard embed
        embed = discord.Embed(
            title=f" {ctx.guild.name} Leaderboard",
            color=self.EMBED_COLOR
        )
        
        leaderboard_text = ""
        for idx, entry in enumerate(lb_data, start=offset + 1):
            user = ctx.guild.get_member(entry['user_id'])
            if user:
                medals = ["🥇", "🥈", "🥉"]
                medal = medals[idx - 1] if idx <= 3 else f"`#{idx}`"
                leaderboard_text += f"{medal} **{user.display_name}**\n"
                leaderboard_text += f"     Level {entry['level']} • {entry['xp']:,} XP • {entry['messages']:,} messages\n\n"
        
        if not leaderboard_text:
            leaderboard_text = "No user data available"
        
        embed.description = leaderboard_text
        embed.set_footer(text=f"Page {page}/{total_pages} • {total_users} total users")
        
        await self._send(ctx, embed=embed)
    
    @commands.hybrid_command(
        name='xp',
        description='View detailed XP information'
    )
    @commands.guild_only()
    @app_commands.describe(user='The user to check')
    async def xp(self, ctx: commands.Context, user: Optional[discord.Member] = None):
        """Display detailed XP information"""
        if ctx.guild is None:
            return

        target = user or ctx.author
        
        if target.bot:
            await self._send(ctx, "Bots don't have XP!", ephemeral=True)
            return

        await self._maybe_defer(ctx)
        
        user_data = await db.get_user_data(target.id, ctx.guild.id)
        
        if not user_data:
            await self._send(ctx, f"{target.mention} hasn't earned any XP yet!", ephemeral=True)
            return
        
        xp = user_data['xp']
        level = user_data['level']
        messages = user_data['messages']
        rank = await db.get_user_rank(target.id, ctx.guild.id)
        
        xp_needed, xp_progress, xp_required = self.calculate_xp_to_next_level(xp, level)
        avg_xp = xp / messages if messages > 0 else 0
        
        embed = discord.Embed(
            title=f" {target.display_name}'s XP Details",
            color=self.EMBED_COLOR
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="Server Rank", value=f"#{rank}", inline=True)
        embed.add_field(name="Level", value=f"{level}", inline=True)
        embed.add_field(name="Total XP", value=f"{xp:,}", inline=True)
        embed.add_field(name="Messages", value=f"{messages:,}", inline=True)
        embed.add_field(name="Avg XP/Message", value=f"{avg_xp:.1f}", inline=True)
        embed.add_field(name="XP to Level Up", value=f"{xp_needed:,}", inline=True)
        embed.add_field(
            name="Progress to Next Level",
            value=f"{xp_progress:,} / {xp_required:,} ({(xp_progress/xp_required*100):.1f}%)",
            inline=False
        )
        
        await self._send(ctx, embed=embed)
    
    # ========================================================================
    # Admin Commands - Level Management
    # ========================================================================
    
    @commands.hybrid_command(
        name='setlevel',
        description='Set a user\'s level (Admin only)'
    )
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    @app_commands.describe(user='The user', level='The level to set')
    async def setlevel(self, ctx: commands.Context, user: discord.Member, level: int):
        """Set a user's level"""
        if ctx.guild is None:
            return

        await self._maybe_defer(ctx)

        if level < 0:
            await self._send(ctx, " Level must be 0 or higher!", ephemeral=True)
            return
        
        xp = self.calculate_xp_for_level(level)
        
        # Preserve message count
        user_data = await db.get_user_data(user.id, ctx.guild.id)
        messages = user_data['messages'] if user_data else 0
        
        await db.update_user_xp(user.id, ctx.guild.id, xp, level, messages, time.time())
        
        embed = discord.Embed(
            title=" Level Set",
            description=f"Set {user.mention} to **Level {level}** ({xp:,} XP)",
            color=self.EMBED_COLOR
        )
        await self._send(ctx, embed=embed)
    
    @commands.hybrid_command(
        name='addxp',
        description='Add XP to a user (Admin only)'
    )
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    @app_commands.describe(user='The user', amount='Amount of XP to add')
    async def addxp(self, ctx: commands.Context, user: discord.Member, amount: int):
        """Add XP to a user"""
        if ctx.guild is None:
            return

        await self._maybe_defer(ctx)

        user_data = await db.get_user_data(user.id, ctx.guild.id)
        
        if user_data:
            new_xp = user_data['xp'] + amount
            messages = user_data['messages']
        else:
            new_xp = max(0, amount)
            messages = 0
        
        new_level = self.calculate_level(new_xp)
        await db.update_user_xp(user.id, ctx.guild.id, new_xp, new_level, messages, time.time())
        
        embed = discord.Embed(
            title=" XP Added",
            description=f"Added {amount:,} XP to {user.mention}\nNew Level: **{new_level}** | Total XP: {new_xp:,}",
            color=self.EMBED_COLOR
        )
        await self._send(ctx, embed=embed)
    
    @commands.hybrid_command(
        name='resetlevel',
        description='Reset a user\'s level data (Admin only)'
    )
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    @app_commands.describe(user='The user to reset')
    async def resetlevel(self, ctx: commands.Context, user: discord.Member):
        """Reset a user's level data"""
        if ctx.guild is None:
            return

        await self._maybe_defer(ctx)

        await db.reset_user_data(user.id, ctx.guild.id)
        
        embed = discord.Embed(
            title=" Level Reset",
            description=f"Reset all level data for {user.mention}",
            color=self.EMBED_COLOR
        )
        await self._send(ctx, embed=embed)
    
    @commands.hybrid_command(
        name='resetalllevels',
        description='Reset all server level data (Admin only)'
    )
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    @app_commands.describe(confirm='Type CONFIRM to proceed')
    async def resetalllevels(self, ctx: commands.Context, confirm: Optional[str] = None):
        """Reset all level data in the server"""
        if ctx.guild is None:
            return

        await self._maybe_defer(ctx)

        if confirm != "CONFIRM":
            embed = discord.Embed(
                title=" Warning",
                description="This will **delete all level data** for this server!\n\n"
                           f"To proceed, use: `{ctx.prefix}resetalllevels CONFIRM`",
                color=discord.Color.red()
            )
            await self._send(ctx, embed=embed)
            return
        
        await db.reset_guild_data(ctx.guild.id)
        
        embed = discord.Embed(
            title=" All Levels Reset",
            description="All level data has been reset for this server",
            color=self.EMBED_COLOR
        )
        await self._send(ctx, embed=embed)
    
    # ========================================================================
    # Admin Commands - Configuration
    # ========================================================================
    
    @commands.hybrid_command(
        name='setlevelchannel',
        description='Set the level-up announcement channel (Admin only)'
    )
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    @app_commands.describe(channel='The channel for level-up announcements')
    async def setlevelchannel(self, ctx: commands.Context, channel: Optional[discord.TextChannel] = None):
        """Set or remove the level-up announcement channel"""
        if ctx.guild is None:
            return

        await self._maybe_defer(ctx)

        if channel:
            await db.set_levelup_channel(ctx.guild.id, channel.id)
            embed = discord.Embed(
                title=" Level-Up Channel Set",
                description=f"Level-up announcements will be sent to {channel.mention}",
                color=self.EMBED_COLOR
            )
        else:
            await db.set_levelup_channel(ctx.guild.id, None)
            embed = discord.Embed(
                title=" Level-Up Channel Removed",
                description="Level-up announcements will be sent in the same channel as messages",
                color=self.EMBED_COLOR
            )
        
        await self._send(ctx, embed=embed)
    
    @commands.hybrid_command(
        name='addrole',
        description='Add a role reward for a level (Admin only)'
    )
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    @app_commands.describe(level='The level', role='The role to award')
    async def addrole(self, ctx: commands.Context, level: int, role: discord.Role):
        """Add a role reward for reaching a level"""
        if ctx.guild is None:
            return

        await self._maybe_defer(ctx)

        if level < 1:
            await self._send(ctx, " Level must be 1 or higher!", ephemeral=True)
            return
        
        # Check if bot can manage this role
        me = ctx.guild.me
        if me is None or role >= me.top_role:
            await self._send(ctx, " I cannot assign this role! It's higher than or equal to my highest role.", ephemeral=True)
            return
        
        if role.managed:
            await self._send(ctx, " This role is managed by an integration and cannot be assigned!", ephemeral=True)
            return
        
        await db.add_role_reward(ctx.guild.id, level, role.id)
        
        embed = discord.Embed(
            title=" Role Reward Added",
            description=f"Users will receive {role.mention} when they reach **Level {level}**",
            color=self.EMBED_COLOR
        )
        await self._send(ctx, embed=embed)
    
    @commands.hybrid_command(
        name='removerole',
        description='Remove a role reward (Admin only)'
    )
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    @app_commands.describe(level='The level to remove the role reward from')
    async def removerole(self, ctx: commands.Context, level: int):
        """Remove a role reward for a level"""
        if ctx.guild is None:
            return

        await self._maybe_defer(ctx)

        result = await db.remove_role_reward(ctx.guild.id, level)
        
        if result:
            embed = discord.Embed(
                title=" Role Reward Removed",
                description=f"Removed role reward for **Level {level}**",
                color=self.EMBED_COLOR
            )
        else:
            embed = discord.Embed(
                title=" Not Found",
                description=f"No role reward found for Level {level}",
                color=discord.Color.red()
            )
        
        await self._send(ctx, embed=embed)
    
    @commands.hybrid_command(
        name='rolerewards',
        aliases=['listroles'],
        description='View all role rewards'
    )
    @commands.guild_only()
    async def rolerewards(self, ctx: commands.Context):
        """List all configured role rewards"""
        if ctx.guild is None:
            return

        await self._maybe_defer(ctx)

        role_rewards = await db.get_role_rewards(ctx.guild.id)
        
        if not role_rewards:
            await self._send(ctx, "No role rewards have been configured yet!", ephemeral=True)
            return
        
        embed = discord.Embed(
            title=" Role Rewards",
            description="Roles awarded for reaching specific levels",
            color=self.EMBED_COLOR
        )
        
        rewards_text = ""
        for reward in role_rewards:
            role = ctx.guild.get_role(reward['role_id'])
            if role:
                rewards_text += f"**Level {reward['level']}** → {role.mention}\n"
            else:
                rewards_text += f"**Level {reward['level']}** → *Deleted Role*\n"
        
        embed.description = rewards_text
        await self._send(ctx, embed=embed)

async def setup(bot: commands.Bot):
    """Setup function to add cog to bot"""
    await bot.add_cog(Leveling(bot))
