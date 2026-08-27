"""Pluggable XP formula system.

Usage:
    from services.formula_registry import FormulaRegistry, QuadraticFormula

    registry = FormulaRegistry()
    registry.register("quadratic", QuadraticFormula)
    registry.register("linear", LinearFormula)

    formula = registry.get("quadratic")
    level = formula.calculate_level(total_xp)
    xp_needed = formula.xp_for_level(5)
"""

from __future__ import annotations

import abc
import logging
from typing import ClassVar

logger = logging.getLogger("miku.formula_registry")


class BaseFormula(abc.ABC):
    """Abstract base for an XP leveling formula."""

    name: ClassVar[str] = "base"

    @abc.abstractmethod
    def calculate_level(self, xp: int) -> int:
        """Derive the level from cumulative XP."""

    @abc.abstractmethod
    def xp_for_level(self, level: int) -> int:
        """Return the cumulative XP required to reach *exactly* this level."""

    def xp_to_next_level(self, current_xp: int, current_level: int) -> tuple[int, int, int]:
        """Return (xp_needed, xp_progress, xp_required_for_level)."""
        xp_for_current = self.xp_for_level(current_level)
        xp_for_next = self.xp_for_level(current_level + 1)
        xp_needed = xp_for_next - current_xp
        xp_progress = current_xp - xp_for_current
        xp_required_for_level = xp_for_next - xp_for_current
        return xp_needed, xp_progress, xp_required_for_level


class QuadraticFormula(BaseFormula):
    """Arcane/MEE6-style quadratic formula.

    Each level requires: 5L² + 50L + 100  (where L = target level).
    Cumulative XP is the sum of all previous level requirements.
    """

    name: ClassVar[str] = "quadratic"

    def calculate_level(self, xp: int) -> int:
        level = 0
        xp_needed = 0
        while xp_needed <= xp:
            level += 1
            xp_needed += 5 * (level ** 2) + (50 * level) + 100
        return max(0, level - 1)

    def xp_for_level(self, level: int) -> int:
        total_xp = 0
        for lvl in range(1, level + 1):
            total_xp += 5 * (lvl ** 2) + (50 * lvl) + 100
        return total_xp


class LinearFormula(BaseFormula):
    """Simpler linear formula.

    Each level requires a fixed amount of XP (base_xp_per_level)
    plus a small per-level increment (xp_increment).
    Formula per-level: base_xp_per_level + (level - 1) * xp_increment
    """

    name: ClassVar[str] = "linear"

    base_xp: int = 100
    increment: int = 25

    def calculate_level(self, xp: int) -> int:
        level = 0
        cumulative = 0
        while True:
            needed = self.base_xp + level * self.increment
            if cumulative + needed > xp:
                break
            cumulative += needed
            level += 1
        return level

    def xp_for_level(self, level: int) -> int:
        total_xp = 0
        for lvl in range(level):
            total_xp += self.base_xp + lvl * self.increment
        return total_xp


class FormulaRegistry:
    """Registry of available XP formulas.

    Register custom formulas::
        registry.register("custom", MyFormula)
        formula = registry.get("custom")
    """

    def __init__(self) -> None:
        self._formulas: dict[str, type[BaseFormula]] = {}
        self._instances: dict[str, BaseFormula] = {}

    def register(self, name: str, formula_cls: type[BaseFormula]) -> None:
        if not issubclass(formula_cls, BaseFormula):
            raise TypeError(f"{formula_cls.__name__} must inherit from BaseFormula")
        self._formulas[name] = formula_cls
        logger.info("Registered XP formula '%s' (%s)", name, formula_cls.__name__)

    def get(self, name: str) -> BaseFormula:
        if name not in self._instances:
            cls = self._formulas.get(name)
            if cls is None:
                raise KeyError(f"Unknown formula '{name}'. Available: {list(self._formulas)}")
            self._instances[name] = cls()
        return self._instances[name]

    def list_formulas(self) -> list[str]:
        return list(self._formulas)

    def load_defaults(self) -> None:
        """Register built-in formulas."""
        self.register("quadratic", QuadraticFormula)
        self.register("linear", LinearFormula)
