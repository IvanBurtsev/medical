"""Тесты извлечения предложений конкурентов из HTML (модуль 2)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from medax_radar.extract import (  # noqa: E402
    extract_offers,
    parse_jsonld,
    parse_microdata,
    parse_price_regex,
    to_float,
)
from medax_radar.ingestion.competitor import CompetitorAdapter  # noqa: E402

JSONLD_HTML = """
<html><head>
<script type="application/ld+json">
{"@context":"https://schema.org","@type":"Product",
 "name":"Стоматологическая установка X200",
 "brand":{"@type":"Brand","name":"DentPro"},
 "offers":{"@type":"Offer","price":"429000","priceCurrency":"RUB"}}
</script>
</head><body><div>49 900 ₽</div></body></html>
"""

MICRODATA_HTML = """
<html><body>
<div itemscope itemtype="https://schema.org/Product">
  <span itemprop="name">Компрессор AirPro 100</span>
  <meta itemprop="price" content="68000">
  <meta itemprop="priceCurrency" content="RUB">
</div>
</body></html>
"""

REGEX_HTML = """
<html><body>
<div class="item">Матрас 3+1</div>
<div class="price">49 900 ₽</div>
<div class="item">Стерилизатор B23</div>
<div class="price">129 000 руб.</div>
</body></html>
"""


class TestToFloat(unittest.TestCase):
    def test_formats(self) -> None:
        self.assertEqual(to_float("1999"), 1999.0)
        self.assertEqual(to_float("1 234,56"), 1234.56)
        self.assertEqual(to_float("1,234.56"), 1234.56)
        self.assertEqual(to_float("49 900 ₽"), 49900.0)
        self.assertIsNone(to_float(""))
        self.assertIsNone(to_float("нет цены"))


class TestJsonLd(unittest.TestCase):
    def test_parse(self) -> None:
        offers = parse_jsonld(JSONLD_HTML)
        self.assertEqual(len(offers), 1)
        self.assertEqual(offers[0]["price"], 429000.0)
        self.assertEqual(offers[0]["brand"], "DentPro")

    def test_precedence_over_regex(self) -> None:
        offers = extract_offers(JSONLD_HTML, "https://x.ru/", "K")
        self.assertEqual(len(offers), 1)
        self.assertEqual(offers[0]["product_name"], "Стоматологическая установка X200")


class TestMicrodata(unittest.TestCase):
    def test_parse(self) -> None:
        offers = parse_microdata(MICRODATA_HTML)
        self.assertEqual(len(offers), 1)
        self.assertEqual(offers[0]["price"], 68000.0)

    def test_extract(self) -> None:
        offers = extract_offers(MICRODATA_HTML, "https://x.ru/", "K", region="Ростовская область")
        self.assertEqual(len(offers), 1)
        self.assertEqual(offers[0]["competitor"], "K")
        self.assertEqual(offers[0]["region"], "Ростовская область")


class TestRegexFallback(unittest.TestCase):
    def test_parse(self) -> None:
        offers = parse_price_regex(REGEX_HTML)
        prices = sorted(o["price"] for o in offers)
        self.assertEqual(prices, [49900.0, 129000.0])

    def test_extract_dedup(self) -> None:
        offers = extract_offers(REGEX_HTML, "https://x.ru/", "K")
        names = [o["product_name"] for o in offers]
        self.assertIn("Матрас 3+1", names)
        self.assertEqual(len(names), len(set(names)))


class TestAllowlist(unittest.TestCase):
    def test_allowed_same_domain(self) -> None:
        self.assertTrue(CompetitorAdapter._allowed(
            "https://shop.ru/catalog/", "https://shop.ru", {"allowlist_enforced": True}))

    def test_blocked_foreign_domain(self) -> None:
        self.assertFalse(CompetitorAdapter._allowed(
            "https://evil.ru/x", "https://shop.ru", {"allowlist_enforced": True}))

    def test_disabled(self) -> None:
        self.assertTrue(CompetitorAdapter._allowed(
            "https://evil.ru/x", "https://shop.ru", {"allowlist_enforced": False}))


if __name__ == "__main__":
    unittest.main()
