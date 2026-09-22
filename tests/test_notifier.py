"""Тесты Telegram-нотификатора."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from medax_radar.notifier import build_summary, send_telegram  # noqa: E402


class TestSummary(unittest.TestCase):
    def test_build_summary(self) -> None:
        report = {
            "stats": {"leads": 592, "hot": 5, "warm": 12, "cold": 575,
                      "tenders": 49, "competitor_offers": 40},
            "generated_at": "2026-09-21T20:00:00+00:00",
        }
        text = build_summary(report)
        self.assertIn("592", text)
        self.assertIn("5", text)
        self.assertIn("49", text)
        self.assertIn("MedAX Radar", text)

    def test_send_no_settings_returns_false(self) -> None:
        self.assertFalse(send_telegram("test", token="", chat_id=""))

    def test_send_network_fails_gracefully(self) -> None:
        # токен/чатид заданы, но запрос упадёт (нет сети или невалидный токен)
        result = send_telegram("test", token="invalid", chat_id="123")
        # в зависимости от сети может упасть или вернуть False; проверяем только False/не крашится
        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()