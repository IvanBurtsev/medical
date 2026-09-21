"""Сбор собственного каталога MedAX (цены) для сравнения с конкурентами.

Парсит карточки medaxgroup.ru: имя и цена лежат в атрибутах
``data-product`` / ``data-price`` / ``data-url`` кнопки заявки.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

from . import config

logger = logging.getLogger("medax_radar.medax_catalog")

_BUTTON_RE = re.compile(
    r'<a\b[^>]*data-product="(?P<name>[^"]*)"[^>]*data-price="(?P<price>[^"]*)"'
    r'[^>]*data-url="(?P<url>[^"]*)"[^>]*>',
    re.IGNORECASE,
)


def parse_price(value: str) -> float | None:
    """'157&nbsp;000 р.' -> 157000.0 ; 'По запросу'/'0 р.' -> None."""
    text = value.replace("&nbsp;", " ").replace("\u00a0", " ")
    digits = re.sub(r"[^\d]", "", text)
    if not digits:
        return None
    price = float(digits)
    return price if price > 0 else None


def parse_catalog_html(html: str, category: str) -> list[dict]:
    """Извлекает товары MedAX из HTML страницы категории."""
    products: list[dict] = []
    seen: set[tuple[str, int]] = set()
    for match in _BUTTON_RE.finditer(html):
        name = re.sub(r"\s+", " ", match.group("name")).strip()
        price = parse_price(match.group("price"))
        if not name or price is None:
            continue
        key = (name.lower(), int(price))
        if key in seen:
            continue
        seen.add(key)
        products.append({
            "name": name,
            "price": price,
            "currency": "RUB",
            "category": category,
            "url": match.group("url").strip(),
        })
    return products


def scrape_catalog(categories: dict[str, str] | None = None, limit: int = 200) -> list[dict]:
    """Живой сбор каталога MedAX по категориям."""
    cfg = config.medax_site_config()
    categories = categories or cfg.get("categories", {})
    from .net.client import HttpClient
    from .net.ratelimit import HostRateLimiter
    from .net.robots import RobotsCache

    ua = config.http_user_agent()
    client = HttpClient(
        user_agent=ua,
        robots=RobotsCache(fetcher=lambda url: _fetch_text(url, ua), user_agent=ua),
        limiter=HostRateLimiter(rate_per_sec=float(cfg.get("rate_limit_per_sec", 1.0)), burst=1),
        retries=2,
    )
    products: list[dict] = []
    for category, url in categories.items():
        try:
            html = client.get(url).text
        except Exception as exc:  # noqa: BLE001
            logger.warning("Категория MedAX недоступна %s: %s", url, exc)
            continue
        found = parse_catalog_html(html, category)
        logger.info("MedAX %s: %d товаров", category, len(found))
        products.extend(found)
        if len(products) >= limit:
            break
    return products


def snapshot(products: list[dict]) -> dict:
    return {
        "generated_at": datetime.now(tz=timezone.utc).isoformat(timespec="seconds"),
        "count": len(products),
        "products": products,
    }


def _fetch_text(url: str, user_agent: str) -> str | None:
    import urllib.request

    try:
        request = urllib.request.Request(url, headers={"User-Agent": user_agent})
        with urllib.request.urlopen(request, timeout=15) as response:  # noqa: S310
            return response.read().decode("utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        return None
