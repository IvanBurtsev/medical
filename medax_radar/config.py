"""Загрузка конфигурации проекта (каталог, источники, веса скоринга)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from functools import lru_cache
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
DATA_DIR = PROJECT_ROOT / "data"
SAMPLES_DIR = DATA_DIR / "samples"
RUNTIME_DIR = PROJECT_ROOT / "runtime"
DB_PATH = RUNTIME_DIR / "medax_radar.db"


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


@lru_cache(maxsize=1)
def catalog() -> dict[str, Any]:
    return _load_json(CONFIG_DIR / "medax_catalog.json")


@lru_cache(maxsize=1)
def sources_config() -> dict[str, Any]:
    return _load_json(CONFIG_DIR / "sources.json")


@lru_cache(maxsize=1)
def competitors_config() -> dict[str, Any]:
    return _load_json(CONFIG_DIR / "competitors.json")


def all_categories() -> list[dict[str, Any]]:
    return list(catalog().get("categories", []))


def all_services() -> list[dict[str, Any]]:
    return list(catalog().get("services", []))


def region_priority(region: str) -> float:
    table = sources_config().get("regions_priority", {})
    return float(table.get(region, table.get("_default", 0.3)))


def scoring_weights() -> dict[str, Any]:
    return sources_config().get("scoring", {})


def lead_tiers() -> dict[str, int]:
    return sources_config().get("lead_tiers", {"hot": 75, "warm": 50, "cold": 0})


def source_enabled(name: str) -> bool:
    return bool(sources_config().get("sources", {}).get(name, {}).get("enabled", False))


def database_backend() -> str:
    return os.environ.get("MEDAX_DB_BACKEND", "sqlite").lower()


def database_url() -> str | None:
    return os.environ.get("MEDAX_DATABASE_URL")


def http_user_agent() -> str:
    return os.environ.get(
        "MEDAX_USER_AGENT",
        "MedAXRadarBot/4.0 (+https://medaxgroup.ru/; compliance@medaxgroup.ru)",
    )


def validate() -> list[str]:
    """Проверяет целостность конфигурации. Возвращает список проблем."""
    problems: list[str] = []

    categories = all_categories()
    services = all_services()
    if not categories:
        problems.append("Каталог пуст: config/medax_catalog.json → categories")
    if not services:
        problems.append("Услуги пусты: config/medax_catalog.json → services")

    for key in ("id", "name", "keywords"):
        for entry in categories + services:
            if key not in entry:
                problems.append(f"Запись каталога без поля {key!r}: {entry!r}")

    ids = [e["id"] for e in categories + services if "id" in e]
    duplicates = {i for i in ids if ids.count(i) > 1}
    if duplicates:
        problems.append(f"Дубли id в каталоге: {sorted(duplicates)}")

    scoring = scoring_weights()
    total_weight = sum(
        float(v.get("weight", 0)) for v in scoring.values() if isinstance(v, dict)
    )
    if scoring and total_weight <= 0:
        problems.append("Суммарный вес скоринга должен быть больше нуля")

    for name, meta in sources_config().get("sources", {}).items():
        if "kind" not in meta:
            problems.append(f"Источник {name} без поля 'kind'")

    return problems
