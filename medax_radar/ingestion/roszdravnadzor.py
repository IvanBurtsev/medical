"""Источник: реестр лицензий Росздравнадзора (открытые данные).

В демо используется локальная выборка. Для live-режима см. fetch_live().
"""

from __future__ import annotations

import json
import urllib.request

from .. import config
from .base import RawRecord, SourceAdapter


class RoszdravnadzorAdapter(SourceAdapter):
    source_key = "roszdravnadzor_licenses"

    def fetch(self) -> list[RawRecord]:
        path = config.SAMPLES_DIR / "licenses.json"
        if not path.exists():
            return []
        with path.open("r", encoding="utf-8") as fh:
            rows = json.load(fh).get("records", [])
        return [RawRecord("clinic", self.source_key, row) for row in rows]

    def fetch_live(self) -> list[RawRecord]:
        """Забор из открытого API портала Росздравнадзора.

        Реальный контур (для продакшена):
          1. Скачать датасет лицензий на мед. деятельность с
             https://roszdravnadzor.gov.ru/opendata (формат CSV/XML).
          2. Распарсить поля: номер лицензии, дата, лицензиат, ИНН, адрес,
             виды медицинской деятельности.
          3. Фильтровать по дате выдачи (последние N дней) и региону.
        Демо-окружение работает офлайн, поэтому live-режим отключён.
        """
        url = "https://roszdravnadzor.gov.ru/opendata"
        try:
            with urllib.request.urlopen(url, timeout=10) as resp:  # noqa: S310
                resp.read(1)
        except Exception as exc:  # pragma: no cover - зависит от сети
            raise RuntimeError(f"Росздравнадзор недоступен: {exc}") from exc
        raise NotImplementedError(
            "Парсер формата открытых данных Росздравнадзора подключается "
            "в продакшене (нужен доступ к полному датасету)."
        )
