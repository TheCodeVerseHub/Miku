"""Rank card image generation for the legacy leveling system.

This generator fetches user avatars over HTTP (aiohttp), then uses Pillow to
render a simple "rank card" PNG. It also uses in-memory caches to reduce
repeated work.

Important: call `await RankCardGenerator.close()` during shutdown to close the
aiohttp session.
"""

import asyncio
import io
import logging
from typing import Optional, Tuple

import aiohttp
from cachetools import TTLCache
from discord import Member
from PIL import Image, ImageDraw, ImageFont

from ..models.sql import LevelingProfile


class RankCardGenerator:
    """High-performance rank card generator with caching and DI."""

    def __init__(
        self,
        font_paths: Optional[list[str]] = None,
        avatar_cache_size: int = 512,
        avatar_cache_ttl: int = 600,
        card_cache_size: int = 256,
        card_cache_ttl: int = 60,
    ):
        self._http = aiohttp.ClientSession()
        self._logger = logging.getLogger(self.__class__.__name__)

        self.width = 900
        self.height = 300

        self.bg_color = (30, 30, 40)  # dark gray
        self.text_color = (255, 255, 255)  # white
        self.secondary_text_color = (180, 180, 180)  # light gray

        # Default paths assume a UNIX-like environment
        self._font_paths = font_paths or [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ]

        # caches
        self._avatar_cache: TTLCache[str, Image.Image] = TTLCache(
            maxsize=avatar_cache_size,
            ttl=avatar_cache_ttl,
        )

        self._card_cache: TTLCache[str, bytes] = TTLCache(
            maxsize=card_cache_size,
            ttl=card_cache_ttl,
        )

        self._font_cache: dict[tuple[int, bool], ImageFont.FreeTypeFont] = {}

        self._logger.info("RankCardGenerator initialized")

    async def close(self) -> None:
        await self._http.close()

    async def fetch_avatar(self, avatar_url: str) -> Optional[Image.Image]:
        """
        Fetch an avatar from the given URL and store it in the cache.

        Args:
            avatar_url (str): The URL of the avatar to fetch.

        Returns:
            Optional[Image.Image]: The fetched avatar, or None if the fetch failed.
        """
        if avatar_url in self._avatar_cache:
            return self._avatar_cache[avatar_url]

        try:
            async with self._http.get(avatar_url) as resp:
                if resp.status != 200:
                    self._logger.warning(
                        "Avatar fetch failed (%s): status=%s",
                        avatar_url,
                        resp.status,
                    )
                    return None

                data = await resp.read()
                avatar = Image.open(io.BytesIO(data)).convert("RGBA")

                self._avatar_cache[avatar_url] = avatar

                return avatar

        except asyncio.TimeoutError:
            self._logger.warning("Avatar fetch timeout: %s", avatar_url)

        except aiohttp.ClientError:
            self._logger.exception("Avatar HTTP error: %s", avatar_url)

        except Exception:
            self._logger.exception("Unexpected avatar fetch failure: %s", avatar_url)

        return None

    def get_font(self, size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
        """
        Fetches a font of a given size and boldness.

        The font is fetched from one of the following paths (in order of preference):
        - /usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf
        - /usr/share/fonts/truetype/dejavu/DejaVuSans.ttf
        - /usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf
        - /usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf

        If none of the above fonts are available, falls back to the default font.

        Args:
            size (int): The size of the font to fetch.
            bold (bool, optional): Whether to fetch a bold font. Defaults to False.

        Returns:
            ImageFont.FreeTypeFont: The fetched font.
        """
        key = (size, bold)

        if key in self._font_cache:
            return self._font_cache[key]

        font_candidates = [
            (
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
                if bold
                else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
            ),
            (
                "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
                if bold
                else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"
            ),
        ]

        for path in font_candidates:
            try:
                font = ImageFont.truetype(path, size)
                self._font_cache[key] = font
                return font
            except OSError:
                continue

        self._logger.warning("Falling back to default font")
        font = ImageFont.load_default()
        self._font_cache[key] = font  # type: ignore
        return font  # type: ignore

    def create_circular_avatar(
        self, avatar: Image.Image, size: int = 120
    ) -> Image.Image:
        """
        Creates a circular avatar from a given image.

        Args:
            avatar (Image.Image): The image to create a circular avatar from.
            size (int, optional): The size of the avatar to create. Defaults to 120.

        Returns:
            Image.Image: The created circular avatar.
        """
        avatar = avatar.resize((size, size), Image.Resampling.LANCZOS)

        mask = Image.new("L", (size, size), 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse((0, 0, size, size), fill=255)

        output = Image.new("RGBA", (size, size))
        output.paste(avatar, (0, 0))
        output.putalpha(mask)

        return output

    async def generate_rank_card(
        self,
        avatar_url: str,
        username: str,
        rank: int,
        level: int,
        current_xp: int,
        required_xp: int,
        total_xp: int,
        messages: int,
        accent_color: Tuple[int, int, int] = (88, 101, 242),
    ) -> bytes:
        """
        Generates a rank card image for a given user.

        Args:
            avatar_url (str): URL of the user's avatar.
            username (str): Username of the user.
            rank (int): Rank of the user.
            level (int): Level of the user.
            current_xp (int): Current XP of the user.
            required_xp (int): Required XP to reach the next level.
            total_xp (int): Total XP of the user.
            messages (int): Total messages sent by the user.
            accent_color (Tuple[int, int, int], optional): Accent color of the rank card. Defaults to (88, 101, 242).

        Returns:
            bytes: Bytes of the generated rank card image.
        """
        cache_key = f"{username}:{rank}:{level}:{current_xp}:{messages}"
        self._logger.debug("Generating rank card for %s with cache key %s", username, cache_key)

        if cache_key in self._card_cache:
            self._logger.debug("Rank card cache hit for %s", username)
            return self._card_cache[cache_key]

        try:
            img = Image.new("RGB", (self.width, self.height), self.bg_color)
            draw = ImageDraw.Draw(img)

            avatar = await self.fetch_avatar(avatar_url)

            if avatar:
                avatar_img = self.create_circular_avatar(avatar, 140)
                img.paste(avatar_img, (50, 80), avatar_img)

            font_username = self.get_font(45, bold=True)
            font_medium = self.get_font(30, bold=True)
            font_small = self.get_font(22)

            draw.text((220, 40), username, font=font_username, fill=self.text_color)

            draw.text((220, 100), f"RANK #{rank}", font=font_medium, fill=accent_color)
            draw.text(
                (420, 100), f"LEVEL {level}", font=font_medium, fill=self.text_color
            )

            progress = (current_xp / required_xp) if required_xp else 0
            progress_text = f"{current_xp:,} / {required_xp:,} XP"

            draw.text((220, 160), progress_text, font=font_small, fill=self.text_color)

            stats = (
                f"Total XP: {total_xp:,} • Messages: {messages:,} • {progress*100:.1f}%"
            )
            draw.text(
                (220, 210), stats, font=font_small, fill=self.secondary_text_color
            )

            buffer = io.BytesIO()
            img.save(buffer, "PNG")
            buffer.seek(0)

            result = buffer.getvalue()

            self._card_cache[cache_key] = result

            return result

        except Exception:
            self._logger.exception("Rank card generation failed for %s", username)
            raise
