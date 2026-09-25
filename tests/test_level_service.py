"""
Tests for the LevelService (src/services/level_service.py).
"""

from unittest.mock import AsyncMock, patch

import pytest

from services.level_service import LevelService, RestrictionType, XpSource
from utils.db_cache import LevelingCache

GUILD_ID = 987654321098765432
USER_ID = 123456789012345678


class TestLevelService:
    """Tests for LevelService business logic."""

    @pytest.fixture
    def service(self, mock_bot):
        return LevelService(mock_bot)

    def test_calculate_level(self, service):
        """Test level calculation using default quadratic formula (0-based)."""
        assert service.calculate_level(0) == 0
        assert service.calculate_level(155) == 1
        assert service.calculate_level(375) == 2
        assert service.calculate_level(5675) == 10

    def test_calculate_xp_for_level(self, service):
        """Test XP calculation for a level."""
        assert service.calculate_xp_for_level(0) == 0
        assert service.calculate_xp_for_level(1) == 155
        assert service.calculate_xp_for_level(2) == 375

    def test_calculate_xp_to_next_level(self, service):
        """Test XP-to-next-level calculation."""
        xp_needed, xp_progress, xp_required = service.calculate_xp_to_next_level(0, 0)
        assert xp_required == 155
        assert xp_needed == 155
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
        with patch("utils.database.get_user_data", AsyncMock(return_value=None)), \
             patch("utils.database.update_user_xp", AsyncMock()), \
             patch("utils.database.insert_xp_log", AsyncMock()), \
             patch("utils.database.get_guild_settings", AsyncMock(return_value=None)):

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
        with patch("utils.database.get_guild_settings",
                   AsyncMock(return_value={"xp_enabled": False})):

            result = await service.award_message_xp(mock_discord_message)
            assert result is None

    @pytest.mark.asyncio
    async def test_set_level(self, service):
        """Test admin set-level operation."""
        # 375 XP is a valid level 2 (level 1 costs 155, level 2 costs 220).
        existing = {"xp": 375, "level": 2, "messages": 5}
        with patch("utils.database.get_user_data", AsyncMock(return_value=existing)), \
             patch("utils.database.update_user_xp", AsyncMock()), \
             patch("utils.database.insert_xp_log", AsyncMock()), \
             patch("utils.database.insert_audit_log", AsyncMock()):

            result = await service.set_level(
                guild_id=123,
                user_id=456,
                level=10,
                admin_id=789,
                reason="Test",
            )
            assert result["old_level"] == 2
            assert result["new_level"] == 10
            assert result["xp"] == service.calculate_xp_for_level(10)

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
        existing = {"xp": 375, "level": 2, "messages": 5}  # a consistent level/xp pair
        with patch("utils.database.get_user_data", AsyncMock(return_value=existing)), \
             patch("utils.database.update_user_xp", AsyncMock()), \
             patch("utils.database.insert_xp_log", AsyncMock()), \
             patch("utils.database.insert_audit_log", AsyncMock()):

            result = await service.add_xp(
                guild_id=123,
                user_id=456,
                amount=500,
                admin_id=789,
                reason="Bonus",
            )
            assert result["old_xp"] == 375
            assert result["new_xp"] == 875
            assert result["old_level"] == 2
            assert result["new_level"] == 3

    @pytest.mark.asyncio
    async def test_remove_xp(self, service):
        """Test admin remove-XP operation."""
        # 5675 XP is exactly level 10, so 5675 - 200 = 5475 drops back to level 9.
        existing = {"xp": 5675, "level": 10, "messages": 50}
        with patch("utils.database.get_user_data", AsyncMock(return_value=existing)), \
             patch("utils.database.update_user_xp", AsyncMock()), \
             patch("utils.database.insert_xp_log", AsyncMock()), \
             patch("utils.database.insert_audit_log", AsyncMock()):

            result = await service.remove_xp(
                guild_id=123,
                user_id=456,
                amount=200,
                admin_id=789,
                reason="Correction",
            )
            assert result["new_xp"] == 5475
            assert result["new_level"] == 9


class TestAdminMutationsWithCache:
    """Admin actions must go through the cache, not around it.

    Writing the database directly and then invalidating the cache entry threw
    away every XP point that had not been flushed yet (up to 30s worth).
    """

    @pytest.fixture
    def cache(self, mock_bot) -> LevelingCache:
        return LevelingCache(mock_bot)

    @pytest.fixture
    def service(self, mock_bot, cache) -> LevelService:
        return LevelService(mock_bot, cache=cache)

    @staticmethod
    def _patch_db():
        return (
            patch("utils.database.get_user_data", AsyncMock(return_value=None)),
            patch("utils.database.update_user_xp", AsyncMock()),
            patch("utils.database.insert_xp_log", AsyncMock()),
            patch("utils.database.insert_audit_log", AsyncMock()),
        )

    @pytest.mark.asyncio
    async def test_add_xp_keeps_xp_that_is_only_in_the_cache(self, service, cache):
        await cache.update_user_xp(USER_ID, GUILD_ID, 100, 0, 1, 10.0)  # unflushed message XP
        get_user_data, update_user_xp, log_xp, log_audit = self._patch_db()

        with get_user_data, update_user_xp as db_write, log_xp, log_audit:
            result = await service.add_xp(GUILD_ID, USER_ID, 50, admin_id=1, reason="Bonus")

        assert result["old_xp"] == 100
        assert result["new_xp"] == 150
        data = await cache.get_user_data(USER_ID, GUILD_ID)
        assert data["xp"] == 150
        db_write.assert_not_awaited(), "the write must stay in the cache until the next flush"

    @pytest.mark.asyncio
    async def test_set_level_keeps_messages_and_cached_values(self, service, cache):
        await cache.update_user_xp(USER_ID, GUILD_ID, 100, 0, 7, 10.0)
        get_user_data, update_user_xp, log_xp, log_audit = self._patch_db()

        with get_user_data, update_user_xp, log_xp, log_audit:
            result = await service.set_level(GUILD_ID, USER_ID, 5, admin_id=1)

        assert result["new_level"] == 5
        data = await cache.get_user_data(USER_ID, GUILD_ID)
        assert data["level"] == 5
        assert data["xp"] == service.calculate_xp_for_level(5)
        assert data["messages"] == 7, "message count must survive an admin level change"

    @pytest.mark.asyncio
    async def test_reset_member_evicts_the_cache_before_deleting(self, service, cache):
        await cache.update_user_xp(USER_ID, GUILD_ID, 100, 0, 1, 10.0)

        async def reset_user_data(user_id, guild_id):
            assert (guild_id, user_id) not in cache._user_cache, (
                "an in-flight flush would re-create the row after the delete"
            )

        with patch("utils.database.reset_user_data", AsyncMock(side_effect=reset_user_data)), \
             patch("utils.database.insert_audit_log", AsyncMock()):
            await service.reset_member(GUILD_ID, USER_ID, admin_id=1)

        assert (GUILD_ID, USER_ID) not in cache._user_cache

    @pytest.mark.asyncio
    async def test_reset_guild_clears_the_cache_before_deleting(self, service, cache):
        await cache.update_user_xp(USER_ID, GUILD_ID, 100, 0, 1, 10.0)

        async def reset_guild_data(guild_id):
            assert cache._user_cache == {}, "the cache must be empty before the rows go away"

        with patch("utils.database.reset_guild_data", AsyncMock(side_effect=reset_guild_data)), \
             patch("utils.database.insert_audit_log", AsyncMock()):
            await service.reset_guild(GUILD_ID, admin_id=1)

    @pytest.mark.asyncio
    async def test_without_a_cache_the_database_is_still_written(self, mock_bot):
        """The direct-database fallback (tests, tooling) keeps working."""
        service = LevelService(mock_bot)
        existing = {"xp": 100, "level": 0, "messages": 1, "last_message_time": 5.0}

        with patch("utils.database.get_user_data", AsyncMock(return_value=existing)), \
             patch("utils.database.update_user_xp", AsyncMock()) as db_write, \
             patch("utils.database.insert_xp_log", AsyncMock()), \
             patch("utils.database.insert_audit_log", AsyncMock()):
            result = await service.add_xp(GUILD_ID, USER_ID, 50, admin_id=1)

        assert result["new_xp"] == 150
        db_write.assert_awaited_once()


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
