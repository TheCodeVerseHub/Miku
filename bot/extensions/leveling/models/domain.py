from dataclasses import dataclass

@dataclass
class MessageResult:
    """Result of processing a message
    If the user leveled up, previous_level will be the level they were previously at.
    """
    leveled_up: bool
    current_level: int
    previous_level: int | None
    current_experience: float
    previous_experience: float | None
