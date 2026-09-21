"""Обратная совместимость: старое имя ``Database`` → ``SQLiteRepository``.

Новый код должен использовать ``medax_radar.storage.create_repository``.
"""

from __future__ import annotations

from .storage import SQLiteRepository as Database

__all__ = ["Database"]
