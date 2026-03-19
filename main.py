"""
Miku - Discord Leveling Bot
Main entry point

Why does this file exist?
- It keeps the repo root clean: we run `python main.py` from the `Miku/` folder.
- It adds `Miku/src/` to Python's import path so `src/bot.py` can be imported as `bot`.

If you're new:
- Most code you will edit lives in `src/` (cogs, utils, bot startup).
- This file should stay tiny and boring.
"""

import sys
import asyncio
from pathlib import Path

# Add src directory to path so imports like `from bot import main` work.
# (This is a simple alternative to packaging the project during development.)
sys.path.insert(0, str(Path(__file__).parent / 'src'))

if __name__ == "__main__":
    from bot import main
    asyncio.run(main())

