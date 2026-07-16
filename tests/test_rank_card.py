"""
Tests for the RankCardGenerator (src/utils/rank_card.py).
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_rank_card_initialization():
    """Test RankCardGenerator initializes correctly."""
    from src.utils.rank_card import RankCardGenerator

    generator = RankCardGenerator(width=800, height=200)
    assert generator.width == 800
    assert generator.height == 200

    await generator.close()


@pytest.mark.asyncio
async def test_rank_card_generation():
    """Test rank card generation returns bytes."""
    from src.utils.rank_card import RankCardGenerator

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
    from src.utils.rank_card import RankCardGenerator

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
    """Test avatar caching."""
    from src.utils.rank_card import RankCardGenerator

    generator = RankCardGenerator(avatar_cache_size=10, avatar_cache_ttl=60)

    # Mock the HTTP session
    mock_image_data = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100  # Minimal PNG
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.read = AsyncMock(return_value=mock_image_data)
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock()

    with patch.object(generator._http, "get", AsyncMock(return_value=mock_response)):
        avatar = await generator._fetch_avatar("https://example.com/avatar.png")
        assert avatar is not None

        # Second call should use cache (no HTTP request)
        avatar2 = await generator._fetch_avatar("https://example.com/avatar.png")
        assert avatar2 is avatar  # Same cached object

    await generator.close()


@pytest.mark.asyncio
async def test_save_to_bytes():
    """Test the backwards-compatible save_to_bytes method."""
    from src.utils.rank_card import RankCardGenerator
    from PIL import Image

    generator = RankCardGenerator()
    img = Image.new("RGB", (100, 100), (255, 0, 0))
    result = generator.save_to_bytes(img)
    assert result is not None
    assert result.readable()

    await generator.close()
