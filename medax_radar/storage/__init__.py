"""Слой хранения: фабрика репозиториев и абстракция.

Бэкенд выбирается переменной окружения ``MEDAX_DB_BACKEND`` (sqlite|postgres)
или явным аргументом. Пайплайн не знает о конкретной реализации.
"""

from __future__ import annotations

import os

from .base import LIST_FIELDS, Repository
from .sqlite import SQLiteRepository
from .postgres import PostgresRepository


def create_repository(backend: str | None = None, **kwargs) -> Repository:
    """Создаёт репозиторий выбранного бэкенда.

    >>> create_repository()                  # SQLite (по умолчанию)
    >>> create_repository("postgres", dsn="postgresql://...")
    """
    backend = (backend or os.environ.get("MEDAX_DB_BACKEND", "sqlite")).lower()
    if backend == "sqlite":
        return SQLiteRepository(**kwargs)
    if backend in ("postgres", "postgresql"):
        return PostgresRepository(**kwargs)
    raise ValueError(f"Неизвестный бэкенд хранилища: {backend!r}")


__all__ = [
    "Repository",
    "LIST_FIELDS",
    "SQLiteRepository",
    "PostgresRepository",
    "create_repository",
]
