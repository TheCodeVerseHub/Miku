import time

from discord.ext import commands


class GlobalCommandCooldown(commands.CommandError):
    """Raised when a user tries to run a command while it's on cooldown.

    Named distinctly from discord.py's own commands.CommandOnCooldown to
    avoid isinstance-check collisions in error handlers.
    """

    def __init__(self, retry_after: float):
        self.retry_after = retry_after
        super().__init__(f"Command on cooldown. Retry in {retry_after:.1f}s")


class CooldownManager:
    def __init__(self, cooldown_seconds: float = 5):
        self.cooldown_seconds = cooldown_seconds
        self.user_timestamps: dict[tuple[int, str], float] = {}

    def check(self, user_id: int, command_name: str) -> float:
        """Return seconds remaining on cooldown (0 if not on cooldown).

        If the user is NOT on cooldown, this also records the current time
        as their new "last used" timestamp for this command.
        """
        now = time.time()
        key = (user_id, command_name)
        last_used = self.user_timestamps.get(key, 0.0)
        elapsed = now - last_used

        if elapsed < self.cooldown_seconds:
            return self.cooldown_seconds - elapsed

        self.user_timestamps[key] = now
        return 0.0


# Global instance shared across all cogs.
cooldown_manager = CooldownManager(cooldown_seconds=5)
