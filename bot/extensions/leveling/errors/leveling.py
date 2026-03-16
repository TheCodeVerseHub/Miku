from typing import Any


class LevelingError(Exception):
    pass

class MemberAlreadyHasLevelingProfile(LevelingError):
    pass
