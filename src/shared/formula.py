"""
Shared XP Formula Module.

This module provides a single source of truth for XP/level calculations.
Both the bot (src/) and the dashboard (dashboard/) import from here,
eliminating the duplicated formula logic that previously existed.

Usage:
    from shared.formula import calculate_level, calculate_xp_for_level

    level = calculate_level(1000)
    xp_needed = calculate_xp_for_level(10)
"""

from __future__ import annotations

from typing import Tuple


def calculate_level(xp: int) -> int:
    """Calculate the level from cumulative XP.

    Uses the quadratic formula:
        XP per level = 5L² + 50L + 100

    Args:
        xp: Total accumulated XP.

    Returns:
        Level (0 or higher).
    """
    if xp <= 0:
        return 0

    level = 0
    cumulative = 0
    while True:
        level += 1
        needed = 5 * (level ** 2) + (50 * level) + 100
        if cumulative + needed > xp:
            return max(0, level - 1)
        cumulative += needed


def calculate_xp_for_level(level: int) -> int:
    """Calculate the cumulative XP required to reach a specific level.

    Args:
        level: The target level.

    Returns:
        Total XP needed to reach this level.
    """
    if level <= 1:
        return 0

    total = 0
    for lvl in range(1, level + 1):
        total += 5 * (lvl ** 2) + (50 * lvl) + 100
    return total


def calculate_xp_to_next_level(current_xp: int, current_level: int) -> Tuple[int, int, int]:
    """Calculate progress toward the next level.

    Args:
        current_xp: Current total XP.
        current_level: Current level.

    Returns:
        Tuple of (xp_needed, xp_progress, xp_required_for_level).
    """
    xp_for_current = calculate_xp_for_level(current_level)
    xp_for_next = calculate_xp_for_level(current_level + 1)
    xp_needed = xp_for_next - current_xp
    xp_progress = current_xp - xp_for_current
    xp_required = xp_for_next - xp_for_current
    return xp_needed, xp_progress, xp_required


def calculate_xp_progress_percent(current_xp: int, current_level: int) -> float:
    """Calculate the percentage progress to the next level.

    Args:
        current_xp: Current total XP.
        current_level: Current level.

    Returns:
        Progress percentage (0.0 to 100.0).
    """
    _, xp_progress, xp_required = calculate_xp_to_next_level(current_xp, current_level)
    if xp_required <= 0:
        return 100.0
    return round((xp_progress / xp_required) * 100, 1)
