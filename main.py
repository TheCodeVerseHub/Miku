"""
Miku - Discord Leveling Bot
Main entry point
"""

import sys
import asyncio
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

if __name__ == "__main__":
    from bot import main
    asyncio.run(main())

