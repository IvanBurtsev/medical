"""Тесты аутентификации дашборда."""

from __future__ import annotations

import base64
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from medax_radar.dashboard import check_basic_auth  # noqa: E402


def _header(user: str, password: str) -> str:
    token = base64.b64encode(f"{user}:{password}".encode("utf-8")).decode("ascii")
    return f"Basic {token}"


class TestBasicAuth(unittest.TestCase):
    def test_open_when_no_user_configured(self) -> None:
        self.assertTrue(check_basic_auth(None, "", ""))
        self.assertTrue(check_basic_auth("garbage", "", ""))

    def test_valid_credentials(self) -> None:
        self.assertTrue(check_basic_auth(_header("admin", "s3cret"), "admin", "s3cret"))

    def test_wrong_password(self) -> None:
        self.assertFalse(check_basic_auth(_header("admin", "nope"), "admin", "s3cret"))

    def test_wrong_user(self) -> None:
        self.assertFalse(check_basic_auth(_header("guest", "s3cret"), "admin", "s3cret"))

    def test_missing_header(self) -> None:
        self.assertFalse(check_basic_auth(None, "admin", "s3cret"))
        self.assertFalse(check_basic_auth("", "admin", "s3cret"))

    def test_non_basic_scheme(self) -> None:
        self.assertFalse(check_basic_auth("Bearer abc", "admin", "s3cret"))

    def test_malformed_base64(self) -> None:
        self.assertFalse(check_basic_auth("Basic !!!not-base64!!!", "admin", "s3cret"))

    def test_no_colon(self) -> None:
        token = base64.b64encode(b"nocolon").decode("ascii")
        self.assertFalse(check_basic_auth(f"Basic {token}", "admin", "s3cret"))


if __name__ == "__main__":
    unittest.main()
