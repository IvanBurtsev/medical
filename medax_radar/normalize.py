"""Нормализация и классификация данных из источников."""

from __future__ import annotations

import re
from datetime import date, datetime, timezone
from typing import Iterable

from . import config

_WS = re.compile(r"\s+")
_QUOTES = re.compile(r"[«»\"']")
_NON_ALNUM = re.compile(r"[^0-9a-zа-яё]+")


def clean_text(value: str | None) -> str:
    if not value:
        return ""
    return _WS.sub(" ", str(value)).strip()


def normalize_name(value: str | None) -> str:
    text = clean_text(value).lower()
    text = _QUOTES.sub("", text)
    text = text.replace("ооо", "").replace("оао", "").replace("зао", "")
    text = text.replace("индивидуальный предприниматель", "").replace("ип", "")
    return clean_text(text)


def slugify(value: str | None) -> str:
    text = normalize_name(value).replace(" ", "_")
    return _NON_ALNUM.sub("_", text).strip("_")


def classify_by_keywords(text: str, entries: Iterable[dict]) -> list[str]:
    """Возвращает список id записей каталога/услуг, чьи ключевые слова найдены."""
    haystack = f" {clean_text(text).lower()} "
    matched: list[str] = []
    for entry in entries:
        for kw in entry.get("keywords", []):
            if kw.lower() in haystack:
                matched.append(entry["id"])
                break
    return matched


def classify_categories(*parts: str) -> list[str]:
    text = " ".join(p for p in parts if p)
    ids = classify_by_keywords(text, config.all_categories())
    return _dedupe_keep_order(ids)


def classify_services(*parts: str) -> list[str]:
    text = " ".join(p for p in parts if p)
    ids = classify_by_keywords(text, config.all_services())
    return _dedupe_keep_order(ids)


def _dedupe_keep_order(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def parse_date(value: str | None) -> date | None:
    if not value:
        return None
    value = clean_text(value)
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(value[: len(fmt) + 2].strip(), fmt).date()
        except ValueError:
            continue
    return None


def age_days(value: str | None) -> int | None:
    parsed = parse_date(value)
    if parsed is None:
        return None
    today = datetime.now(tz=timezone.utc).date()
    return (today - parsed).days


def region_from_address(address: str, fallback: str = "") -> str:
    if fallback:
        return fallback
    text = clean_text(address).lower()
    for region in config.sources_config().get("regions_priority", {}):
        if region == "_default":
            continue
        if region.lower() in text:
            return region
    return fallback or "_unknown"


def completeness(clinic) -> float:
    """Доля заполненных ключевых полей (0..1)."""
    fields = [
        clinic.name,
        clinic.inn,
        clinic.region,
        clinic.city,
        clinic.phone,
        clinic.email,
        clinic.license_number,
    ]
    filled = sum(1 for f in fields if clean_text(f))
    return round(filled / len(fields), 3)
