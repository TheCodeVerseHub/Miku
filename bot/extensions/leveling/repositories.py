"""Repository layer for the legacy leveling system.

If you're new to the "repo/service" split:
- Repositories are thin wrappers around the ORM/session.
- They do *no* business logic; they just load/save/delete models.
- Services (see `services/`) build higher-level behavior on top.
"""

from datetime import timezone
from sqlalchemy.ext.asyncio.session import AsyncSession

from .models.sql import LevelingProfile

# We're doing some hacky stuff with the timezones here because SQLAlchemy and the message eval service are complaining otherwise.
class LevelingProfileRepository:
    session: AsyncSession

    def __init__(self, session):
        self.session = session

    async def get_by_member_id(
        self, member_id: int, guild_id: int
    ) -> LevelingProfile | None:
        profile = await self.session.get(LevelingProfile, (guild_id, member_id))
        if profile and profile.last_message_timestamp:
            profile.last_message_timestamp = profile.last_message_timestamp.replace(tzinfo=timezone.utc)
        return profile

    async def save(self, profile: LevelingProfile) -> LevelingProfile:
        if profile.last_message_timestamp:
            profile.last_message_timestamp = profile.last_message_timestamp.replace(tzinfo=timezone.utc)
        self.session.add(profile)
        await self.session.flush()
        await self.session.refresh(profile)
        return profile

    async def delete(self, profile: LevelingProfile) -> None:
        await self.session.delete(profile)
