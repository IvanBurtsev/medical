"""Тесты парсера открытых данных Росздравнадзора (модуль 1)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from medax_radar.ingestion.roszdravnadzor import parse_licenses_xml  # noqa: E402

XML = """<?xml version="1.0" encoding="utf-8"?>
<licenses_list>
  <licenses>
    <name>Федеральная служба по надзору в сфере здравоохранения</name>
    <activity_type>Техническое обслуживание медицинских изделий</activity_type>
    <full_name_licensee>Общество с ограниченной ответственностью "АМД"</full_name_licensee>
    <abbreviated_name_licensee>ООО "АМД"</abbreviated_name_licensee>
    <address_region>Самарская область</address_region>
    <address>443008, Самарская область, г. Самара, ул. Красных Коммунаров, д. 17</address>
    <ogrn>1146311002310</ogrn>
    <inn>6311151116</inn>
    <work_address_list>
      <address_place>
        <region>Самарская область</region>
        <city>г Самара</city>
      </address_place>
    </work_address_list>
    <number>Л041-01197-63/00000001</number>
    <date_register>2020-01-15</date_register>
  </licenses>
  <licenses>
    <abbreviated_name_licensee>ООО "Второй"</abbreviated_name_licensee>
    <address_region>Ростовская область</address_region>
    <inn>6163000000</inn>
    <number>Л041-01197-61/00000002</number>
    <date_register>2021-03-20</date_register>
  </licenses>
</licenses_list>
"""


class TestParseLicenses(unittest.TestCase):
    def test_parse_all(self) -> None:
        records = parse_licenses_xml(XML, activity="Техническое обслуживание медицинских изделий")
        self.assertEqual(len(records), 2)

    def test_first_fields(self) -> None:
        record = parse_licenses_xml(XML, activity="ТО МИ")[0]
        self.assertEqual(record["name"], 'ООО "АМД"')
        self.assertEqual(record["inn"], "6311151116")
        self.assertEqual(record["ogrn"], "1146311002310")
        self.assertEqual(record["region"], "Самарская область")
        self.assertEqual(record["city"], "г Самара")
        self.assertEqual(record["license_number"], "Л041-01197-63/00000001")
        self.assertEqual(record["activities"], ["ТО МИ"])

    def test_max_records(self) -> None:
        records = parse_licenses_xml(XML, activity="x", max_records=1)
        self.assertEqual(len(records), 1)

    def test_bad_xml(self) -> None:
        self.assertEqual(parse_licenses_xml("not xml", activity="x"), [])


if __name__ == "__main__":
    unittest.main()
