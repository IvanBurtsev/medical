"""Тесты конфигурации и доменной логики."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from medax_radar import config  # noqa: E402
from medax_radar.dedupe import merge_clinics  # noqa: E402
from medax_radar.models import Clinic  # noqa: E402
from medax_radar.normalize import age_days, completeness, parse_date  # noqa: E402
from medax_radar.scoring import score_lead  # noqa: E402


class TestConfig(unittest.TestCase):
    def test_shipped_config_valid(self) -> None:
        self.assertEqual(config.validate(), [])

    def test_region_priority_known_and_default(self) -> None:
        self.assertGreater(config.region_priority("Ставропольский край"), 0.9)
        self.assertEqual(config.region_priority("Антарктида"), 0.3)

    def test_default_backend(self) -> None:
        self.assertEqual(config.database_backend(), "sqlite")


class TestNormalize(unittest.TestCase):
    def test_parse_date_formats(self) -> None:
        self.assertEqual(parse_date("2026-09-21").year, 2026)
        self.assertEqual(parse_date("21.09.2026").month, 9)
        self.assertIsNone(parse_date("не дата"))

    def test_age_days(self) -> None:
        self.assertIsNotNone(age_days("2026-09-20"))
        self.assertIsNone(age_days("пусто"))

    def test_completeness(self) -> None:
        empty = Clinic(key="k", name="N")
        full = Clinic(key="k", name="N", inn="1", region="R", city="C",
                      phone="p", email="e", license_number="L")
        self.assertLess(completeness(empty), completeness(full))


class TestDedupeMerge(unittest.TestCase):
    def test_merge_by_inn_unions_fields(self) -> None:
        a = Clinic(key="inn:1", name="Клиника", inn="1", phone="+7",
                   activities=["стоматология"], sources=["s1"])
        b = Clinic(key="inn:1", name="Клиника", inn="1", email="e@x",
                   activities=["имплантология"], sources=["s2"])
        merged = merge_clinics([a, b])
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0].email, "e@x")
        self.assertEqual(sorted(merged[0].activities),
                         ["имплантология", "стоматология"])
        self.assertEqual(merged[0].sources, ["s1", "s2"])


class TestScoring(unittest.TestCase):
    def test_score_bounds_and_tier(self) -> None:
        clinic = Clinic(key="k", name="N", region="Ставропольский край",
                        license_issued="2026-09-20", phone="+7", email="e",
                        inn="1", city="C", license_number="L",
                        activities=["стоматология"])
        lead = score_lead(clinic, ["dental_units"], ["turnkey_clinic"], [])
        self.assertGreaterEqual(lead.score, 0)
        self.assertLessEqual(lead.score, 100)
        self.assertIn(lead.tier, {"hot", "warm", "cold"})

    def test_new_license_scores_higher(self) -> None:
        base = dict(key="k", name="N", region="R", city="C", phone="+7")
        fresh = Clinic(**base, license_issued="2026-09-20")
        old = Clinic(**base, license_issued="2020-01-01")
        fresh_lead = score_lead(fresh, ["dental_units"], [], [])
        old_lead = score_lead(old, ["dental_units"], [], [])
        self.assertGreater(fresh_lead.score, old_lead.score)


if __name__ == "__main__":
    unittest.main()
