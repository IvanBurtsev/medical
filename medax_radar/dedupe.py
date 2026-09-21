"""Дедупликация и слияние записей о клиниках из разных источников."""

from __future__ import annotations

from .models import Clinic
from .normalize import clean_text, normalize_name, slugify


def clinic_key(name: str, inn: str, region: str) -> str:
    inn = clean_text(inn)
    if inn:
        return f"inn:{inn}"
    return f"name:{slugify(name)}:{slugify(region)}"


def _merge_text(target: str, source: str) -> str:
    if clean_text(target):
        return target
    return source


def merge_clinics(clinics: list[Clinic]) -> list[Clinic]:
    """Сливает дубли по ИНН (или имени+региону), обогащая поля."""
    merged: dict[str, Clinic] = {}
    for clinic in clinics:
        key = clinic.key or clinic_key(clinic.name, clinic.inn, clinic.region)
        clinic.key = key
        if key not in merged:
            merged[key] = clinic
            clinic.activities = sorted(set(clinic.activities))
            continue
        base = merged[key]
        base.name = _merge_text(base.name, clinic.name)
        base.inn = _merge_text(base.inn, clinic.inn)
        base.ogrn = _merge_text(base.ogrn, clinic.ogrn)
        base.region = _merge_text(base.region, clinic.region)
        base.city = _merge_text(base.city, clinic.city)
        base.address = _merge_text(base.address, clinic.address)
        base.phone = _merge_text(base.phone, clinic.phone)
        base.email = _merge_text(base.email, clinic.email)
        base.license_number = _merge_text(base.license_number, clinic.license_number)
        base.license_issued = _merge_text(base.license_issued, clinic.license_issued)
        base.registered_at = _merge_text(base.registered_at, clinic.registered_at)
        base.activities = sorted(set(base.activities) | set(clinic.activities))
        base.sources = sorted(set(base.sources) | set(clinic.sources))
        base.source_urls = sorted(set(base.source_urls) | set(clinic.source_urls))
    return list(merged.values())


def is_likely_competitor(name: str, okved: str = "") -> bool:
    """Грубая эвристика: дистрибьютор медоборудования — не наш лид, а конкурент."""
    lowered = normalize_name(name)
    markers = ("медтехник", "медтех", "медимпорт", "дент депо", "дентал депо",
               "юнидент", "валлекс", "диамед", "медторг", "медицинская техника")
    if any(m in lowered for m in markers):
        return True
    if okved.startswith("46.46"):
        return True
    return False
