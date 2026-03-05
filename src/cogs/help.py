import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional

class HelpView(discord.ui.View):
    """Interactive help menu with dropdown"""
    
    def __init__(self, bot, user_id: int):
        super().__init__(timeout=180)
        self.bot = bot
        self.user_id = user_id
        self.add_item(CategorySelect(bot))
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Only allow the command user to interact"""
        return interaction.user.id == self.user_id

class CategorySelect(discord.ui.Select):
    """Dropdown menu for selecting command categories"""
    
    def __init__(self, bot):
        self.bot = bot
        
        # Define categories with descriptions
        options = [
            discord.SelectOption(
                label="Home",
                description="Return to main help menu",
                value="home"
            ),
            discord.SelectOption(
                label="Leveling",
                description="XP and rank commands",
                value="leveling"
            ),
            discord.SelectOption(
                label="Admin",
                description="Server administration commands",
                value="admin"
            ),
        ]
        
        super().__init__(
            placeholder="Select a category to view commands...",
            options=options,
            min_values=1,
            max_values=1
        )
    
    async def callback(self, interaction: discord.Interaction):
        """Handle category selection"""
        category = self.values[0]
        
        if category == "home":
            embed = create_main_help_embed(self.bot)
        elif category == "leveling":
            embed = create_leveling_help_embed()
        elif category == "admin":
            embed = create_admin_help_embed()
        else:
            embed = create_main_help_embed(self.bot)
        
        await interaction.response.edit_message(embed=embed)

def create_main_help_embed(bot) -> discord.Embed:
    """Create the main help embed"""
    embed = discord.Embed(
        title="Miku - Help",
        description="Feature-rich Discord leveling bot with XP tracking and rank systems",
        color=discord.Color.from_rgb(88, 101, 242)
    )
    
    embed.add_field(
        name="Commands",
        value="**Prefix:** `&` (e.g. `&help`)\n**Slash:** `/command` (e.g. `/help`)",
        inline=False
    )
    
    embed.add_field(
        name="",
        value="Select a category below to view commands:",
        inline=False
    )
    
    # List categories
    categories = [
        ("Leveling", "5 commands", "XP tracking, ranks, and leaderboards"),
        ("Admin", "4 commands", "Server management and configuration"),
    ]
    
    category_text = ""
    for name, count, desc in categories:
        category_text += f"**{name}** - {count}\n{desc}\n\n"
    
    embed.add_field(
        name="Available Categories",
        value=category_text,
        inline=False
    )
    
    embed.set_footer(text="Use the menu below for detailed command information")
    
    return embed

def create_leveling_help_embed() -> discord.Embed:
    """Create leveling commands help embed"""
    embed = discord.Embed(
        title="Leveling Commands",
        description="Commands for checking ranks, XP, and leaderboards",
        color=discord.Color.from_rgb(88, 101, 242)
    )
    
    commands_list = [
        ("rank [user]", "level, lvl", "View your or another user's rank card with level and XP progress"),
        ("xp [user]", "", "Check detailed XP information including stats and progress"),
        ("leaderboard [page]", "lb, top", "Display the server leaderboard showing top members by XP"),
    ]
    
    for cmd, aliases, description in commands_list:
        alias_text = f" (Aliases: {aliases})" if aliases else ""
        embed.add_field(
            name=f"`&{cmd.split()[0]}` / `/{cmd.split()[0]}`",
            value=f"**Usage:** `&{cmd}` or `/{cmd}`{alias_text}\n{description}",
            inline=False
        )
    
    embed.set_footer(text="Use the dropdown menu to view other categories")
    
    return embed

def create_admin_help_embed() -> discord.Embed:
    """Create admin commands help embed"""
    embed = discord.Embed(
        title="Admin Commands",
        description="Server administration commands (Requires Administrator permission)",
        color=discord.Color.from_rgb(88, 101, 242)
    )
    
    commands_list = [
        ("setlevel <user> <level>", "", "Set a specific user's level to any value"),
        ("addxp <user> <amount>", "", "Add a specific amount of XP to a user"),
        ("resetlevel <user>", "", "Reset a single user's level and XP data"),
        ("resetalllevels CONFIRM", "", "Reset ALL server level data (requires CONFIRM)"),
    ]
    
    for cmd, aliases, description in commands_list:
        alias_text = f" (Aliases: {aliases})" if aliases else ""
        embed.add_field(
            name=f"`&{cmd.split()[0]}` / `/{cmd.split()[0]}`",
            value=f"**Usage:** `&{cmd}` or `/{cmd}`{alias_text}\n{description}",
            inline=False
        )
    
    embed.set_footer(text="Use the dropdown menu to view other categories")
    
    return embed

class Help(commands.Cog):
    """Help command system"""
    
    def __init__(self, bot):
        self.bot = bot
        # Remove default help command
        bot.help_command = None
    
    @commands.hybrid_command(name='help', description='Display bot commands and information')
    @app_commands.describe(command='Specific command to get help for')
    async def help(self, ctx: commands.Context, command: Optional[str] = None):
        """Display help menu with command categories"""
        
        if command:
            # Show help for specific command
            cmd = self.bot.get_command(command)
            if cmd:
                embed = discord.Embed(
                    title=f"Command: {cmd.name}",
                    description=cmd.help or "No description available",
                    color=discord.Color.from_rgb(88, 101, 242)
                )
                
                # Add aliases if any
                if hasattr(cmd, 'aliases') and cmd.aliases:
                    embed.add_field(
                        name="Aliases",
                        value=", ".join(f"`{alias}`" for alias in cmd.aliases),
                        inline=False
                    )
                
                # Add usage
                usage = f"`&{cmd.name}`"
                if cmd.signature:
                    usage = f"`&{cmd.name} {cmd.signature}`"
                embed.add_field(name="Usage", value=usage, inline=False)
                
                await ctx.send(embed=embed)
            else:
                await ctx.send(f"Command `{command}` not found")
        else:
            # Show main help menu with interactive view
            embed = create_main_help_embed(self.bot)
            view = HelpView(self.bot, ctx.author.id)
            await ctx.send(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(Help(bot))
