import importlib
import logging
import pathlib

import discord
from discord.ext import commands

from .config import settings
from .database import engine

intents = discord.Intents.default()
intents.message_content = True
intents.members = True


def _find_available_extensions() -> set[str]:
    """Discovers all (potential) extensions inside the extensions directory.

    Returns:
        set[str]: A set of all discovered modules
    """
    extensions_path = pathlib.Path(__file__).parent / "extensions"

    if not extensions_path.exists():
        raise FileNotFoundError(f"Extensions directory not found: {extensions_path}")

    base_import = f"{__name__}.extensions"

    discovered: set[str] = set()

    for child in extensions_path.iterdir():
        if child.name.startswith("_"):
            continue

        if child.is_file() and child.suffix == ".py":
            discovered.add(f"{base_import}.{child.stem}")
        elif child.is_dir():
            discovered.add(f"{base_import}.{child.name}")

    return discovered


class MikuBot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger = logging.getLogger(self.__class__.__name__)
        try:
            self.available_extensions = set(_find_available_extensions())
        except FileNotFoundError as e:
            self.logger.error(
                "Failed to discover available extensions: %s",
                e,
                exc_info=True,
                stack_info=True,
            )
            raise

    async def close(self) -> None:
        # We hook the close method in order to perform database connection cleanup
        from .database import close_db

        try:
            await close_db()
        except Exception as e:
            self.logger.error(
                "Could not close database connection: %s",
                e,
                exc_info=True,
                stack_info=True,
            )

        # We must call discord.py's close method afterwards, otherwise we will break the shutdown process
        return await super().close()

    async def setup_hook(self):
        """
        This function is called before the bot logs in.

        It loads all available extensions from the extensions directory.

        The process works as follows:

        1. It checks if all required core extensions are available.
           If any core extension is missing, it logs an error and raises an exception.
        2. It checks if all additional extensions are available.
           If any additional extension is missing, it logs a warning.
        3. It loads all available extensions in a deterministic order.
           If any extension fails to load, it logs an error.
           If the failed extension is a core extension, it raises an exception, preventing the bot from starting.
           If the failed extension is an additional extension, it logs an error but continues to the next extension.

        This function is responsible for loading all extensions and setting up the bot.
        """
        core_extensions = set(settings.core_extensions)
        optional_extensions = set(settings.additional_extensions)

        missing_core = core_extensions - self.available_extensions
        if missing_core:
            self.logger.error(
                "Missing required core extensions: %s",
                ", ".join(sorted(missing_core)),
            )
            raise RuntimeError("Required extensions are missing")

        self.missing_optional = optional_extensions - self.available_extensions
        for ext in sorted(self.missing_optional):
            self.logger.warning("Optional extension not found: %s", ext)

        to_load = sorted(
            (core_extensions | optional_extensions) & self.available_extensions
        )

        for extension in to_load:
            try:
                await self.load_extension(extension)
                self.logger.info("Loaded extension: %s", extension)

            except Exception:
                if extension in core_extensions:
                    self.logger.exception(
                        "Failed to load required extension: %s", extension
                    )
                    raise

                self.logger.exception(
                    "Failed to load optional extension: %s", extension
                )

    async def on_ready(self):
        if self.user is None:
            try:
                raise Exception(
                    "Bot is not logged in, but on_ready event was triggered regardless. This is a bug."
                )
            except Exception as e:
                # This try/catch is here to avoid duplicating the log message in the exception and then the logger call.
                # Feel free to change this if you deem this ugly.
                self.logger.error(e, exc_info=True, stack_info=True)
                raise
        self.logger.info(
            f"Logged in as {self.user.name}#{self.user.discriminator} ({self.user.id})"
        )


bot = MikuBot(settings.command_prefix, intents=intents)


def main():
    bot.run(settings.discord_token.get_secret_value(), log_handler=None)
