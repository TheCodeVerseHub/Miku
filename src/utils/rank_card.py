"""Rank card image generator used by the leveling cog.

This module lives under `src/utils/` so it can be imported as `utils.rank_card`
when running the rewrite in `src/`.

The API is intentionally small:
- `generate_rank_card(...)` -> bytes (PNG)
- `save_to_bytes(image)` -> BytesIO (PNG) for backwards-compat
- `close()` for cleaning up the internal aiohttp session
"""

from __future__ import annotations

import asyncio
import io
import logging
from typing import Optional, Tuple

import aiohttp
from cachetools import TTLCache
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger("miku.rank_card")


class RankCardGenerator:
    """Generate a simple rank card PNG with light caching."""

    def __init__(
        self,
        *,
        width: int = 900,
        height: int = 300,
        avatar_cache_size: int = 256,
        avatar_cache_ttl: int = 600,
        card_cache_size: int = 128,
        card_cache_ttl: int = 60,
    ) -> None:
        self.width = width
        self.height = height

        self._http = aiohttp.ClientSession()

        self._avatar_cache: TTLCache[str, Image.Image] = TTLCache(
            maxsize=avatar_cache_size,
            ttl=avatar_cache_ttl,
        )
        self._card_cache: TTLCache[str, bytes] = TTLCache(
            maxsize=card_cache_size,
            ttl=card_cache_ttl,
        )

        # Pillow stubs don't always model inheritance between FreeTypeFont and ImageFont.
        self._font_cache: dict[
            tuple[int, bool],
            ImageFont.FreeTypeFont | ImageFont.ImageFont,
        ] = {}

    async def close(self) -> None:
        await self._http.close()

    async def _fetch_avatar(self, avatar_url: str) -> Optional[Image.Image]:
        if avatar_url in self._avatar_cache:
            return self._avatar_cache[avatar_url]

        try:
            async with self._http.get(avatar_url) as resp:
                if resp.status != 200:
                    return None
                data = await resp.read()

            img = Image.open(io.BytesIO(data)).convert("RGBA")
            self._avatar_cache[avatar_url] = img
            return img

        except asyncio.TimeoutError:
            return None
        except aiohttp.ClientError:
            logger.exception("Avatar HTTP error")
            return None
        except Exception:
            logger.exception("Unexpected avatar decode error")
            return None

    def _get_font(
        self,
        size: int,
        *,
        bold: bool = False,
    ) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        key = (size, bold)
        if key in self._font_cache:
            return self._font_cache[key]

        candidates = [
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

        for path in candidates:
            try:
                font = ImageFont.truetype(path, size)
                self._font_cache[key] = font
                return font
            except OSError:
                continue

        font = ImageFont.load_default()
        self._font_cache[key] = font
        return font

    def _circular_avatar(self, avatar: Image.Image, *, size: int = 140) -> Image.Image:
        avatar = avatar.resize((size, size), Image.Resampling.LANCZOS)

        mask = Image.new("L", (size, size), 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse((0, 0, size, size), fill=255)

        output = Image.new("RGBA", (size, size))
        output.paste(avatar, (0, 0))
        output.putalpha(mask)
        return output

    def save_to_bytes(self, image: Image.Image) -> io.BytesIO:
        """Backwards compatible helper to produce a seeked BytesIO."""
        buff = io.BytesIO()
        image.save(buff, format="PNG")
        buff.seek(0)
        return buff

    async def generate_rank_card(
        self,
        *,
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
        """Generate a PNG rank card and return it as bytes."""

        cache_key = f"{username}:{rank}:{level}:{current_xp}:{required_xp}:{messages}"
        if cache_key in self._card_cache:
            return self._card_cache[cache_key]

        # Base card
        img = Image.new("RGB", (self.width, self.height), (30, 30, 40))
        draw = ImageDraw.Draw(img)

        # Avatar
        avatar = await self._fetch_avatar(avatar_url)
        if avatar is not None:
            avatar_img = self._circular_avatar(avatar, size=140)
            img.paste(avatar_img, (50, 80), avatar_img)

        # Text
        font_username = self._get_font(45, bold=True)
        font_medium = self._get_font(30, bold=True)
        font_small = self._get_font(22)

        draw.text((220, 40), username, font=font_username, fill=(255, 255, 255))
        draw.text((220, 100), f"RANK #{rank}", font=font_medium, fill=accent_color)
        draw.text((420, 100), f"LEVEL {level}", font=font_medium, fill=(255, 255, 255))

        # Progress bar
        progress = (current_xp / required_xp) if required_xp else 0.0
        progress = max(0.0, min(1.0, progress))

        bar_x, bar_y = 220, 150
        bar_w, bar_h = 600, 24
        draw.rounded_rectangle(
            (bar_x, bar_y, bar_x + bar_w, bar_y + bar_h),
            radius=12,
            fill=(55, 55, 70),
        )
        fill_w = int(bar_w * progress)
        if fill_w > 0:
            draw.rounded_rectangle(
                (bar_x, bar_y, bar_x + fill_w, bar_y + bar_h),
                radius=12,
                fill=accent_color,
            )

        draw.text(
            (220, 185),
            f"{current_xp:,} / {required_xp:,} XP",
            font=font_small,
            fill=(255, 255, 255),
        )
        draw.text(
            (220, 220),
            f"Total XP: {total_xp:,} • Messages: {messages:,} • {progress*100:.1f}%",
            font=font_small,
            fill=(180, 180, 180),
        )

        buff = io.BytesIO()
        img.save(buff, format="PNG")
        result = buff.getvalue()

        self._card_cache[cache_key] = result
        return result
