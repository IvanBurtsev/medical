"""Тесты аутентификации дашборда."""

from __future__ import annotations

import base64
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import tempfile  # noqa: E402

from medax_radar.dashboard import (  # noqa: E402
    check_basic_auth,
    export_csv,
    filter_leads,
    filter_tenders,
    parse_filters,
    render_html,
)
from medax_radar.models import Lead, Tender  # noqa: E402
from medax_radar.storage import SQLiteRepository  # noqa: E402


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


class TestFilters(unittest.TestCase):
    def test_parse_filters(self) -> None:
        self.assertEqual(parse_filters("view=leads&tier=hot&q=%D0%9C"), 
                         {"view": "leads", "tier": "hot", "q": "М"})
        self.assertEqual(parse_filters(""), {})

    def test_filter_leads(self) -> None:
        leads = [
            {"name": "Клиника А", "region": "Ставропольский край", "city": "Ставрополь",
             "tier": "hot", "recommended_categories": ["dental_units"],
             "sources": ["zakupki_customers"]},
            {"name": "Клиника Б", "region": "Ростовская область", "city": "Ростов",
             "tier": "cold", "recommended_categories": ["uzi"],
             "sources": ["roszdravnadzor_licenses"]},
        ]
        self.assertEqual(len(filter_leads(leads, {})), 2)
        self.assertEqual(len(filter_leads(leads, {"tier": "hot"})), 1)
        self.assertEqual(len(filter_leads(leads, {"region": "Ростовская область"})), 1)
        self.assertEqual(len(filter_leads(leads, {"q": "клиника а"})), 1)
        self.assertEqual(len(filter_leads(leads, {"category": "uzi"})), 1)
        self.assertEqual(len(filter_leads(leads, {"source": "zakupki_customers"})), 1)
        self.assertEqual(len(filter_leads(leads, {"source": "bogus"})), 0)
        self.assertEqual(len(filter_leads(leads, {"tier": "hot", "region": "Ростовская область"})), 0)

    def test_filter_tenders(self) -> None:
        tenders = [{"title": "Поставка УЗИ", "customer": "ГБУЗ №1", "region": "Ростовская область"}]
        self.assertEqual(len(filter_tenders(tenders, {"q": "узи"})), 1)
        self.assertEqual(len(filter_tenders(tenders, {"region": "Москва"})), 0)


class TestRenderAndExport(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = SQLiteRepository(path=Path(self._tmp.name) / "dash.db")
        self.repo.clear()
        self.repo.save_lead(Lead(key="k1", name="Клиника А", region="Ставропольский край",
                                 city="Ставрополь", score=90, tier="hot",
                                 recommended_categories=["dental_units"], reasons=["тест"],
                                 contacts={"phone": "+7"},
                                 sources=["zakupki_customers"]))
        self.repo.save_tender(Tender(reg_number="1", title="Поставка УЗИ", region="Ростовская область",
                                     customer="ГБУЗ", price=100000, matched_categories=["uzi"]))
        self.repo.commit()

    def tearDown(self) -> None:
        self.repo.close()
        self._tmp.cleanup()

    def test_render_has_tabs_and_filters(self) -> None:
        html_text = render_html(self.repo, {"view": "leads"})
        self.assertIn("tabs", html_text)
        self.assertIn("filters", html_text)
        self.assertIn("Клиника А", html_text)

    def test_export_leads_csv(self) -> None:
        filename, text = export_csv(self.repo, "leads")
        self.assertEqual(filename, "leads.csv")
        self.assertIn("Клиника А", text)
        self.assertIn("score", text.splitlines()[0])

    def test_export_unknown_type(self) -> None:
        with self.assertRaises(ValueError):
            export_csv(self.repo, "bogus")


if __name__ == "__main__":
    unittest.main()
