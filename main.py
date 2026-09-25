"""
Miku - Discord Leveling Bot
Main entry point

Why does this file exist?
- It keeps the repo root clean: we run `python main.py` from the `Miku/` folder.
- It adds `Miku/src/` to Python's import path so `src/bot.py` can be imported as `bot`.
- It also adds the project root so `shared/` modules are importable.

If you're new:
- Most code you will edit lives in `src/` (cogs, utils, bot startup).
- This file should stay tiny and boring.
"""

import asyncio
import importlib
import inspect
import sys
from collections.abc import Callable, Coroutine
from pathlib import Path
from typing import Any, cast

PROJECT_ROOT = Path(__file__).parent.resolve()
SRC_PATH = str(PROJECT_ROOT / "src")

# `import bot` must resolve to `Miku/src/bot.py`, not to the legacy `Miku/bot/`
# package that also lives in this repository.
#
# This cannot use a simple `if path not in sys.path: sys.path.insert(0, path)`
# guard. An editable install (`uv sync`, `pip install -e .`) already puts
# `src/` on `sys.path`, but appends it *after* the project root - and the
# project root (which holds the legacy `bot/` package) is always on the path
# because it contains this file. The guard would then skip the insert and the
# legacy package would win, crashing startup with a pydantic error from
# `bot/config.py`. So always move both entries to the front, `src/` first.
for path in (str(PROJECT_ROOT), SRC_PATH):
    while path in sys.path:
        sys.path.remove(path)
    sys.path.insert(0, path)

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
