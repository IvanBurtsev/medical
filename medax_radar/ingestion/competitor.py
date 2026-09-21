"""Источник: сайты конкурентов-дистрибьюторов (модуль 2, по умолчанию выключен).

Высокий юридический риск: включать только после юридического заключения
и с соблюдением robots.txt / rate limiting. В демо — локальная выборка.
"""

from __future__ import annotations

import json

from .. import config
from .base import RawRecord, SourceAdapter


class CompetitorAdapter(SourceAdapter):
    source_key = "competitor_sites"

    def fetch(self) -> list[RawRecord]:
        path = config.SAMPLES_DIR / "competitors.json"
        if not path.exists():
            return []
        with path.open("r", encoding="utf-8") as fh:
            rows = json.load(fh).get("records", [])
        return [RawRecord("competitor", self.source_key, row) for row in rows]

    def fetch_live(self) -> list[RawRecord]:
        raise NotImplementedError(
            "Live-парсинг сайтов конкурентов включается только после "
            "юридического заключения и настройки robots.txt / rate limiting."
        )
