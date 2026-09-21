"""Тесты сбора каталога MedAX и сравнения цен с конкурентами."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from medax_radar.compare import (  # noqa: E402
    build_report,
    jaccard,
    match_products,
    positioning,
    tokenize,
)
from medax_radar.medax_catalog import parse_catalog_html, parse_price  # noqa: E402

CATALOG_HTML = """
<a href="#" class="btn zayavka-btn" data-product="Стоматологическая установка K3"
   data-price="157&nbsp;000 р." data-url="https://medaxgroup.ru/k3/">Оставить заявку</a>
<div class="section-product-price">По запросу</div>
<a href="#" data-product="Компрессор Mercury 100л"
   data-price="0 р." data-url="https://medaxgroup.ru/comp/">Оставить заявку</a>
"""


class TestMedaxCatalog(unittest.TestCase):
    def test_parse_price(self) -> None:
        self.assertEqual(parse_price("157&nbsp;000 р."), 157000.0)
        self.assertIsNone(parse_price("0 р."))
        self.assertIsNone(parse_price("По запросу"))

    def test_parse_catalog_html(self) -> None:
        products = parse_catalog_html(CATALOG_HTML, "dental_units")
        self.assertEqual(len(products), 1)
        self.assertEqual(products[0]["price"], 157000.0)
        self.assertEqual(products[0]["category"], "dental_units")


class TestCompare(unittest.TestCase):
    def test_tokenize_and_jaccard(self) -> None:
        self.assertEqual(tokenize("Стоматологическая установка Mercury 330"),
                         {"стома", "устан", "mercu", "330"})
        self.assertGreater(jaccard({"a", "b"}, {"a", "b"}), 0.9)
        self.assertEqual(jaccard(set(), {"a"}), 0.0)

    def test_stemming_matches_word_forms(self) -> None:
        self.assertTrue(tokenize("Аспиратор") & tokenize("Аспирационная система"))

    def test_match_same_category(self) -> None:
        ours = [{"name": "Стоматологическая установка Mercury 330", "price": 157000,
                 "category": "dental_units"}]
        theirs = [{"competitor": "K", "product_name": "Стоматологическая установка Basic Line B-200",
                   "price": 200000, "category": "dental_units"}]
        matches = match_products(ours, theirs, threshold=0.2)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["cheaper"], "MedAX")
        self.assertEqual(matches[0]["diff"], -43000)

    def test_no_cross_category_match(self) -> None:
        ours = [{"name": "Компрессор Mercury 70л", "price": 23500, "category": "compressors"}]
        theirs = [{"competitor": "K", "product_name": "Компрессор AirPro 100л",
                   "price": 68000, "category": "dental_units"}]
        self.assertEqual(match_products(ours, theirs), [])

    def test_positioning_and_report(self) -> None:
        ours = [
            {"name": "Компрессор Mercury 70л", "price": 23500, "category": "compressors"},
            {"name": "Компрессор Mercury 100л", "price": 41000, "category": "compressors"},
        ]
        theirs = [{"competitor": "K", "product_name": "Компрессор Mercury 100л",
                   "price": 68000, "category": "compressors"}]
        report = build_report(ours, theirs, threshold=0.1)
        self.assertGreaterEqual(len(report["matches"]), 1)
        self.assertEqual(report["positioning"][0]["category"], "compressors")
        self.assertLess(report["positioning"][0]["delta_pct"], 0)


if __name__ == "__main__":
    unittest.main()
