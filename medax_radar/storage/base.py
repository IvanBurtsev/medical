"""Абстракция хранилища MedAX Radar.

Любая реализация (SQLite, PostgreSQL) обязана реализовать интерфейс
:class:`Repository`. Это позволяет менять бэкенд без изменения пайплайна.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import Clinic, CompetitorOffer, Lead, Tender

#: Поля-списки, которые сериализуются в JSON.
LIST_FIELDS: tuple[str, ...] = (
    "activities",
    "sources",
    "source_urls",
    "matched_categories",
    "reasons",
    "signals",
    "recommended_categories",
    "recommended_services",
    "contacts",
)


class Repository(ABC):
    """Интерфейс хранилища."""

    # --- запись -----------------------------------------------------------
    @abstractmethod
    def save_clinic(self, clinic: Clinic) -> None: ...

    @abstractmethod
    def save_tender(self, tender: Tender) -> None: ...

    @abstractmethod
    def save_competitor_offer(self, offer: CompetitorOffer) -> None: ...

    @abstractmethod
    def save_lead(self, lead: Lead) -> None: ...

    @abstractmethod
    def save_run_meta(self, generated_at: str, version: str, stats: dict) -> None: ...

    @abstractmethod
    def save_source_health(self, metrics: list[dict]) -> None: ...

    @abstractmethod
    def clear(self) -> None: ...

    @abstractmethod
    def commit(self) -> None: ...

    # --- чтение -----------------------------------------------------------
    @abstractmethod
    def leads(self, min_score: float = 0.0) -> list[dict]: ...

    @abstractmethod
    def tenders(self) -> list[dict]: ...

    @abstractmethod
    def competitor_offers(self) -> list[dict]: ...

    @abstractmethod
    def clinics(self) -> list[dict]: ...

    @abstractmethod
    def run_meta(self) -> dict: ...

    @abstractmethod
    def source_health(self) -> list[dict]: ...

    @abstractmethod
    def stats(self) -> dict: ...

    @abstractmethod
    def close(self) -> None: ...
