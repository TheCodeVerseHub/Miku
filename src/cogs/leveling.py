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
    
    # ========================================================================
    # Leveling Formula
    # ========================================================================
    
    def calculate_level(self, xp: int) -> int:
        """Calculate level from total XP using Arcane/MEE6-style formula"""
        # Formula: xp_needed = 5 * (level^2) + (50 * level) + 100
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
        
        user_id = message.author.id
        guild_id = message.guild.id
        current_time = time.time()
        
        # Check cooldown (60 seconds default)
        cooldown_key = f"{user_id}_{guild_id}"
        if cooldown_key in self.xp_cooldown:
            if current_time - self.xp_cooldown[cooldown_key] < 60:
                return
        
        # Update cooldown
        self.xp_cooldown[cooldown_key] = current_time
        
        # Get user data
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
        
        # Save to database
        await db.update_user_xp(user_id, guild_id, new_xp, new_level, messages, current_time)
        
        # Check for level up
        if new_level > current_level:
            await self.handle_level_up(message, new_level)
    
    async def handle_level_up(self, message: discord.Message, new_level: int):
        """Handle level up event"""
        user = message.author
        guild = message.guild
        
        # Create level up embed
        embed = discord.Embed(
            title="🎉 Level Up!",
            description=f"Congratulations {user.mention}! You've reached **Level {new_level}**!",
            color=self.EMBED_COLOR
        )
        embed.set_thumbnail(url=user.display_avatar.url)
        
        # Get custom levelup channel or use current channel
        guild_settings = await db.get_guild_settings(guild.id)
        target_channel = message.channel
        
        if guild_settings and guild_settings.get('levelup_channel_id'):
            custom_channel = guild.get_channel(guild_settings['levelup_channel_id'])
            if custom_channel:
                target_channel = custom_channel
        
        # Send level up message
        try:
            await target_channel.send(embed=embed, delete_after=30)
        except:
            if target_channel != message.channel:
                try:
                    await message.channel.send(embed=embed, delete_after=30)
                except:
                    pass
        
        # Assign role rewards
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
        target = user or ctx.author
        
        if target.bot:
            await ctx.send("Bots don't have ranks!", ephemeral=True)
            return
        
        await ctx.defer()
        
        # Get user data
        user_data = await db.get_user_data(target.id, ctx.guild.id)
        
        if not user_data:
            await ctx.send(f"{target.mention} hasn't earned any XP yet!")
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
            
            image_bytes = self.rank_card_generator.save_to_bytes(card_image)
            file = discord.File(fp=image_bytes, filename='rank_card.png')
            await ctx.send(file=file)
            
        except Exception as e:
            logger.error(f"Rank card generation failed: {e}")
            
            # Fallback to embed
            embed = discord.Embed(
                title=f"📊 {target.display_name}'s Rank",
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
            await ctx.send(embed=embed)
    
    @commands.hybrid_command(
        name='leaderboard',
        aliases=['lb', 'top'],
        description='View the server leaderboard'
    )
    @commands.guild_only()
    @app_commands.describe(page='Page number to view')
    async def leaderboard(self, ctx: commands.Context, page: int = 1):
        """Display server leaderboard"""
        if page < 1:
            page = 1
        
        per_page = 10
        offset = (page - 1) * per_page
        
        # Get leaderboard data
        lb_data = await db.get_leaderboard(ctx.guild.id, limit=per_page, offset=offset)
        
        if not lb_data:
            await ctx.send("No one has earned any XP yet! Start chatting to level up!", ephemeral=True)
            return
        
        # Get total users for page count
        total_users = await db.get_total_users(ctx.guild.id)
        total_pages = max(1, (total_users + per_page - 1) // per_page)
        page = min(page, total_pages)
        
        # Build leaderboard embed
        embed = discord.Embed(
            title=f"🏆 {ctx.guild.name} Leaderboard",
            color=self.EMBED_COLOR
        )
        
        leaderboard_text = ""
        for idx, entry in enumerate(lb_data, start=offset + 1):
            user = ctx.guild.get_member(entry['user_id'])
            if user:
                medal = ["🥇", "🥈", "🥉"][idx - 1] if idx <= 3 else f"`#{idx}`"
                leaderboard_text += f"{medal} **{user.display_name}**\n"
                leaderboard_text += f"     Level {entry['level']} • {entry['xp']:,} XP • {entry['messages']:,} messages\n\n"
        
        if not leaderboard_text:
            leaderboard_text = "No user data available"
        
        embed.description = leaderboard_text
        embed.set_footer(text=f"Page {page}/{total_pages} • {total_users} total users")
        
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(
        name='xp',
        description='View detailed XP information'
    )
    @commands.guild_only()
    @app_commands.describe(user='The user to check')
    async def xp(self, ctx: commands.Context, user: Optional[discord.Member] = None):
        """Display detailed XP information"""
        target = user or ctx.author
        
        if target.bot:
            await ctx.send("Bots don't have XP!", ephemeral=True)
            return
        
        user_data = await db.get_user_data(target.id, ctx.guild.id)
        
        if not user_data:
            await ctx.send(f"{target.mention} hasn't earned any XP yet!", ephemeral=True)
            return
        
        xp = user_data['xp']
        level = user_data['level']
        messages = user_data['messages']
        rank = await db.get_user_rank(target.id, ctx.guild.id)
        
        xp_needed, xp_progress, xp_required = self.calculate_xp_to_next_level(xp, level)
        avg_xp = xp / messages if messages > 0 else 0
        
        embed = discord.Embed(
            title=f"📈 {target.display_name}'s XP Details",
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
        
        await ctx.send(embed=embed)
    
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
        if level < 0:
            await ctx.send("❌ Level must be 0 or higher!", ephemeral=True)
            return
        
        xp = self.calculate_xp_for_level(level)
        
        # Preserve message count
        user_data = await db.get_user_data(user.id, ctx.guild.id)
        messages = user_data['messages'] if user_data else 0
        
        await db.update_user_xp(user.id, ctx.guild.id, xp, level, messages, time.time())
        
        embed = discord.Embed(
            title="✅ Level Set",
            description=f"Set {user.mention} to **Level {level}** ({xp:,} XP)",
            color=self.EMBED_COLOR
        )
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(
        name='addxp',
        description='Add XP to a user (Admin only)'
    )
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    @app_commands.describe(user='The user', amount='Amount of XP to add')
    async def addxp(self, ctx: commands.Context, user: discord.Member, amount: int):
        """Add XP to a user"""
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
            title="✅ XP Added",
            description=f"Added {amount:,} XP to {user.mention}\nNew Level: **{new_level}** | Total XP: {new_xp:,}",
            color=self.EMBED_COLOR
        )
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(
        name='resetlevel',
        description='Reset a user\'s level data (Admin only)'
    )
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    @app_commands.describe(user='The user to reset')
    async def resetlevel(self, ctx: commands.Context, user: discord.Member):
        """Reset a user's level data"""
        await db.reset_user_data(user.id, ctx.guild.id)
        
        embed = discord.Embed(
            title="✅ Level Reset",
            description=f"Reset all level data for {user.mention}",
            color=self.EMBED_COLOR
        )
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(
        name='resetalllevels',
        description='Reset all server level data (Admin only)'
    )
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    @app_commands.describe(confirm='Type CONFIRM to proceed')
    async def resetalllevels(self, ctx: commands.Context, confirm: Optional[str] = None):
        """Reset all level data in the server"""
        if confirm != "CONFIRM":
            embed = discord.Embed(
                title="⚠️ Warning",
                description="This will **delete all level data** for this server!\n\n"
                           f"To proceed, use: `{ctx.prefix}resetalllevels CONFIRM`",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
        
        await db.reset_guild_data(ctx.guild.id)
        
        embed = discord.Embed(
            title="✅ All Levels Reset",
            description="All level data has been reset for this server",
            color=self.EMBED_COLOR
        )
        await ctx.send(embed=embed)
    
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
        if channel:
            await db.set_levelup_channel(ctx.guild.id, channel.id)
            embed = discord.Embed(
                title="✅ Level-Up Channel Set",
                description=f"Level-up announcements will be sent to {channel.mention}",
                color=self.EMBED_COLOR
            )
        else:
            await db.set_levelup_channel(ctx.guild.id, None)
            embed = discord.Embed(
                title="✅ Level-Up Channel Removed",
                description="Level-up announcements will be sent in the same channel as messages",
                color=self.EMBED_COLOR
            )
        
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(
        name='addrole',
        description='Add a role reward for a level (Admin only)'
    )
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    @app_commands.describe(level='The level', role='The role to award')
    async def addrole(self, ctx: commands.Context, level: int, role: discord.Role):
        """Add a role reward for reaching a level"""
        if level < 1:
            await ctx.send("❌ Level must be 1 or higher!", ephemeral=True)
            return
        
        # Check if bot can manage this role
        if role >= ctx.guild.me.top_role:
            await ctx.send("❌ I cannot assign this role! It's higher than or equal to my highest role.", ephemeral=True)
            return
        
        if role.managed:
            await ctx.send("❌ This role is managed by an integration and cannot be assigned!", ephemeral=True)
            return
        
        await db.add_role_reward(ctx.guild.id, level, role.id)
        
        embed = discord.Embed(
            title="✅ Role Reward Added",
            description=f"Users will receive {role.mention} when they reach **Level {level}**",
            color=self.EMBED_COLOR
        )
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(
        name='removerole',
        description='Remove a role reward (Admin only)'
    )
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    @app_commands.describe(level='The level to remove the role reward from')
    async def removerole(self, ctx: commands.Context, level: int):
        """Remove a role reward for a level"""
        result = await db.remove_role_reward(ctx.guild.id, level)
        
        if result:
            embed = discord.Embed(
                title="✅ Role Reward Removed",
                description=f"Removed role reward for **Level {level}**",
                color=self.EMBED_COLOR
            )
        else:
            embed = discord.Embed(
                title="❌ Not Found",
                description=f"No role reward found for Level {level}",
                color=discord.Color.red()
            )
        
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(
        name='rolerewards',
        aliases=['listroles'],
        description='View all role rewards'
    )
    @commands.guild_only()
    async def rolerewards(self, ctx: commands.Context):
        """List all configured role rewards"""
        role_rewards = await db.get_role_rewards(ctx.guild.id)
        
        if not role_rewards:
            await ctx.send("No role rewards have been configured yet!", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="🎁 Role Rewards",
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
        await ctx.send(embed=embed)

async def setup(bot: commands.Bot):
    """Setup function to add cog to bot"""
    await bot.add_cog(Leveling(bot))

        
        # Save to database
        await db.update_user_xp(user_id, guild_id, new_xp, new_level, messages, current_time)
        
        # Check if user leveled up
        if new_level > current_level:
            await self.send_level_up_message(message, message.author, new_level)
            # Check for role rewards
            await self.assign_role_rewards(message.guild, message.author, new_level)
    
    async def send_level_up_message(self, message, user, level):
        """Send level up notification to configured channel or current channel"""
        embed = discord.Embed(
            title="🎉 Level Up!",
            description=f"Congratulations {user.mention}! You've reached **Level {level}**! 🌟",
            color=self.EMBED_COLOR
        )
        embed.set_thumbnail(url=user.display_avatar.url)
        
        # Get guild settings to check for custom level-up channel
        guild_settings = await db.get_guild_settings(message.guild.id)
        
        target_channel = message.channel  # Default to current channel
        
        if guild_settings and guild_settings.get('levelup_channel_id'):
            custom_channel = message.guild.get_channel(guild_settings['levelup_channel_id'])
            if custom_channel:
                target_channel = custom_channel
        
        try:
            await target_channel.send(embed=embed, delete_after=15)
        except:
            # If custom channel fails, try current channel
            if target_channel != message.channel:
                try:
                    await message.channel.send(embed=embed, delete_after=15)
                except:
                    pass
    
    async def assign_role_rewards(self, guild, user, level):
        """Assign role rewards when user reaches a level"""
        role_id = await db.get_role_for_level(guild.id, level)
        
        if role_id:
            role = guild.get_role(role_id)
            if role:
                try:
                    await user.add_roles(role, reason=f"Level {level} reward")
                except Exception:
                    pass
    
    # Rank/Level Command (Hybrid)
    @commands.hybrid_command(name='rank', aliases=['level', 'lvl'], description='Check your or another user\'s rank and level')
    @commands.guild_only()
    @app_commands.describe(user='The user to check (leave empty for yourself)')
    async def rank(self, ctx: commands.Context, user: Optional[discord.Member] = None):
        """Check rank and level of a user"""
        if not ctx.guild:
            return
        
        target = user or ctx.author
        
        if target.bot:
            await ctx.send("Bots don't have levels!", ephemeral=True)
            return
        
        # Defer response since image generation takes time
        await ctx.defer()
        
        user_data = await db.get_user_data(target.id, ctx.guild.id)
        
        if user_data is None:
            await ctx.send(f"{target.mention} hasn't earned any XP yet!")
            return
        
        xp = user_data['xp']
        level = user_data['level']
        messages = user_data['messages']
        rank = await db.get_user_rank(target.id, ctx.guild.id)
        
        # Ensure rank is an integer (default to 0 if None)
        if rank is None:
            rank = 0
        
        xp_needed, xp_progress, xp_required = self.calculate_xp_to_next_level(xp, level)
        
        # Generate rank card image
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
                accent_color=(88, 101, 242)  # Discord blurple
            )
            
            # Convert to bytes
            image_bytes = self.rank_card_generator.save_to_bytes(card_image)
            
            # Send the image
            file = discord.File(fp=image_bytes, filename='rank_card.png')
            await ctx.send(file=file)
            
        except Exception:
            # Fallback to embed if image generation fails
            embed = discord.Embed(
                title=f"{target.display_name}'s Rank Card",
                color=self.EMBED_COLOR
            )
            embed.set_thumbnail(url=target.display_avatar.url)
            embed.add_field(name="Rank", value=f"#{rank}", inline=True)
            embed.add_field(name="Level", value=f"{level}", inline=True)
            embed.add_field(name="Messages", value=f"{messages:,}", inline=True)
            embed.add_field(
                name="Progress", 
                value=f"{xp_progress:,}/{xp_required:,} XP\n{xp_needed:,} XP to level {level + 1}",
                inline=False
            )
            embed.set_footer(text=f"Total XP: {xp:,}")
            await ctx.send(embed=embed)
    
    def create_progress_bar(self, current: int, total: int, length: int = 10) -> str:
        """Create a visual progress bar"""
        if total == 0:
            percent = 0
        else:
            percent = current / total
        filled = int(length * percent)
        bar = "█" * filled + "░" * (length - filled)
        return f"[{bar}] {percent * 100:.1f}%"
    
    # Leaderboard Command (Hybrid)
    @commands.hybrid_command(name='leaderboard', aliases=['lb', 'top'], description='View the server leaderboard')
    @commands.guild_only()
    @app_commands.describe(page='Page number to view')
    async def leaderboard(self, ctx: commands.Context, page: int = 1):
        """Display server leaderboard"""
        if not ctx.guild:
            return
        
        if page < 1:
            page = 1
        
        per_page = 10
        offset = (page - 1) * per_page
        
        lb_data = await db.get_leaderboard(ctx.guild.id, limit=50)  # Get top 50
        
        if not lb_data:
            await ctx.send("No one has earned XP yet! Start chatting to earn XP!", ephemeral=True)
            return
        
        # Paginate
        total_pages = math.ceil(len(lb_data) / per_page)
        page = min(page, total_pages)
        offset = (page - 1) * per_page
        
        page_data = lb_data[offset:offset + per_page]
        
        embed = discord.Embed(
            title=f"{ctx.guild.name} Leaderboard",
            description="Top members by XP",
            color=self.EMBED_COLOR
        )
        
        leaderboard_text = ""
        for idx, entry in enumerate(page_data, start=offset + 1):
            user = ctx.guild.get_member(entry['user_id'])
            if user:
                leaderboard_text += f"`#{idx}` **{user.display_name}**\n"
                leaderboard_text += f"     Level: {entry['level']} • XP: {entry['xp']:,} • Messages: {entry['messages']:,}\n\n"
        
        embed.description = leaderboard_text
        embed.set_footer(text=f"Page {page}/{total_pages}")
        
        await ctx.send(embed=embed)
    
    # XP Command (Hybrid) - Check XP details
    @commands.hybrid_command(name='xp', description='Check detailed XP information')
    @commands.guild_only()
    @app_commands.describe(user='The user to check')
    async def xp(self, ctx: commands.Context, user: Optional[discord.Member] = None):
        """Check detailed XP information"""
        if not ctx.guild:
            return
        
        target = user or ctx.author
        
        if target.bot:
            await ctx.send("Bots don't have XP!", ephemeral=True)
            return
        
        user_data = await db.get_user_data(target.id, ctx.guild.id)
        
        if user_data is None:
            await ctx.send(f"{target.mention} hasn't earned any XP yet!", ephemeral=True)
            return
        
        xp = user_data['xp']
        level = user_data['level']
        messages = user_data['messages']
        
        xp_needed, xp_progress, xp_required = self.calculate_xp_to_next_level(xp, level)
        
        embed = discord.Embed(
            title=f"{target.display_name}'s XP Details",
            color=self.EMBED_COLOR
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="Total XP", value=f"{xp:,}", inline=True)
        embed.add_field(name="Current Level", value=f"{level}", inline=True)
        embed.add_field(name="Messages Sent", value=f"{messages:,}", inline=True)
        embed.add_field(name="XP to Next Level", value=f"{xp_needed:,}", inline=True)
        embed.add_field(name="Progress", value=f"{xp_progress:,}/{xp_required:,}", inline=True)
        embed.add_field(name="Avg XP/Message", value=f"{xp/messages:.1f}" if messages > 0 else "0", inline=True)
        
        await ctx.send(embed=embed)
    
    # Admin Commands
    @commands.hybrid_command(name='resetlevel', description='Reset a user\'s level (Admin only)')
    @commands.guild_only()
    @app_commands.describe(user='The user to reset')
    @commands.has_permissions(administrator=True)
    async def resetlevel(self, ctx: commands.Context, user: discord.Member):
        """Reset a user's level data (Admin only)"""
        if not ctx.guild:
            return
        
        await db.reset_user_data(user.id, ctx.guild.id)
        await ctx.send(f"Reset level data for {user.mention}")
    
    @commands.hybrid_command(name='resetalllevels', description='Reset all server levels (Admin only)')
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def resetalllevels(self, ctx: commands.Context, confirm: Optional[str] = None):
        """Reset all level data in the server (Admin only)"""
        if not ctx.guild:
            return
        
        if confirm != "CONFIRM":
            await ctx.send("This will reset ALL level data in the server!\nUse `&resetalllevels CONFIRM` to proceed.")
            return
        
        await db.reset_guild_data(ctx.guild.id)
        await ctx.send("All level data has been reset for this server")
    
    @commands.hybrid_command(name='setlevel', description='Set a user\'s level (Admin only)')
    @commands.guild_only()
    @app_commands.describe(user='The user', level='Level to set')
    @commands.has_permissions(administrator=True)
    async def setlevel(self, ctx: commands.Context, user: discord.Member, level: int):
        """Set a user's level (Admin only)"""
        if not ctx.guild:
            return
        
        if level < 0:
            await ctx.send("Level must be 0 or higher!")
            return
        
        xp = self.calculate_xp_for_level(level)
        current_data = await db.get_user_data(user.id, ctx.guild.id)
        messages = current_data['messages'] if current_data else 0
        
        await db.update_user_xp(user.id, ctx.guild.id, xp, level, messages, time.time())
        await ctx.send(f"Set {user.mention}'s level to {level} ({xp:,} XP)")
    
    @commands.hybrid_command(name='addxp', description='Add XP to a user (Admin only)')
    @commands.guild_only()
    @app_commands.describe(user='The user', amount='Amount of XP to add')
    @commands.has_permissions(administrator=True)
    async def addxp(self, ctx: commands.Context, user: discord.Member, amount: int):
        """Add XP to a user (Admin only)"""
        if not ctx.guild:
            return
        
        current_data = await db.get_user_data(user.id, ctx.guild.id)
        
        if current_data:
            new_xp = current_data['xp'] + amount
            messages = current_data['messages']
        else:
            new_xp = amount
            messages = 0
        
        new_level = self.calculate_level(new_xp)
        await db.update_user_xp(user.id, ctx.guild.id, new_xp, new_level, messages, time.time())
        
        await ctx.send(f"Added {amount:,} XP to {user.mention} (Level {new_level}, Total XP: {new_xp:,})")
    
    # Configuration Commands
    @commands.hybrid_command(name='setlevelchannel', description='Set the level-up announcement channel (Admin only)')
    @commands.guild_only()
    @app_commands.describe(channel='The channel for level-up messages')
    @commands.has_permissions(administrator=True)
    async def setlevelchannel(self, ctx: commands.Context, channel: discord.TextChannel):
        """Set the level-up announcement channel (Admin only)"""
        if not ctx.guild:
            return
        
        await db.set_levelup_channel(ctx.guild.id, channel.id)
        
        embed = discord.Embed(
            title="✅ Level-Up Channel Set",
            description=f"Level-up announcements will now be sent to {channel.mention}",
            color=self.EMBED_COLOR
        )
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(name='addrole', description='Add a role reward for a level (Admin only)')
    @commands.guild_only()
    @app_commands.describe(level='The level to award the role', role='The role to award')
    @commands.has_permissions(administrator=True)
    async def addrole(self, ctx: commands.Context, level: int, role: discord.Role):
        """Add a role reward for a level (Admin only)"""
        if not ctx.guild:
            return
        
        if level < 1:
            await ctx.send("Level must be 1 or higher!", ephemeral=True)
            return
        
        # Check if bot can manage this role
        if role >= ctx.guild.me.top_role:
            await ctx.send("❌ I cannot assign this role as it's higher than or equal to my highest role!", ephemeral=True)
            return
        
        await db.add_role_reward(ctx.guild.id, level, role.id)
        
        embed = discord.Embed(
            title="✅ Role Reward Added",
            description=f"Users will now receive {role.mention} when they reach **Level {level}**",
            color=self.EMBED_COLOR
        )
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(name='removerole', description='Remove a role reward for a level (Admin only)')
    @commands.guild_only()
    @app_commands.describe(level='The level to remove the role reward from')
    @commands.has_permissions(administrator=True)
    async def removerole(self, ctx: commands.Context, level: int):
        """Remove a role reward for a level (Admin only)"""
        if not ctx.guild:
            return
        
        await db.remove_role_reward(ctx.guild.id, level)
        
        embed = discord.Embed(
            title="✅ Role Reward Removed",
            description=f"Role reward for **Level {level}** has been removed",
            color=self.EMBED_COLOR
        )
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(name='rolerewards', aliases=['listroles'], description='List all role rewards')
    @commands.guild_only()
    async def rolerewards(self, ctx: commands.Context):
        """List all configured role rewards"""
        if not ctx.guild:
            return
        
        role_rewards = await db.get_role_rewards(ctx.guild.id)
        
        if not role_rewards:
            await ctx.send("No role rewards have been configured yet!", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="🎁 Role Rewards",
            description="Roles awarded for reaching specific levels",
            color=self.EMBED_COLOR
        )
        
        for reward in role_rewards:
            role = ctx.guild.get_role(reward['role_id'])
            if role:
                embed.add_field(
                    name=f"Level {reward['level']}",
                    value=role.mention,
                    inline=True
                )
        
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Leveling(bot))
