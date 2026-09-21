"""Базовые типы для адаптеров источников."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class RawRecord:
    """Сырая запись источника.

    type: "clinic" | "tender" | "competitor"
    """

    type: str
    source: str
    payload: dict[str, Any] = field(default_factory=dict)


class SourceAdapter(ABC):
    """Интерфейс адаптера источника данных."""

    #: ключ источника (совпадает с config/sources.json)
    source_key: str = ""
    #: true — тянет данные из сети, false — из локальной выборки
    live: bool = False

    def __init__(self, live: bool = False) -> None:
        self.live = live

    @property
    def name(self) -> str:
        return self.source_key

    @abstractmethod
    def fetch(self) -> list[RawRecord]:
        """Возвращает список сырых записей."""

    def fetch_live(self) -> list[RawRecord]:
        """Забор из реального источника. По умолчанию не поддержан."""
        raise NotImplementedError(
            f"Live-режим для источника {self.source_key or type(self).__name__} "
            f"не реализован в демо. Используйте sample-выборку или включите "
            f"адаптер после настройки доступа."
        )
