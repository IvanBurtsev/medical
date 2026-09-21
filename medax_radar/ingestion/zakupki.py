"""Источник: госзакупки 44-ФЗ/223-ФЗ (zakupki.gov.ru).

В демо используется локальная выборка. Для live-режима см. fetch_live().
"""

from __future__ import annotations

import json
import urllib.request

from .. import config
from .base import RawRecord, SourceAdapter


class ZakupkiAdapter(SourceAdapter):
    source_key = "zakupki_tenders"

    def fetch(self) -> list[RawRecord]:
        path = config.SAMPLES_DIR / "tenders.json"
        if not path.exists():
            return []
        with path.open("r", encoding="utf-8") as fh:
            rows = json.load(fh).get("records", [])
        return [RawRecord("tender", self.source_key, row) for row in rows]

    def fetch_live(self) -> list[RawRecord]:
        """Поиск закупок на медоборудование.

        Реальный контур:
          1. Официальный поиск/выгрузка zakupki.gov.ru (44-ФЗ, 223-ФЗ).
          2. Фильтр по ОКПД2: 26.60.*, 32.50.*, 28.13.14, 31.09.11, 14.12.30.
          3. Извлечение: реестровый номер, заказчик, ИНН, регион, НМЦК,
             даты публикации/окончания, ссылка.
        Демо-окружение работает офлайн, live-режим отключён.
        """
        url = "https://zakupki.gov.ru/"
        try:
            with urllib.request.urlopen(url, timeout=10) as resp:  # noqa: S310
                resp.read(1)
        except Exception as exc:  # pragma: no cover
            raise RuntimeError(f"zakupki.gov.ru недоступен: {exc}") from exc
        raise NotImplementedError(
            "Парсер закупок подключается в продакшене (официальный API/выгрузка)."
        )
