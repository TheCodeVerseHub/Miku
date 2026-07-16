"""
Tests for the XP formula system (formula_registry.py).
"""

import pytest
from src.services.formula_registry import (
    FormulaRegistry,
    QuadraticFormula,
    LinearFormula,
    BaseFormula,
)


class TestQuadraticFormula:
    """Tests for the Quadratic XP formula."""

    @pytest.fixture
    def formula(self):
        return QuadraticFormula()

    def test_level_1_requires_0_xp(self, formula):
        assert formula.xp_for_level(1) == 0

    def test_level_1_calculation(self, formula):
        assert formula.calculate_level(0) == 1
        assert formula.calculate_level(50) == 1
        assert formula.calculate_level(154) == 1

    def test_level_2_threshold(self, formula):
        # Level 2 requires: 5 * 2^2 + 50 * 2 + 100 = 20 + 100 + 100 = 220
        # Cumulative from level 1: 0 + 220 = 220
        xp_for_2 = formula.xp_for_level(2)
        assert xp_for_2 == 220
        assert formula.calculate_level(xp_for_2 - 1) == 1
        assert formula.calculate_level(xp_for_2) == 2

    def test_level_calculation_consistency(self, formula):
        """Verify that xp_for_level and calculate_level are consistent."""
        for level in [1, 5, 10, 20, 50, 100]:
            xp = formula.xp_for_level(level)
            computed = formula.calculate_level(xp)
            assert computed == level, f"Mismatch at level {level}: xp={xp}"

    def test_xp_to_next_level(self, formula):
        """Test the xp_to_next_level helper."""
        xp_needed, xp_progress, xp_required = formula.xp_to_next_level(0, 1)
        assert xp_needed == 220  # XP needed to reach level 2
        assert xp_progress == 0
        assert xp_required == 220

    def test_negative_xp(self, formula):
        assert formula.calculate_level(-100) == 1

    def test_zero_xp(self, formula):
        assert formula.calculate_level(0) == 1


class TestLinearFormula:
    """Tests for the Linear XP formula."""

    @pytest.fixture
    def formula(self):
        return LinearFormula()

    def test_defaults(self, formula):
        assert formula.base_xp == 100
        assert formula.increment == 25

    def test_level_1_requires_0_xp(self, formula):
        assert formula.xp_for_level(1) == 0

    def test_level_2_threshold(self, formula):
        # Level 1→2: base_xp + 0 = 100
        assert formula.xp_for_level(2) == 100
        assert formula.calculate_level(99) == 1
        assert formula.calculate_level(100) == 2

    def test_level_calculation_consistency(self, formula):
        for level in [1, 5, 10, 20]:
            xp = formula.xp_for_level(level)
            assert formula.calculate_level(xp) == level

    def test_custom_configuration(self):
        formula = LinearFormula()
        formula.base_xp = 200
        formula.increment = 50
        # Level 1→2: 200
        assert formula.xp_for_level(2) == 200
        # Level 2→3: 200 + 50 = 250
        assert formula.xp_for_level(3) == 200 + 250


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
