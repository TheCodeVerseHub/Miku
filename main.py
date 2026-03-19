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
import importlib
import inspect
from pathlib import Path
from typing import Any, Callable, Coroutine, cast

# Add src directory to path so `import bot` resolves to `Miku/src/bot.py`.
# Note: there is also a legacy `Miku/bot/` package in this repo, so we insert
# `src/` at the front to make the intended module win.
src_path = str((Path(__file__).parent / "src").resolve())
if src_path not in sys.path:
    sys.path.insert(0, src_path)

if __name__ == "__main__":
    bot_module = importlib.import_module("bot")
    main_attr = getattr(bot_module, "main", None)

    if not callable(main_attr):
        raise RuntimeError(
            "Expected an async `main()` in `Miku/src/bot.py`, but it was not found. "
            f"Imported module: {getattr(bot_module, '__file__', bot_module)!r}"
        )

    if not inspect.iscoroutinefunction(main_attr):
        raise RuntimeError(
            "Imported `bot.main` is not async. This usually means Python resolved "
            "the legacy `Miku/bot/` package instead of `Miku/src/bot.py`. "
            f"Imported module: {getattr(bot_module, '__file__', bot_module)!r}"
        )

    async_main = cast(Callable[[], Coroutine[Any, Any, None]], main_attr)
    asyncio.run(async_main())

