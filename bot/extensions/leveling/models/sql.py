from datetime import datetime, timezone
from typing import Any
from sqlalchemy import BigInteger, DateTime, Double
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def get_default_experience() -> float:
    # Lazy initialization here to prevent weird circular imports
    from ..services.leveling import MessageEvaluationService

    return MessageEvaluationService.calculate_experience_for_level(1)


class LevelingProfile(Base):
    __tablename__ = "leveling_profiles"

    guild_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    experience: Mapped[float] = mapped_column(Double, default=0)
    # Do not touch the defaults, it breaks the exp calculation system
    level: Mapped[int] = mapped_column(BigInteger, default=1)
    last_message_timestamp: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
