import importlib
import logging
import pathlib

import discord
from discord.ext import commands

from .config import settings

intents = discord.Intents.default()
intents.message_content = True
intents.members = True


def _is_module_a_discord_py_extension(import_string: str):
    """Checks if a module is a Discord.py extension.

    This method is used internally to validate discord.py extensions (cogs) before loading them.

    If a module is not a Discord.py extension, this function will attempt to "un-import" it by deleting it.
    This is mainly to free up memory and avoid memory leaks, though the implementation may be inadequate.

    Args:
        import_string (str): The import string of the module to check.

    Returns:
        bool: True if the module is a Discord.py extension, False otherwise.
    """
    try:
        module = importlib.import_module(import_string)
        if hasattr(module, "setup"):
            return True
        else:
            # This should - IN THEORY - free up memory and functionally "un-import" the module
            # Haven't tested it, someone will have to check it out in the future.
            del module
            return False
    except ModuleNotFoundError:
        return False


def _find_available_extensions() -> list[str]:
    """Finds all available Discord.py extensions (cogs) in the extensions directory.

    This method is used internally to discover and return a list of all available extensions.

    Returns:
        list[str]: A list of import strings of all available extensions.

    Raises:
        FileNotFoundError: If the extensions directory is not found.
    """
    # We need to lazy load this import, otherwise we'll create an infinite import loop
    import bot as package

    bot_base_direction = pathlib.Path(package.__file__).parent.joinpath("./extensions/")
    if not bot_base_direction.exists():
        raise FileNotFoundError(
            f"Could not find extension directory: {bot_base_direction}"
        )

    base_import_string = f"{package.__name__}.extensions"

    extensions = []
    for child in bot_base_direction.iterdir():
        if child.name.startswith("__"):
            continue
        if child.name.endswith(".py") or child.is_dir():
            if _is_module_a_discord_py_extension(f"{base_import_string}.{child.name}"):
                extensions.append(f"{base_import_string}.{child.name}")
    return extensions


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
            raise e

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
           If any core extension is missing, it raises an exception.
        2. It checks if all additional extensions are available.
           If any additional extension is missing, it logs a warning.
        3. It loads all available extensions.
           If any extension fails to load, it logs an error.
           If the failed extension is a core extension, it raises an exception, preventing the bot from starting.
           If the failed extension is an additional extension, it logs an error but continues to the next extension.

        This function is responsible for loading all extensions and setting up the bot.
        """
        core_extensions = set(settings.core_extensions)
        additional_extensions = set(settings.additional_extensions)

        if len(core_extensions & self.available_extensions) != len(core_extensions):
            try:
                raise Exception(
                    "The following core extensions are missing: %s"
                    % ", ".join(core_extensions - self.available_extensions)
                )
            except Exception as e:
                # Once again, the try/catch here is to avoid duplicating the log message and then the logger call
                # You can change this as well if you deem it too ugly to look at.
                self.logger.error(e, exc_info=True, stack_info=True)
                raise e

        for missing_additional_extension in (
            additional_extensions - self.available_extensions
        ):
            self.logger.warning(
                "The following additional extension is missing: %s",
                missing_additional_extension,
            )

        for extension in (
            core_extensions | additional_extensions
        ) & self.available_extensions:
            try:
                await self.load_extension(extension)
                self.logger.info("Loaded extension: %s", extension)
            except Exception as e:
                if extension in core_extensions:
                    self.logger.error(
                        "The required extension %s failed to load: %s",
                        extension,
                        e,
                        exc_info=True,
                        stack_info=True,
                    )
                    raise e
                else:
                    self.logger.error(
                        "Optional extension %s failed to load: %s",
                        extension,
                        e,
                        exc_info=True,
                        stack_info=True,
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
                raise e
        self.logger.info(
            f"Logged in as {self.user.name}#{self.user.discriminator} ({self.user.id})"
        )


bot = MikuBot(settings.command_prefix, intents=intents)


def main():
    bot.run(settings.discord_token.get_secret_value(), log_handler=None)
