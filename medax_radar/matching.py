"""Матчинг лидов и тендеров с каталогом и услугами MedAX."""

from __future__ import annotations

from .models import Clinic, Tender, CompetitorOffer
from .normalize import classify_categories, classify_services, clean_text

# Подсказки: вид деятельности из лицензии -> категории каталога MedAX.
ACTIVITY_TO_CATEGORIES: dict[str, list[str]] = {
    "стоматолог": ["dental_units", "handpieces", "polymerization", "hygiene", "furniture"],
    "имплантолог": ["implantology", "handpieces", "cad_cam"],
    "ортодонт": ["cad_cam", "dental_units"],
    "ортопедическ": ["cad_cam", "dental_units"],
    "эндодонт": ["endo_perio", "handpieces"],
    "пародонт": ["endo_perio"],
    "гигиен": ["hygiene", "polymerization"],
    "рентгенолог": ["xray", "ct_3d"],
    "томограф": ["ct_3d", "xray"],
    "магнитно-резонанс": ["xray", "ct_3d"],
    "ультразвуков": ["uzi"],
    "анестезиолог": ["anesthesia"],
    "реанимат": ["anesthesia"],
    "хирург": ["anesthesia", "implantology"],
    "физиотерап": [],
    "лабораторн": [],
    "эндоскоп": [],
    "профосмотр": [],
}

# Подсказки: вид деятельности -> услуги MedAX.
ACTIVITY_TO_SERVICES: dict[str, list[str]] = {
    "стоматолог": ["turnkey_clinic", "design", "service_repair", "education", "surgical_templates"],
    "имплантолог": ["surgical_templates", "education", "service_repair"],
    "ортодонт": ["education", "service_repair"],
    "рентгенолог": ["radiation", "design", "service_repair"],
    "томограф": ["radiation", "design"],
    "ультразвуков": ["service_repair"],
    "анестезиолог": ["service_repair", "design"],
    "хирург": ["design", "service_repair", "education"],
}


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def recommend_for_clinic(clinic: Clinic) -> tuple[list[str], list[str]]:
    """Возвращает (категории каталога, услуги), релевантные клинике."""
    activities_text = " ".join(clinic.activities)
    lowered = clean_text(activities_text).lower()

    categories = classify_categories(clinic.name, activities_text)
    services = classify_services(clinic.name, activities_text)

    for marker, cats in ACTIVITY_TO_CATEGORIES.items():
        if marker in lowered:
            categories.extend(cats)
    for marker, svcs in ACTIVITY_TO_SERVICES.items():
        if marker in lowered:
            services.extend(svcs)

    # Любая новая клиника — потенциальный клиент лицензирования/проектирования.
    if clinic.license_number:
        services.extend(["licensing", "design"])

    return _dedupe(categories), _dedupe(services)


def match_tender(tender: Tender) -> list[str]:
    """Определяет категории каталога, релевантные тендеру."""
    return classify_categories(tender.title, tender.okpd2)


def match_competitor_offer(offer: CompetitorOffer) -> list[str]:
    if offer.category:
        return [offer.category]
    return classify_categories(offer.product_name, offer.brand)
