"""
Tests for the RankCardGenerator (src/utils/rank_card.py).
"""

from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_rank_card_initialization():
    """Test RankCardGenerator initializes correctly."""
    from utils.rank_card import RankCardGenerator

    generator = RankCardGenerator(width=800, height=200)
    assert generator.width == 800
    assert generator.height == 200

    await generator.close()


@pytest.mark.asyncio
async def test_rank_card_generation():
    """Test rank card generation returns bytes."""
    from utils.rank_card import RankCardGenerator

    generator = RankCardGenerator()

    with patch.object(generator, "_fetch_avatar", AsyncMock(return_value=None)):
        result = await generator.generate_rank_card(
            avatar_url="https://example.com/avatar.png",
            username="TestUser",
            rank=1,
            level=10,
            current_xp=150,
            required_xp=220,
            total_xp=3850,
            messages=100,
        )

        assert isinstance(result, bytes)
        assert len(result) > 0

    await generator.close()


@pytest.mark.asyncio
async def test_rank_card_caching():
    """Test that identical cards are cached."""
    from utils.rank_card import RankCardGenerator

    generator = RankCardGenerator(card_cache_size=10, card_cache_ttl=60)

    with patch.object(generator, "_fetch_avatar", AsyncMock(return_value=None)):
        result1 = await generator.generate_rank_card(
            avatar_url="https://example.com/avatar.png",
            username="CacheTest",
            rank=1, level=5,
            current_xp=50, required_xp=220,
            total_xp=500, messages=20,
        )

        # Second call should use cache
        result2 = await generator.generate_rank_card(
            avatar_url="https://example.com/avatar.png",
            username="CacheTest",
            rank=1, level=5,
            current_xp=50, required_xp=220,
            total_xp=500, messages=20,
        )

        assert result1 == result2

    await generator.close()


@pytest.mark.asyncio
async def test_avatar_fetch_caching():
    """Test that avatars are downloaded once and then served from cache."""
    import io

    from aioresponses import aioresponses
    from PIL import Image

    from utils.rank_card import RankCardGenerator

    url = "https://cdn.example.com/avatar.png"
    generator = RankCardGenerator(avatar_cache_size=10, avatar_cache_ttl=60)

    # A real (tiny) PNG: the generator decodes the response with Pillow, so a
    # hand-rolled byte string that only *looks* like a PNG returns None.
    buffer = io.BytesIO()
    Image.new("RGBA", (8, 8), (255, 0, 0, 255)).save(buffer, format="PNG")
    png_bytes = buffer.getvalue()

    with aioresponses() as mocked:
        mocked.get(url, status=200, body=png_bytes)

        avatar = await generator._fetch_avatar(url)
        assert avatar is not None

        # A second fetch must be served from the avatar cache (aioresponses
        # only registered one response for that URL).
        avatar2 = await generator._fetch_avatar(url)
        assert avatar2 is avatar

    await generator.close()


@pytest.mark.asyncio
async def test_avatar_fetch_failure_returns_none():
    """A failed avatar download must not raise - the card still renders."""
    from aioresponses import aioresponses

    from utils.rank_card import RankCardGenerator

    url = "https://cdn.example.com/missing.png"
    generator = RankCardGenerator()

    with aioresponses() as mocked:
        mocked.get(url, status=404)
        assert await generator._fetch_avatar(url) is None

    await generator.close()


@pytest.mark.asyncio
async def test_save_to_bytes():
    """Test the backwards-compatible save_to_bytes method."""
    from PIL import Image

    from utils.rank_card import RankCardGenerator

    generator = RankCardGenerator()
    img = Image.new("RGB", (100, 100), (255, 0, 0))
    result = generator.save_to_bytes(img)
    assert result is not None
    assert result.readable()

    await generator.close()
