"""Адаптер локальной демо-выборки (data/samples/*.json)."""

from __future__ import annotations

import json

from .. import config
from .base import RawRecord, SourceAdapter


def _read(filename: str) -> list[dict]:
    path = config.SAMPLES_DIR / filename
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    return list(data.get("records", []))


class SampleAdapter(SourceAdapter):
    """Читает синтетические данные, имитируя несколько источников сразу."""

    source_key = "sample_dataset"

    def fetch(self) -> list[RawRecord]:
        records: list[RawRecord] = []

        for row in _read("licenses.json"):
            records.append(RawRecord("clinic", "roszdravnadzor_licenses", row))

        for row in _read("companies.json"):
            records.append(RawRecord("clinic", "fns_companies", row))

        for row in _read("tenders.json"):
            records.append(RawRecord("tender", "zakupki_tenders", row))

        for row in _read("competitors.json"):
            records.append(RawRecord("competitor", "competitor_sites", row))

        return records
