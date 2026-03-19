"""Custom exception types for the legacy leveling extension.

Keeping extension-specific errors in one place makes it easier for cogs/services
to catch and handle them cleanly.
"""

from typing import Any


class LevelingError(Exception):
    pass

class MemberAlreadyHasLevelingProfile(LevelingError):
    pass
