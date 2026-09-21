"""Базовые тесты пайплайна (stdlib unittest)."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from medax_radar import pipeline  # noqa: E402
from medax_radar.db import Database  # noqa: E402
from medax_radar.dedupe import clinic_key, is_likely_competitor  # noqa: E402
from medax_radar.matching import recommend_for_clinic  # noqa: E402
from medax_radar.models import Clinic  # noqa: E402
from medax_radar.normalize import classify_categories  # noqa: E402


class TestNormalize(unittest.TestCase):
    def test_classify_implantology(self) -> None:
        self.assertIn("implantology", classify_categories("имплантация зубов"))

    def test_classify_xray(self) -> None:
        self.assertIn("xray", classify_categories("рентгенология"))


class TestDedupe(unittest.TestCase):
    def test_key_by_inn(self) -> None:
        self.assertEqual(clinic_key("A", "123", "X"), "inn:123")

    def test_competitor_detection(self) -> None:
        self.assertTrue(is_likely_competitor("ООО МедТехника Юг", "46.46"))
        self.assertFalse(is_likely_competitor("ООО Дентал Плюс", "86.23"))


class TestMatching(unittest.TestCase):
    def test_stomatology_recommends_dental_units(self) -> None:
        clinic = Clinic(key="k", name="Дентал", activities=["стоматология"])
        cats, services = recommend_for_clinic(clinic)
        self.assertIn("dental_units", cats)
        self.assertIn("turnkey_clinic", services)


class TestPipeline(unittest.TestCase):
    def test_full_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Database(path=Path(tmp) / "test_medax.db")
            result = pipeline.run(db, include_competitors=True)
            stats = result["stats"]
            self.assertGreater(stats["clinics"], 0)
            self.assertGreater(stats["tenders"], 0)
            self.assertGreater(stats["competitor_offers"], 0)
            self.assertGreaterEqual(stats["hot"] + stats["warm"], 1)
            leads = db.leads()
            self.assertTrue(all(0 <= lead["score"] <= 100 for lead in leads))
            self.assertTrue(result["health"])
            db.close()


if __name__ == "__main__":
    unittest.main()
