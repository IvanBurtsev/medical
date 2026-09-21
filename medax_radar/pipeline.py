"""Пайплайн: ingestion -> нормализация -> дедупликация -> матчинг -> скоринг.

Слой не зависит от конкретного хранилища (см. medax_radar.storage).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from . import __version__, config
from .dedupe import clinic_key, is_likely_competitor, merge_clinics
from .ingestion import ADAPTERS
from .matching import match_competitor_offer, match_tender, recommend_for_clinic
from .models import Clinic, CompetitorOffer, Tender
from .normalize import (
    clean_text,
    region_from_address,
)
from .scoring import score_lead
from .storage import Repository, create_repository

logger = logging.getLogger("medax_radar.pipeline")

OKVED_TO_ACTIVITIES = {
    "86.23": ["стоматология"],
    "86.21": ["терапия"],
    "86.22": ["специализированная медицинская помощь"],
    "86.90": ["прочие медицинские услуги"],
}


def _now() -> str:
    return datetime.now(tz=timezone.utc).isoformat(timespec="seconds")


def _clinic_from_license(payload: dict[str, Any]) -> Clinic:
    region = region_from_address(payload.get("address", ""), payload.get("region", ""))
    name = clean_text(payload.get("name"))
    return Clinic(
        key=clinic_key(name, payload.get("inn", ""), region),
        name=name,
        inn=clean_text(payload.get("inn")),
        ogrn=clean_text(payload.get("ogrn")),
        region=region,
        city=clean_text(payload.get("city")),
        address=clean_text(payload.get("address")),
        phone=clean_text(payload.get("phone")),
        email=clean_text(payload.get("email")),
        license_number=clean_text(payload.get("license_number")),
        license_issued=clean_text(payload.get("issued_at")),
        activities=list(payload.get("activities", [])),
        sources=["roszdravnadzor_licenses"],
        source_urls=[payload.get("source_url", "")],
    )


def _clinic_from_company(payload: dict[str, Any]) -> Clinic:
    name = clean_text(payload.get("name"))
    region = payload.get("region", "")
    okved = clean_text(payload.get("okved"))
    return Clinic(
        key=clinic_key(name, payload.get("inn", ""), region),
        name=name,
        inn=clean_text(payload.get("inn")),
        ogrn=clean_text(payload.get("ogrn")),
        region=region,
        city=clean_text(payload.get("city")),
        registered_at=clean_text(payload.get("registered_at")),
        activities=OKVED_TO_ACTIVITIES.get(okved, []),
        sources=["fns_companies"],
        source_urls=["https://egrul.nalog.ru/"],
    )


def _tender_from_payload(payload: dict[str, Any]) -> Tender:
    tender = Tender(
        reg_number=clean_text(payload.get("reg_number")),
        title=clean_text(payload.get("title")),
        customer=clean_text(payload.get("customer")),
        customer_inn=clean_text(payload.get("customer_inn")),
        region=clean_text(payload.get("region")),
        city=clean_text(payload.get("city")),
        price=float(payload.get("price") or 0),
        published_at=clean_text(payload.get("published_at")),
        deadline_at=clean_text(payload.get("deadline_at")),
        okpd2=clean_text(payload.get("okpd2")),
        url=clean_text(payload.get("url")),
    )
    tender.matched_categories = match_tender(tender)
    return tender


def _offer_from_payload(payload: dict[str, Any]) -> CompetitorOffer:
    offer = CompetitorOffer(
        competitor=clean_text(payload.get("competitor")),
        product_name=clean_text(payload.get("product_name")),
        category=clean_text(payload.get("category")),
        brand=clean_text(payload.get("brand")),
        price=float(payload.get("price") or 0),
        currency=clean_text(payload.get("currency")) or "RUB",
        region=clean_text(payload.get("region")),
        url=clean_text(payload.get("url")),
        captured_at=clean_text(payload.get("captured_at")),
        promo=clean_text(payload.get("promo")),
    )
    offer.category = (match_competitor_offer(offer) or [""])[0]
    return offer


def _collect(include_competitors: bool) -> tuple[list[Clinic], list[Tender],
                                                 list[CompetitorOffer], int, list[dict]]:
    clinics_raw: list[Clinic] = []
    tenders: list[Tender] = []
    offers: list[CompetitorOffer] = []
    skipped = 0
    health: list[dict] = []

    for source_key, adapter_cls in ADAPTERS.items():
        enabled = config.source_enabled(source_key)
        if source_key == "competitor_sites" and include_competitors:
            enabled = True
        if not enabled:
            logger.info("Источник %s выключен", source_key)
            health.append({
                "source": source_key, "status": "skipped", "records": 0,
                "message": "выключен в config/sources.json", "checked_at": _now(),
            })
            continue

        try:
            records = adapter_cls().fetch()
        except Exception as exc:  # noqa: BLE001 - фиксируем сбой источника
            logger.warning("Источник %s упал: %s", source_key, exc)
            health.append({
                "source": source_key, "status": "error", "records": 0,
                "message": str(exc), "checked_at": _now(),
            })
            continue

        logger.info("Источник %s: %d записей", source_key, len(records))
        health.append({
            "source": source_key, "status": "ok", "records": len(records),
            "message": "", "checked_at": _now(),
        })

        for record in records:
            if record.type == "clinic":
                candidate = (
                    _clinic_from_license(record.payload)
                    if record.source == "roszdravnadzor_licenses"
                    else _clinic_from_company(record.payload)
                )
                if is_likely_competitor(candidate.name, record.payload.get("okved", "")):
                    skipped += 1
                    continue
                clinics_raw.append(candidate)
            elif record.type == "tender":
                tenders.append(_tender_from_payload(record.payload))
            elif record.type == "competitor":
                offers.append(_offer_from_payload(record.payload))

    return clinics_raw, tenders, offers, skipped, health


def run(
    repo: Repository | None = None,
    include_competitors: bool = False,
    reset: bool = True,
    verbose: bool = False,
) -> dict[str, Any]:
    """Выполняет полный цикл и возвращает сводку.

    :param repo: репозиторий; по умолчанию создаётся фабрикой.
    :param include_competitors: включить модуль 2 (парсинг конкурентов).
    :param reset: очищать ли хранилище перед прогоном (для идемпотентности — False).
    """
    if verbose and not logging.getLogger().handlers:
        logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    own_repo = repo is None
    repo = repo or create_repository()
    if reset:
        repo.clear()

    clinics_raw, tenders, offers, skipped, health = _collect(include_competitors)
    clinics = merge_clinics(clinics_raw)
    logger.info("Дедупликация: %d -> %d", len(clinics_raw), len(clinics))

    active_tenders = [t for t in tenders if t.matched_categories]
    logger.info("Тендеров сопоставлено с каталогом: %d", len(active_tenders))

    leads = []
    for clinic in clinics:
        categories, services = recommend_for_clinic(clinic)
        leads.append(score_lead(clinic, categories, services, tenders))
        repo.save_clinic(clinic)
    for tender in tenders:
        repo.save_tender(tender)
    for offer in offers:
        repo.save_competitor_offer(offer)
    for lead in leads:
        repo.save_lead(lead)

    repo.save_source_health(health)

    generated_at = _now()
    stats = {
        "clinics": len(clinics),
        "tenders": len(tenders),
        "tenders_matched": len(active_tenders),
        "competitor_offers": len(offers),
        "leads": len(leads),
        "skipped_competitors": skipped,
        "hot": sum(1 for x in leads if x.tier == "hot"),
        "warm": sum(1 for x in leads if x.tier == "warm"),
        "cold": sum(1 for x in leads if x.tier == "cold"),
    }
    repo.save_run_meta(generated_at, __version__, stats)
    repo.commit()

    if own_repo:
        repo.close()

    return {"generated_at": generated_at, "version": __version__,
            "stats": stats, "health": health}
