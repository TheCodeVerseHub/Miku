"""Tests for the XP formula system (formula_registry.py).

Level numbering is 0-based: a member who has never earned XP is level 0, and
reaching level ``L`` costs ``5L² + 50L + 100`` XP *for that step*, accumulated
across all previous levels. So ``xp_for_level(0) == 0`` and
``xp_for_level(1) == 155`` (see README "Leveling Formula").

These are the values the bot ships with; earlier versions of this file asserted
the older 1-based numbering (``xp_for_level(1) == 0``, ``calculate_level(0) == 1``),
which no implementation has produced for a long time - hence the red CI.
"""

import pytest

from services.formula_registry import (
    FormulaRegistry,
    LinearFormula,
    QuadraticFormula,
)

# Cumulative XP to reach a level, for the quadratic formula.
# Each step costs 5L² + 50L + 100: 155, 220, 295, 380, 475, ...
QUADRATIC_CUMULATIVE_XP = {0: 0, 1: 155, 2: 375, 3: 670, 4: 1050, 5: 1525, 10: 5675}


class TestQuadraticFormula:
    """Tests for the Quadratic XP formula."""

    @pytest.fixture
    def formula(self):
        return QuadraticFormula()

    def test_xp_for_level(self, formula):
        for level, expected in QUADRATIC_CUMULATIVE_XP.items():
            assert formula.xp_for_level(level) == expected, f"level {level}"

    def test_level_1_calculation(self, formula):
        assert formula.calculate_level(0) == 0
        assert formula.calculate_level(50) == 0
        assert formula.calculate_level(154) == 0
        assert formula.calculate_level(155) == 1

    def test_level_2_threshold(self, formula):
        # Level 2 costs 5 * 2² + 50 * 2 + 100 = 220 on top of level 1's 155.
        assert formula.calculate_level(374) == 1
        assert formula.calculate_level(375) == 2

    def test_level_calculation_consistency(self, formula):
        """Verify that xp_for_level and calculate_level are inverses."""
        for level in [0, 1, 5, 10, 20, 50, 100]:
            xp = formula.xp_for_level(level)
            assert formula.calculate_level(xp) == level, f"Mismatch at level {level}: xp={xp}"
            if level > 0:
                assert formula.calculate_level(xp - 1) == level - 1

    def test_xp_to_next_level(self, formula):
        """Test the xp_to_next_level helper."""
        xp_needed, xp_progress, xp_required = formula.xp_to_next_level(0, 0)
        assert xp_needed == 155  # XP needed to reach level 1
        assert xp_progress == 0
        assert xp_required == 155

        xp_needed, xp_progress, xp_required = formula.xp_to_next_level(375, 2)
        assert xp_progress == 0  # 375 is exactly level 2
        assert xp_required == 295  # level 3 costs 5*9 + 150 + 100
        assert xp_needed == 295

    def test_negative_xp(self, formula):
        assert formula.calculate_level(-100) == 0
        assert formula.xp_for_level(-5) == 0

    def test_zero_xp(self, formula):
        assert formula.calculate_level(0) == 0


class TestLinearFormula:
    """Tests for the Linear XP formula."""

    @pytest.fixture
    def formula(self):
        return LinearFormula()

    def test_defaults(self, formula):
        assert formula.base_xp == 100
        assert formula.increment == 25

    def test_xp_for_level(self, formula):
        # Step 1 costs 100, then +25 per level: 100, 125, 150, 175, ...
        assert formula.xp_for_level(0) == 0
        assert formula.xp_for_level(1) == 100
        assert formula.xp_for_level(2) == 225
        assert formula.xp_for_level(3) == 375
        assert formula.xp_for_level(4) == 550

    def test_level_2_threshold(self, formula):
        assert formula.calculate_level(99) == 0
        assert formula.calculate_level(100) == 1
        assert formula.calculate_level(224) == 1
        assert formula.calculate_level(225) == 2

    def test_level_calculation_consistency(self, formula):
        for level in [0, 1, 5, 10, 20]:
            xp = formula.xp_for_level(level)
            assert formula.calculate_level(xp) == level, f"Mismatch at level {level}: xp={xp}"

    def test_custom_configuration(self):
        formula = LinearFormula()
        formula.base_xp = 200
        formula.increment = 50
        assert formula.xp_for_level(1) == 200
        assert formula.xp_for_level(2) == 200 + 250
        assert formula.xp_for_level(3) == 200 + 250 + 300


class TestFormulaRegistry:
    """Tests for the FormulaRegistry."""

    @pytest.fixture
    def registry(self):
        r = FormulaRegistry()
        r.load_defaults()
        return r

    def test_register_and_get(self, registry):
        registry.register("custom", QuadraticFormula)
        formula = registry.get("custom")
        assert isinstance(formula, QuadraticFormula)

    def test_get_unknown_formula(self, registry):
        with pytest.raises(KeyError):
            registry.get("nonexistent")

    def test_load_defaults(self, registry):
        formulas = registry.list_formulas()
        assert "quadratic" in formulas
        assert "linear" in formulas

    def test_singleton_instances(self, registry):
        """Registry should return the same instance for repeated gets."""
        f1 = registry.get("quadratic")
        f2 = registry.get("quadratic")
        assert f1 is f2

    def test_register_invalid_class(self, registry):
        with pytest.raises(TypeError):
            registry.register("invalid", object)  # type: ignore

    def test_factory_method(self):
        registry = FormulaRegistry()
        registry.load_defaults()
        quad = registry.get("quadratic")
        assert quad.calculate_level(1000) >= 1
