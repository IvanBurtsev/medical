"""Доменные модели MedAX Radar.

Все модели — плоские dataclass-структуры, чтобы их можно было легко
сериализовать в JSON и SQLite без внешних зависимостей.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class Clinic:
    """Клиника — потенциальный покупатель оборудования (лид)."""

    key: str
    name: str
    inn: str = ""
    ogrn: str = ""
    region: str = ""
    city: str = ""
    address: str = ""
    phone: str = ""
    email: str = ""
    license_number: str = ""
    license_issued: str = ""
    activities: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    source_urls: list[str] = field(default_factory=list)
    registered_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Tender:
    """Госзакупка на медицинское оборудование."""

    reg_number: str
    title: str
    customer: str = ""
    customer_inn: str = ""
    region: str = ""
    city: str = ""
    price: float = 0.0
    published_at: str = ""
    deadline_at: str = ""
    okpd2: str = ""
    url: str = ""
    matched_categories: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CompetitorOffer:
    """Товарное предложение конкурента-дистрибьютора."""

    competitor: str
    product_name: str
    category: str = ""
    brand: str = ""
    price: float = 0.0
    currency: str = "RUB"
    region: str = ""
    url: str = ""
    captured_at: str = ""
    promo: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Lead:
    """Скорингованный лид: клиника + сигналы + рекомендации."""

    key: str
    name: str
    region: str
    city: str
    score: float
    tier: str
    reasons: list[str] = field(default_factory=list)
    signals: list[str] = field(default_factory=list)
    recommended_categories: list[str] = field(default_factory=list)
    recommended_services: list[str] = field(default_factory=list)
    contacts: dict[str, str] = field(default_factory=dict)
    sources: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
