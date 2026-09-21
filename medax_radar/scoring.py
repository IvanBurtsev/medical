"""Скоринг лидов: объяснимая оценка 0..100 + причины."""

from __future__ import annotations

from . import config
from .models import Clinic, Lead, Tender
from .normalize import age_days, clean_text, completeness


def _recency_factor(days: int | None, half_life: float) -> float:
    if days is None:
        return 0.0
    if days < 0:
        days = 0
    return 0.5 ** (days / half_life)


def _tender_signal(clinic: Clinic, tenders: list[Tender]) -> tuple[float, list[Tender]]:
    """Сила тендерной активности в регионе клиники (0..1) + сами тендеры."""
    if not clinic.region:
        return 0.0, []
    half_life = config.scoring_weights().get("tender_activity", {}).get("half_life_days", 45)
    relevant = [t for t in tenders if t.region == clinic.region]
    if not relevant:
        return 0.0, []
    strength = 0.0
    for tender in relevant:
        strength += _recency_factor(age_days(tender.published_at), half_life)
    normalized = min(strength / 3.0, 1.0)
    relevant.sort(key=lambda t: t.published_at, reverse=True)
    return normalized, relevant


def score_lead(
    clinic: Clinic,
    recommended_categories: list[str],
    recommended_services: list[str],
    tenders: list[Tender],
) -> Lead:
    weights = config.scoring_weights()
    reasons: list[str] = []
    signals: list[str] = []
    total = 0.0

    # 1. Свежесть лицензии
    w_license = weights.get("license_recency", {}).get("weight", 30)
    half_life = weights.get("license_recency", {}).get("half_life_days", 120)
    lic_age = age_days(clinic.license_issued) if clinic.license_issued else None
    lic_factor = _recency_factor(lic_age, half_life)
    total += w_license * lic_factor
    if clinic.license_issued:
        if lic_age is not None and lic_age <= 30:
            reasons.append(f"Свежая лицензия ({lic_age} дн. назад) — высокий шанс закупки")
            signals.append("new_license")
        elif lic_factor > 0.1:
            reasons.append(f"Лицензия {clinic.license_issued}")

    # 2. Тендерная активность в регионе
    w_tender = weights.get("tender_activity", {}).get("weight", 25)
    tender_factor, region_tenders = _tender_signal(clinic, tenders)
    total += w_tender * tender_factor
    if region_tenders:
        reasons.append(
            f"Активность госзакупок в регионе: {len(region_tenders)} тендер(ов), "
            f"последний от {region_tenders[0].published_at}"
        )
        signals.append("tender_region")

    # 3. Приоритет региона
    w_region = weights.get("region_priority", {}).get("weight", 20)
    region_factor = config.region_priority(clinic.region) if clinic.region else 0.0
    total += w_region * region_factor
    if region_factor >= 0.8:
        reasons.append(f"Приоритетный регион присутствия MedAX: {clinic.region}")

    # 4. Совпадение с каталогом
    w_fit = weights.get("catalog_fit", {}).get("weight", 15)
    fit_factor = min(len(recommended_categories) / 5.0, 1.0)
    total += w_fit * fit_factor
    if recommended_categories:
        reasons.append(
            "Релевантные категории каталога: " + ", ".join(recommended_categories[:6])
        )
        signals.append("catalog_fit")

    # 5. Полнота данных
    w_complete = weights.get("data_completeness", {}).get("weight", 10)
    comp = completeness(clinic)
    total += w_complete * comp
    if clean_text(clinic.phone) or clean_text(clinic.email):
        signals.append("has_contacts")

    score = round(min(total, 100.0), 1)
    tiers = config.lead_tiers()
    if score >= tiers.get("hot", 75):
        tier = "hot"
    elif score >= tiers.get("warm", 50):
        tier = "warm"
    else:
        tier = "cold"

    return Lead(
        key=clinic.key,
        name=clinic.name,
        region=clinic.region,
        city=clinic.city,
        score=score,
        tier=tier,
        reasons=reasons,
        signals=signals,
        recommended_categories=recommended_categories,
        recommended_services=recommended_services,
        contacts={
            "phone": clinic.phone,
            "email": clinic.email,
        },
    )
