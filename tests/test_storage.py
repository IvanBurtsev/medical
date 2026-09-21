"""Тесты слоя хранения и фабрики репозиториев."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from medax_radar.models import Clinic, CompetitorOffer, Lead, Tender  # noqa: E402
from medax_radar.storage import SQLiteRepository, create_repository  # noqa: E402


class TestFactory(unittest.TestCase):
    def test_default_is_sqlite(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = create_repository("sqlite", path=Path(tmp) / "factory.db")
            self.assertIsInstance(repo, SQLiteRepository)
            repo.close()

    def test_unknown_backend(self) -> None:
        with self.assertRaises(ValueError):
            create_repository("mysql")

    def test_postgres_requires_driver_or_dsn(self) -> None:
        with self.assertRaises((ImportError, ValueError)):
            create_repository("postgres")


class TestSQLiteRepository(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = SQLiteRepository(path=Path(self._tmp.name) / "storage_test.db")
        self.repo.clear()

    def tearDown(self) -> None:
        self.repo.close()
        self._tmp.cleanup()

    def test_clinic_roundtrip(self) -> None:
        clinic = Clinic(key="inn:1", name="Тест", inn="1",
                        activities=["стоматология"], sources=["fns_companies"])
        self.repo.save_clinic(clinic)
        self.repo.commit()
        rows = self.repo.clinics()
        self.assertEqual(rows[0]["name"], "Тест")
        self.assertEqual(rows[0]["activities"], ["стоматология"])

    def test_lead_json_fields(self) -> None:
        lead = Lead(key="k", name="N", region="R", city="C", score=88.0, tier="hot",
                    reasons=["причина"], signals=["new_license"],
                    recommended_categories=["dental_units"],
                    recommended_services=["turnkey_clinic"],
                    contacts={"phone": "+7"})
        self.repo.save_lead(lead)
        self.repo.commit()
        row = self.repo.leads()[0]
        self.assertEqual(row["reasons"], ["причина"])
        self.assertEqual(row["contacts"]["phone"], "+7")

    def test_leads_sorted_and_filtered(self) -> None:
        for key, score in (("a", 30.0), ("b", 90.0), ("c", 60.0)):
            self.repo.save_lead(Lead(key=key, name=key, region="R", city="C",
                                     score=score, tier="cold"))
        self.repo.commit()
        scores = [row["score"] for row in self.repo.leads(min_score=50)]
        self.assertEqual(scores, [90.0, 60.0])

    def test_tender_and_offer(self) -> None:
        self.repo.save_tender(Tender(reg_number="1", title="Т", region="R",
                                     matched_categories=["xray"]))
        self.repo.save_competitor_offer(CompetitorOffer(
            competitor="K", product_name="P", captured_at="2026-09-01"))
        self.repo.commit()
        self.assertEqual(self.repo.tenders()[0]["matched_categories"], ["xray"])
        self.assertEqual(self.repo.competitor_offers()[0]["competitor"], "K")

    def test_stats(self) -> None:
        self.repo.commit()
        stats = self.repo.stats()
        self.assertEqual(stats["leads"], 0)
        self.assertIn("clinics", stats)


if __name__ == "__main__":
    unittest.main()
