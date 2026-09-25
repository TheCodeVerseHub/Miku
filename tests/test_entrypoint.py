"""Tests for the `main.py` entrypoint.

`main.py` has one job: make sure `import bot` resolves to `src/bot.py` and not
to the legacy `bot/` package that also lives in this repository. Getting that
wrong means `python main.py` (the documented way to run the bot, and the
container's CMD) starts - or crashes in - the wrong codebase, so it is worth a
regression test.

These tests do not need a Discord token or a database: `main.py` only performs
the import-path setup at module level, and the bot itself is only started under
its ``if __name__ == "__main__":`` guard.
"""

from __future__ import annotations

import importlib
import importlib.util
import inspect
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LEGACY_BOT_PACKAGE = PROJECT_ROOT / "bot" / "__init__.py"
SRC_BOT_MODULE = PROJECT_ROOT / "src" / "bot.py"


def _load_main_module():
    """Import `main.py` as a module without running `asyncio.run(main())`."""
    spec = importlib.util.spec_from_file_location("miku_main", PROJECT_ROOT / "main.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _resolve_bot_module_after_main_setup():
    """Run `main.py`'s path setup, then resolve `bot` the way it does."""
    _load_main_module()
    sys.modules.pop("bot", None)
    return importlib.import_module("bot")


def test_main_puts_src_first_on_sys_path():
    """`src/` must be searched before the project root (which holds `bot/`)."""
    _load_main_module()

    assert sys.path[0] == str(PROJECT_ROOT / "src"), "src/ must be the first sys.path entry"
    assert sys.path.index(str(PROJECT_ROOT)) > 0


def test_import_bot_resolves_to_src_bot_module():
    """The regression this file exists for: `bot` must not be the legacy package."""
    bot = _resolve_bot_module_after_main_setup()

    resolved = Path(bot.__file__).resolve()
    assert resolved == SRC_BOT_MODULE, f"`import bot` resolved to {resolved}"
    assert resolved != LEGACY_BOT_PACKAGE


def test_bot_exposes_async_main():
    """`main.py` requires an async `main()` in whichever `bot` module it imports."""
    bot = _resolve_bot_module_after_main_setup()

    assert callable(bot.main)
    assert inspect.iscoroutinefunction(bot.main)
