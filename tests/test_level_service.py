"""
Tests for the LevelService (src/services/level_service.py).
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.level_service import LevelService, XpSource, RestrictionType


class TestLevelService:
    """Tests for LevelService business logic."""

    @pytest.fixture
    def service(self, mock_bot):
        return LevelService(mock_bot)

    def test_calculate_level(self, service):
        """Test level calculation using default quadratic formula."""
        assert service.calculate_level(0) == 1
        assert service.calculate_level(220) >= 2
        assert service.calculate_level(3850) >= 10

    def test_calculate_xp_for_level(self, service):
        """Test XP calculation for a level."""
        assert service.calculate_xp_for_level(1) == 0
        assert service.calculate_xp_for_level(2) == 220

    def test_calculate_xp_to_next_level(self, service):
        """Test XP-to-next-level calculation."""
        xp_needed, xp_progress, xp_required = service.calculate_xp_to_next_level(0, 1)
        assert xp_required == 220
        assert xp_progress == 0

    def test_cooldown(self, service):
        """Test cooldown tracking."""
        user_id = 12345
        guild_id = 67890

        assert service.is_on_cooldown(user_id, guild_id) is False
        service.set_cooldown(user_id, guild_id)
        assert service.is_on_cooldown(user_id, guild_id) is True

    def test_cooldown_expires(self, service):
        """Test that cooldown expires after the specified time."""
        import time

        user_id = 12345
        guild_id = 67890

        service.set_cooldown(user_id, guild_id)
        with patch("time.time", return_value=time.time() + 61):
            assert service.is_on_cooldown(user_id, guild_id, cooldown_seconds=60) is False

    @pytest.mark.asyncio
    async def test_award_message_xp_bot(self, service, mock_discord_message):
        """Test that bot messages are ignored."""
        mock_discord_message.author.bot = True
        result = await service.award_message_xp(mock_discord_message)
        assert result is None

    @pytest.mark.asyncio
    async def test_award_message_xp_no_guild(self, service, mock_discord_message):
        """Test that DMs are ignored."""
        mock_discord_message.guild = None
        result = await service.award_message_xp(mock_discord_message)
        assert result is None

    @pytest.mark.asyncio
    async def test_award_message_xp_success(self, service, mock_discord_message):
        """Test successful XP award flow."""
        with patch("src.utils.database.get_user_data", AsyncMock(return_value=None)), \
             patch("src.utils.database.update_user_xp", AsyncMock()), \
             patch("src.utils.database.insert_xp_log", AsyncMock()), \
             patch("src.utils.database.get_guild_settings", AsyncMock(return_value=None)):

            result = await service.award_message_xp(mock_discord_message)

            assert result is not None
            assert result["xp_gained"] >= 15
            assert result["xp_gained"] <= 25
            assert result["old_level"] == 0
            assert result["new_level"] >= 0
            assert result["leveled_up"] is False

    @pytest.mark.asyncio
    async def test_award_message_xp_cooldown(self, service, mock_discord_message):
        """Test cooldown prevents double XP."""
        service.set_cooldown(mock_discord_message.author.id, mock_discord_message.guild.id)

        result = await service.award_message_xp(mock_discord_message)
        assert result is None

    @pytest.mark.asyncio
    async def test_award_message_xp_disabled(self, service, mock_discord_message):
        """Test that disabled XP system blocks awards."""
        with patch("src.utils.database.get_guild_settings",
                   AsyncMock(return_value={"xp_enabled": False})):

            result = await service.award_message_xp(mock_discord_message)
            assert result is None

    @pytest.mark.asyncio
    async def test_set_level(self, service):
        """Test admin set-level operation."""
        with patch("src.utils.database.get_user_data",
                   AsyncMock(return_value={"xp": 100, "level": 2, "messages": 5})), \
             patch("src.utils.database.set_user_level", AsyncMock()), \
             patch("src.utils.database.insert_xp_log", AsyncMock()), \
             patch("src.utils.database.insert_audit_log", AsyncMock()):

            result = await service.set_level(
                guild_id=123,
                user_id=456,
                level=10,
                admin_id=789,
                reason="Test",
            )
            assert result["old_level"] == 2
            assert result["new_level"] == 10
            assert result["xp"] > 0

    @pytest.mark.asyncio
    async def test_set_level_negative_raises(self, service):
        """Test negative level raises ValueError."""
        with pytest.raises(ValueError):
            await service.set_level(
                guild_id=123, user_id=456, level=-1, admin_id=789
            )

    @pytest.mark.asyncio
    async def test_add_xp(self, service):
        """Test admin add-XP operation."""
        with patch("src.utils.database.get_user_data",
                   AsyncMock(return_value={"xp": 100, "level": 2, "messages": 5})), \
             patch("src.utils.database.update_user_xp", AsyncMock()), \
             patch("src.utils.database.insert_xp_log", AsyncMock()), \
             patch("src.utils.database.insert_audit_log", AsyncMock()):

            result = await service.add_xp(
                guild_id=123,
                user_id=456,
                amount=500,
                admin_id=789,
                reason="Bonus",
            )
            assert result["old_xp"] == 100
            assert result["new_xp"] == 600
            assert result["old_level"] == 2
            assert result["new_level"] > 2

    @pytest.mark.asyncio
    async def test_remove_xp(self, service):
        """Test admin remove-XP operation."""
        with patch("src.utils.database.get_user_data",
                   AsyncMock(return_value={"xp": 1000, "level": 10, "messages": 50})), \
             patch("src.utils.database.update_user_xp", AsyncMock()), \
             patch("src.utils.database.insert_xp_log", AsyncMock()), \
             patch("src.utils.database.insert_audit_log", AsyncMock()):

            result = await service.remove_xp(
                guild_id=123,
                user_id=456,
                amount=200,
                admin_id=789,
                reason="Correction",
            )
            assert result["new_xp"] == 800


class TestXpSource:
    """Tests for XP source constants."""

    def test_xp_sources_defined(self):
        assert XpSource.MESSAGE == "MESSAGE"
        assert XpSource.VOICE == "VOICE"
        assert XpSource.ADMIN == "ADMIN"
        assert XpSource.BOOSTER == "BOOSTER"
        assert XpSource.EVENT == "EVENT"
        assert XpSource.IMPORT == "IMPORT"
        assert XpSource.BONUS == "BONUS"


class TestRestrictionType:
    """Tests for restriction type constants."""

    def test_restriction_types_defined(self):
        assert RestrictionType.IGNORE_ROLE == "IGNORE_ROLE"
        assert RestrictionType.ALLOW_CHANNEL == "ALLOW_CHANNEL"
        assert RestrictionType.BLOCK_CHANNEL == "BLOCK_CHANNEL"
        assert RestrictionType.IGNORE_CATEGORY == "IGNORE_CATEGORY"
        assert RestrictionType.ALLOW_CATEGORY == "ALLOW_CATEGORY"
