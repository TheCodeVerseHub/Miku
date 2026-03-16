import datetime
import random
import logging

from discord import Member, Message

from sqlalchemy.exc import IntegrityError
from ..errors.leveling import MemberAlreadyHasLevelingProfile
from ..models.sql import LevelingProfile
from ..models.domain import MessageResult
from ..repositories import LevelingProfileRepository


class LevelingProfileService:
    _logger: logging.Logger
    _repository: LevelingProfileRepository

    def __init__(self, repository: LevelingProfileRepository):
        self._logger = logging.getLogger(self.__class__.__name__)
        self._repository = repository

    async def get_or_create_profile(self, member: Member) -> LevelingProfile:
        self._logger.debug(
            "Attempting to retrieve potentially existing leveling profile for %d on %d",
            member.id,
            member.guild.id,
        )
        profile = await self._repository.get_by_member_id(member.id, member.guild.id)
        if profile is None:
            self._logger.debug(
                "User has no leveling profile on this guild yet, creating a new one"
            )
            profile = await self.create_new_profile(member)
        return profile

    async def create_new_profile(self, member: Member) -> LevelingProfile:
        self._logger.debug(
            "Creating new leveling profile for %d on %d", member.id, member.guild.id
        )
        try:
            return await self.save_profile(
                LevelingProfile(guild_id=member.guild.id, user_id=member.id)
            )
        except IntegrityError as e:
            self._logger.warning(
                "Attempted to create duplicate profile for %d on %d",
                member.id,
                member.guild.id,
            )
            raise MemberAlreadyHasLevelingProfile(
                f"The member {member.id} already has a leveling profile on the guild {member.guild.id}!"
            ) from e

    async def save_profile(self, member_profile: LevelingProfile) -> LevelingProfile:
        self._logger.debug(
            "Saving leveling profile for %d on %d",
            member_profile.user_id,
            member_profile.guild_id,
        )
        try:
            return await self._repository.save(member_profile)
        except Exception as e:
            self._logger.error(
                "Failed to save leveling profile for %d on %d",
                member_profile.user_id,
                member_profile.guild_id,
                exc_info=e,
            )
            raise

    async def delete_profile(self, member_profile: LevelingProfile) -> None:
        self._logger.debug(
            f"Deleting leveling profile for %d on %d",
            member_profile.user_id,
            member_profile.guild_id,
        )
        try:
            await self._repository.delete(member_profile)
        except Exception as e:
            self._logger.error(
                f"Failed to delete leveling profile for {member_profile.user_id} on {member_profile.guild_id}",
                exc_info=e,
            )
            raise


# XP awarded per eligible message
XP_MIN = 15
XP_MAX = 25

# Seconds a user must wait before earning XP again
EXPERIENCE_GAIN_COOLDOWN = datetime.timedelta(minutes=1)


from math import sqrt


class MessageEvaluationService:
    _logger: logging.Logger

    def __init__(self):
        self._logger = logging.getLogger(self.__class__.__name__)

    @staticmethod
    def calculate_level(xp: float) -> int:
        # Using the inverse of: XP = 5(L-1)^2 + 50(L-1)
        # Simplified quadratic solution: L = (-40 + sqrt(2500 + 20 * xp)) / 10
        if xp <= 0:
            return 1

        level = int((-40 + sqrt(2500 + 20 * xp)) / 10)

        # Safety check for floating point rounding errors
        while MessageEvaluationService.calculate_experience_for_level(level + 1) <= xp:
            level += 1

        return max(1, level)

    @staticmethod
    def calculate_experience_for_level(level: int) -> float:
        if level <= 1:
            return 0.0
        # This shifts the curve so Level 1 requires 0 XP
        return 5 * (level - 1) ** 2 + 50 * (level - 1)

    async def process_message(
        self, profile: LevelingProfile, message: Message
    ) -> MessageResult:
        """Processes a message and returns the result.
        This method does not mutate the profile.

        Args:
            profile (LevelingProfile): The profile to process the message for.
            message (Message): The message to process.

        Returns:
            MessageResult: The result of processing the message.
        """
        if profile.last_message_timestamp and (
            message.created_at - profile.last_message_timestamp
            < EXPERIENCE_GAIN_COOLDOWN
        ):
            return MessageResult(False, profile.level, None, profile.experience, None)
        xp_gain = random.randint(XP_MIN, XP_MAX)
        new_xp = profile.experience + xp_gain
        new_level = self.calculate_level(new_xp)
        leveled_up = new_level > profile.level
        return MessageResult(
            leveled_up, new_level, profile.level, new_xp, profile.experience
        )


class MessageService:
    # The sole purpose of this class is to bridge the gap between the MessageEvaluationService and the LevelingProfileService

    def __init__(
        self,
        profile_service: LevelingProfileService,
        evaluation_service: MessageEvaluationService,
    ):
        self.profile_service: LevelingProfileService = profile_service
        self.evaluation_service: MessageEvaluationService = evaluation_service

    async def handle_message(self, message: Message) -> MessageResult:
        if not isinstance(message.author, Member):
            raise ValueError("Message must be from a guild member")
        profile = await self.profile_service.get_or_create_profile(message.author)

        result = await self.evaluation_service.process_message(profile, message)

        # If the user didn't level up or gain experience, previous_experience is unset.
        if result.previous_experience is None:
            return result

        # In this case current is "new" and we need to propagate changes to DB
        profile.experience = result.current_experience
        profile.level = result.current_level
        profile.last_message_timestamp = message.created_at

        await self.profile_service.save_profile(profile)

        return result
