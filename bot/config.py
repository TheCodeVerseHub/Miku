import logging
import sys
from logging.handlers import RotatingFileHandler

from colorlog import ColoredFormatter
from pydantic import Field, PostgresDsn, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    discord_token: SecretStr
    database_url: PostgresDsn
    additional_extensions: list[str] = Field(default=[])
    core_extensions: list[str] = Field(default=[])
    command_prefix: str = Field(default="&")
    developer_ids: list[int] = Field(default=[])

    model_config = SettingsConfigDict(env_file=".env")


LOG_DATE_FORMAT = "%Y/%m/%d %I:%M:%S %p"

file_handler = RotatingFileHandler(
    "latest.log", maxBytes=10 * 1024 * 1024, backupCount=10
)  # 10 MB log files per backup
file_formatter = logging.Formatter(
    "%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt=LOG_DATE_FORMAT
)
file_handler.setFormatter(file_formatter)

console_handler = logging.StreamHandler(sys.stdout)
console_formatter = ColoredFormatter(
    "%(asctime)s %(log_color)s%(levelname)-8s%(reset)s [%(name)s] %(message)s",
    datefmt=LOG_DATE_FORMAT,
    reset=True,
    log_colors={
        "DEBUG": "cyan",
        "INFO": "green",
        "WARNING": "yellow",
        "ERROR": "red",
        "CRITICAL": "red,bg_white",
    },
    style="%",
)
console_handler.setFormatter(console_formatter)

logging.basicConfig(level=logging.INFO, handlers=[file_handler, console_handler])


settings = Settings()  # type: ignore
