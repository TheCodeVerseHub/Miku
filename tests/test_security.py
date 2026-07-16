"""
Security-focused tests for the Miku dashboard and bot.

Tests:
- CSRF token generation and validation
- Rate limiting
- Input sanitization
- Session handling
"""

import time

import pytest


class TestCSRFProtection:
    """Tests for CSRF token generation and validation."""

    @pytest.fixture
    def secret(self):
        return "test-secret-key-at-least-32-chars-long!!"

    def test_generate_token(self, secret):
        from dashboard.backend.security import generate_csrf_token

        token = generate_csrf_token(secret)
        parts = token.split(":")
        assert len(parts) == 3
        assert len(parts[0]) == 64  # 32 bytes hex
        assert parts[1].isdigit()  # timestamp
        assert len(parts[2]) == 16  # HMAC signature

    def test_validate_own_token(self, secret):
        from dashboard.backend.security import generate_csrf_token, validate_csrf_token

        token = generate_csrf_token(secret)
        assert validate_csrf_token(token, secret) is True

    def test_reject_tampered_token(self, secret):
        from dashboard.backend.security import generate_csrf_token, validate_csrf_token

        token = generate_csrf_token(secret)
        tampered = token[:-1] + "x"  # Change last character
        assert validate_csrf_token(tampered, secret) is False

    def test_reject_invalid_format(self, secret):
        from dashboard.backend.security import validate_csrf_token

        assert validate_csrf_token("invalid", secret) is False
        assert validate_csrf_token("a:b", secret) is False
        assert validate_csrf_token("", secret) is False

    def test_different_secret_fails(self):
        from dashboard.backend.security import generate_csrf_token, validate_csrf_token

        token = generate_csrf_token("secret1")
        assert validate_csrf_token(token, "secret2") is False

    def test_expired_token(self, secret):
        from dashboard.backend.security import generate_csrf_token, validate_csrf_token

        # We can't easily travel in time, but we can test with a very short
        # max_age by manipulating the token
        import hmac
        import hashlib
        import os

        data = f"{os.urandom(32).hex()}:{int(time.time()) - 7200}"  # 2 hours old
        sig = hmac.new(secret.encode(), data.encode(), hashlib.sha256).hexdigest()[:16]
        old_token = f"{data}:{sig}"

        # Should fail with 1-hour max age
        assert validate_csrf_token(old_token, secret, max_age=3600) is False
        # Should pass with 3-hour max age
        assert validate_csrf_token(old_token, secret, max_age=7200) is True


class TestRateLimiter:
    """Tests for the in-memory rate limiter."""

    @pytest.fixture
    def limiter(self):
        from dashboard.backend.security import RateLimiter

        return RateLimiter(max_requests=3, window_seconds=60)

    def test_allows_within_limit(self, limiter):
        for _ in range(3):
            allowed, _ = limiter.check("test_key")
            assert allowed is True

    def test_blocks_over_limit(self, limiter):
        for _ in range(3):
            limiter.check("test_key")

        allowed, retry_after = limiter.check("test_key")
        assert allowed is False
        assert retry_after > 0

    def test_different_keys_independent(self, limiter):
        for _ in range(5):
            limiter.check("key_a")

        # key_b should still be allowed
        allowed, _ = limiter.check("key_b")
        assert allowed is True

    def test_reset(self, limiter):
        for _ in range(5):
            limiter.check("test_key")

        limiter.reset("test_key")
        allowed, _ = limiter.check("test_key")
        assert allowed is True


class TestInputValidation:
    """Tests for input sanitization and validation."""

    def test_sanitize_search_query(self):
        from dashboard.backend.security import sanitize_search_query

        assert sanitize_search_query("hello") == "hello"
        assert sanitize_search_query("hello world") == "hello world"
        assert sanitize_search_query("user@123") == "user@123"
        assert sanitize_search_query("script>alert('xss')<script") == "scriptalertxssscript"
        assert sanitize_search_query("1=1--") == "11"
        assert len(sanitize_search_query("a" * 200)) <= 100

    def test_validate_guild_id(self):
        from dashboard.backend.security import validate_guild_id

        # Discord snowflakes are ~17-19 digits
        assert validate_guild_id(123456789012345678) is True
        assert validate_guild_id(1) is False
        assert validate_guild_id(9999999999999999) is False  # 16 digits
        assert validate_guild_id(99999999999999999) is True  # 17 digits

    def test_validate_level(self):
        from dashboard.backend.security import validate_level

        assert validate_level(0) is True
        assert validate_level(100) is True
        assert validate_level(100000) is True
        assert validate_level(-1) is False
        assert validate_level(100001) is False

    def test_validate_xp_amount(self):
        from dashboard.backend.security import validate_xp_amount

        assert validate_xp_amount(0) is True
        assert validate_xp_amount(100) is True
        assert validate_xp_amount(-100) is True
        assert validate_xp_amount(-10_000_001) is False
        assert validate_xp_amount(10_000_001) is False
