"""Источник: регистрация ЮЛ (ФНС/ЕГРЮЛ) — сигнал появления новых клиник.

В демо используется локальная выборка. Для live-режима см. fetch_live().
"""

from __future__ import annotations

import json
import urllib.request

from .. import config
from .base import RawRecord, SourceAdapter


class FnsAdapter(SourceAdapter):
    source_key = "fns_companies"

    def fetch(self) -> list[RawRecord]:
        path = config.SAMPLES_DIR / "companies.json"
        if not path.exists():
            return []
        with path.open("r", encoding="utf-8") as fh:
            rows = json.load(fh).get("records", [])
        return [RawRecord("clinic", self.source_key, row) for row in rows]

    def fetch_live(self) -> list[RawRecord]:
        """Поиск новых ЮЛ по ОКВЭД 86.x / 47.73.

        Реальный контур:
          1. Открытые данные ФНС (ЕГРЮЛ/ЕГРИП) — датасет регистраций.
          2. Фильтр по ОКВЭД: 86.21/86.22/86.23 (медицина), 47.73 (аптеки).
          3. Отсечение конкурентов (дистрибьюторов, ОКВЭД 46.46).
        Демо-окружение работает офлайн, live-режим отключён.
        """
        url = "https://egrul.nalog.ru/"
        try:
            with urllib.request.urlopen(url, timeout=10) as resp:  # noqa: S310
                resp.read(1)
        except Exception as exc:  # pragma: no cover
            raise RuntimeError(f"ФНС недоступна: {exc}") from exc
        raise NotImplementedError(
            "Парсер открытых данных ФНС подключается в продакшене."
        )
