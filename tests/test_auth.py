"""Tests for authentication module."""

import base64

from starlette.requests import Request

from rpi.server.auth import (
    _parse_basic_auth,
    hash_password,
    verify_password,
)


class TestPasswordHashing:
    """Tests for password hashing functions."""

    def test_hash_password_creates_salted_hash(self):
        """hash_password should create a hash in salt$hash format."""
        password = "test_password_123"
        hashed = hash_password(password)

        assert "$" in hashed
        salt, key = hashed.split("$", 1)
        assert len(salt) == 32  # 16 bytes in hex
        assert len(key) == 64  # 32 bytes in hex

    def test_hash_password_unique_per_call(self):
        """Each call to hash_password should produce unique output."""
        password = "same_password"
        hash1 = hash_password(password)
        hash2 = hash_password(password)

        assert hash1 != hash2  # Different salts

    def test_verify_password_correct(self):
        """verify_password should return True for correct password."""
        password = "correct_password"
        hashed = hash_password(password)

        assert verify_password(password, hashed) is True

    def test_verify_password_incorrect(self):
        """verify_password should return False for incorrect password."""
        password = "correct_password"
        hashed = hash_password(password)

        assert verify_password("wrong_password", hashed) is False

    def test_verify_password_invalid_hash_format(self):
        """verify_password should return False for invalid hash format."""
        assert (
            verify_password("password", "invalid_hash_no_separator") is False
        )


class TestBasicAuthParsing:
    """Tests for basic auth header parsing."""

    def _make_request(self, auth_header: str | None = None) -> Request:
        """Create a mock request with the given auth header."""
        headers = {}
        if auth_header is not None:
            headers["authorization"] = auth_header
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [(k.encode(), v.encode()) for k, v in headers.items()],
        }
        return Request(scope)

    def test_parse_basic_auth_valid(self):
        """Should extract password from valid basic auth header with correct username."""
        password = "my_secret_password"
        credentials = base64.b64encode(f"admin:{password}".encode()).decode()
        request = self._make_request(f"Basic {credentials}")

        assert _parse_basic_auth(request) == password

    def test_parse_basic_auth_wrong_username(self):
        """Should return None for incorrect username."""
        credentials = base64.b64encode(b"wronguser:password").decode()
        request = self._make_request(f"Basic {credentials}")

        assert _parse_basic_auth(request) is None

    def test_parse_basic_auth_no_header(self):
        """Should return None when no auth header present."""
        request = self._make_request()

        assert _parse_basic_auth(request) is None

    def test_parse_basic_auth_wrong_scheme(self):
        """Should return None for non-Basic auth schemes."""
        request = self._make_request("Bearer some_token")

        assert _parse_basic_auth(request) is None

    def test_parse_basic_auth_invalid_base64(self):
        """Should return None for invalid base64."""
        request = self._make_request("Basic not_valid_base64!!!")

        assert _parse_basic_auth(request) is None

    def test_parse_basic_auth_no_colon(self):
        """Should return None when credentials have no colon."""
        credentials = base64.b64encode(b"no_colon_here").decode()
        request = self._make_request(f"Basic {credentials}")

        assert _parse_basic_auth(request) is None

    def test_parse_basic_auth_empty_password(self):
        """Should return empty string for empty password."""
        credentials = base64.b64encode(b"admin:").decode()
        request = self._make_request(f"Basic {credentials}")

        assert _parse_basic_auth(request) == ""

    def test_parse_basic_auth_password_with_colon(self):
        """Should handle passwords containing colons."""
        password = "pass:word:with:colons"
        credentials = base64.b64encode(f"admin:{password}".encode()).decode()
        request = self._make_request(f"Basic {credentials}")

        assert _parse_basic_auth(request) == password
