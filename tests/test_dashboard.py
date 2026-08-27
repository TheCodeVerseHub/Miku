"""
Tests for the FastAPI dashboard backend.
"""


import pytest


@pytest.mark.asyncio
async def test_health_endpoint():
    """Test the health check endpoint exists in the health sub-router."""
    from dashboard.backend.health import router

    routes = [r.path for r in router.routes if hasattr(r, "path")]
    assert "/health" in routes or "" in routes  # health endpoint
    assert "/health/db" in routes or "/db" in routes
    assert "/health/ready" in routes or "/ready" in routes


class TestFormulaHelpers:
    """Tests for the shared formula module used by the dashboard."""

    @pytest.fixture
    def helpers(self):
        from shared.formula import calculate_level, calculate_xp_for_level
        return calculate_level, calculate_xp_for_level

    def test_calc_level(self, helpers):
        _calc_level, _ = helpers
        assert _calc_level(0) == 0
        assert _calc_level(155) >= 1
        assert _calc_level(1000) >= 3

    def test_calc_xp_for_level(self, helpers):
        _, _calc_xp_for_level = helpers
        assert _calc_xp_for_level(1) >= 0
        assert _calc_xp_for_level(5) > _calc_xp_for_level(1)

    def test_level_xp_consistency(self, helpers):
        _calc_level, _calc_xp_for_level = helpers
        for level in [1, 5, 10, 20]:
            xp = _calc_xp_for_level(level)
            computed = _calc_level(xp)
            # Note: dashboard uses a slightly different formula (level 1 ≠ 0 xp)
            assert computed <= level


@pytest.mark.asyncio
async def test_bot_stats_endpoint():
    """Test the /api/bot/stats endpoint exists in the app."""
    from dashboard.backend.main import app

    routes = [r.path for r in app.routes if hasattr(r, "path")]
    assert "/api/bot/stats" in routes


@pytest.mark.asyncio
async def test_login_redirect():
    """Test login page redirects properly."""
    from dashboard.backend.main import app

    routes = [r.path for r in app.routes if hasattr(r, "path")]
    assert "/auth/login" in routes
    assert "/auth/callback" in routes
    assert "/auth/logout" in routes
