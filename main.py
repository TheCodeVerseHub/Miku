"""
Miku - Discord Leveling Bot
Entry point for the bot
"""

if __name__ == "__main__":
    import sys
    sys.path.insert(0, 'src')
    from src.bot import main
    import asyncio
    asyncio.run(main())
