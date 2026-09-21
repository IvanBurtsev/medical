"""Тесты парсера RSS zakupki.gov.ru (модуль 1, live)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from medax_radar.ingestion.zakupki import parse_rss  # noqa: E402

SAMPLE = """<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0"><channel>
<item>
  <title>Электронный аукцион №0340200003326011456</title>
  <link>https://zakupki.gov.ruhttps://zakupki.gov.ru/epz/order/notice/ea20/view/common-info.html?regNumber=0340200003326011456</link>
  <pubDate>Mon, 21 Sep 2026 13:34:52 GMT</pubDate>
  <description>&lt;strong&gt;Наименование объекта закупки: &lt;/strong&gt;Поставка стоматологической установки&lt;br/&gt;&lt;strong&gt;Наименование Заказчика: &lt;/strong&gt;ГБУЗ «Городская поликлиника»&lt;br/&gt;&lt;strong&gt;Начальная цена контракта: &lt;/strong&gt;980000.00&lt;br/&gt;&lt;strong&gt;Размещено: &lt;/strong&gt;21.09.2026&lt;br/&gt;</description>
</item>
<item>
  <title>Электронный аукцион №0340200003326011457</title>
  <link>https://zakupki.gov.ru/epz/order/notice/ea20/view/common-info.html?regNumber=0340200003326011457</link>
  <pubDate>Mon, 21 Sep 2026 10:00:00 GMT</pubDate>
  <description>&lt;strong&gt;Наименование объекта закупки: &lt;/strong&gt;Поставка УЗИ аппарата&lt;br/&gt;&lt;strong&gt;Начальная цена контракта: &lt;/strong&gt;2 750 000,50&lt;br/&gt;&lt;strong&gt;Размещено: &lt;/strong&gt;20.09.2026&lt;br/&gt;</description>
</item>
</channel></rss>
"""


class TestParseRss(unittest.TestCase):
    def setUp(self) -> None:
        self.items = parse_rss(SAMPLE)

    def test_count(self) -> None:
        self.assertEqual(len(self.items), 2)

    def test_first_fields(self) -> None:
        first = self.items[0]
        self.assertEqual(first["reg_number"], "0340200003326011456")
        self.assertEqual(first["title"], "Поставка стоматологической установки")
        self.assertEqual(first["customer"], "ГБУЗ «Городская поликлиника»")
        self.assertEqual(first["price"], 980000.0)
        self.assertEqual(first["published_at"], "2026-09-21")
        self.assertTrue(first["url"].startswith("https://zakupki.gov.ru/epz/"))

    def test_price_with_spaces_and_comma(self) -> None:
        self.assertEqual(self.items[1]["price"], 2750000.50)

    def test_missing_customer_is_empty(self) -> None:
        self.assertEqual(self.items[1]["customer"], "")


if __name__ == "__main__":
    unittest.main()
