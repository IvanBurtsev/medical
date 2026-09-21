"""Источник: сайты конкурентов-дистрибьюторов (модуль 2).

Собираются только публичные страницы каталога. Обязательно соблюдаются
robots.txt и rate limiting; авторизация/капча не обходятся.

Режимы:
- ``fetch()`` — если включён live (``--live``), идёт на сайты из
  ``config/competitors.json``; при сбое откатывается на демо-выборку.
- ``fetch(sample)`` — синтетические данные ``data/samples/competitors.json``.
"""

from __future__ import annotations

import json
import logging
import re
import urllib.request
from urllib.parse import urlparse

from .. import config
from ..extract import collect_links, extract_offers, parse_sitemap
from ..normalize import clean_text
from .base import RawRecord, SourceAdapter

logger = logging.getLogger("medax_radar.competitor")


class CompetitorAdapter(SourceAdapter):
    source_key = "competitor_sites"

    # --- демо-данные ------------------------------------------------------
    def fetch(self) -> list[RawRecord]:
        if self.live:
            try:
                return self.fetch_live()
            except Exception as exc:  # noqa: BLE001 - не роняем прогон
                logger.warning("Live-сбор конкурентов не удался (%s); демо-данные", exc)
        return self._fetch_sample()

    def _fetch_sample(self) -> list[RawRecord]:
        path = config.SAMPLES_DIR / "competitors.json"
        if not path.exists():
            return []
        with path.open("r", encoding="utf-8") as fh:
            rows = json.load(fh).get("records", [])
        return [RawRecord("competitor", self.source_key, row) for row in rows]

    # --- live-сбор --------------------------------------------------------
    def fetch_live(self) -> list[RawRecord]:
        cfg = config.competitors_config()
        ua = config.http_user_agent()
        client = self._build_client(cfg, ua)
        records: list[RawRecord] = []
        captured = _today()
        for site in cfg.get("sites", []):
            if not site.get("enabled"):
                continue
            name = clean_text(site.get("name", ""))
            region = clean_text(site.get("region", ""))
            base_url = site.get("base_url", "")
            follow = bool(site.get("follow_product_links"))
            pattern = site.get("product_link_pattern")
            max_pages = int(site.get("max_product_pages", 25))

            for url in site.get("catalog_urls", []):
                if not self._allowed(url, base_url, cfg):
                    logger.warning("Домен вне allowlist, пропуск: %s", url)
                    continue
                try:
                    response = client.get(url)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Не удалось забрать %s: %s", url, exc)
                    continue

                offers = extract_offers(response.text, base_url=url,
                                        competitor=name, region=region, captured_at=captured)
                for offer in offers:
                    records.append(RawRecord("competitor", self.source_key, offer))

                if not follow:
                    logger.info("%s: %d предложений с %s", name, len(offers), url)
                    continue

                links = collect_links(
                    response.text, url,
                    pattern=pattern,
                    exclude=site.get("product_link_exclude"),
                    limit=max_pages,
                )
                logger.info("%s: %d предложений со страницы + %d карточек к обходу (%s)",
                            name, len(offers), len(links), url)
                for link in links:
                    if not self._allowed(link, base_url, cfg):
                        continue
                    try:
                        product_page = client.get(link)
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("Карточка недоступна %s: %s", link, exc)
                        continue
                    for offer in extract_offers(
                        product_page.text, base_url=link,
                        competitor=name, region=region, captured_at=captured,
                    ):
                        records.append(RawRecord("competitor", self.source_key, offer))

            self._crawl_sitemaps(
                client, cfg, site, name, region, captured, records,
                pattern=pattern, max_pages=max_pages, base_url=base_url,
            )
        return records

    def _crawl_sitemaps(
        self, client, cfg: dict, site: dict, name: str, region: str,
        captured: str, records: list[RawRecord], pattern: str | None,
        max_pages: int, base_url: str,
    ) -> None:
        sitemaps = site.get("sitemap_urls", [])
        if not sitemaps:
            return
        product_urls: list[str] = []
        for sm_url in sitemaps:
            if not self._allowed(sm_url, base_url, cfg):
                continue
            try:
                xml = client.get(sm_url).text
            except Exception as exc:  # noqa: BLE001
                logger.warning("Sitemap недоступен %s: %s", sm_url, exc)
                continue
            is_index, locs = parse_sitemap(xml)
            if is_index:
                for child in locs[: int(site.get("max_sitemaps", 5))]:
                    if not self._allowed(child, base_url, cfg):
                        continue
                    try:
                        _, child_locs = parse_sitemap(client.get(child).text)
                    except Exception:  # noqa: BLE001
                        continue
                    product_urls.extend(child_locs)
            else:
                product_urls.extend(locs)

        if pattern:
            rx = re.compile(pattern, re.IGNORECASE)
            product_urls = [u for u in product_urls if rx.search(u)]
        product_urls = [u for u in product_urls if "/." not in u]

        logger.info("%s: sitemap дал %d URL, обрабатываю до %d",
                    name, len(product_urls), max_pages)
        for link in product_urls[:max_pages]:
            if not self._allowed(link, base_url, cfg):
                continue
            try:
                page = client.get(link)
            except Exception:  # noqa: BLE001 - битые ссылки пропускаем
                continue
            for offer in extract_offers(
                page.text, base_url=link,
                competitor=name, region=region, captured_at=captured,
            ):
                records.append(RawRecord("competitor", self.source_key, offer))

    @staticmethod
    def _build_client(cfg: dict, ua: str):
        # Импорт внутри функции, чтобы демо-режим не тянул сетевой слой.
        from ..net.client import HttpClient
        from ..net.ratelimit import HostRateLimiter
        from ..net.robots import RobotsCache

        robots = RobotsCache(fetcher=lambda url: _fetch_text(url, ua), user_agent=ua)
        limiter = HostRateLimiter(
            rate_per_sec=float(cfg.get("rate_limit_per_sec", 0.5)), burst=1.0
        )
        return HttpClient(user_agent=ua, robots=robots, limiter=limiter, retries=2)

    @staticmethod
    def _allowed(url: str, base_url: str, cfg: dict) -> bool:
        if not cfg.get("allowlist_enforced", True):
            return True
        host = urlparse(url).netloc.lower()
        base_host = urlparse(base_url).netloc.lower()
        if not base_host:
            return False
        return host == base_host or host.endswith("." + base_host)


def _today() -> str:
    from datetime import datetime, timezone

    return datetime.now(tz=timezone.utc).date().isoformat()


def _fetch_text(url: str, user_agent: str) -> str | None:
    """Забирает текст (например, robots.txt). None при ошибке/недоступности."""
    try:
        request = urllib.request.Request(url, headers={"User-Agent": user_agent})
        with urllib.request.urlopen(request, timeout=15) as response:  # noqa: S310
            return response.read().decode("utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        return None


def scrape_url(url: str, competitor: str, region: str = "") -> list[dict]:
    """Разовый сбор одного публичного URL (для CLI и проверок)."""
    ua = config.http_user_agent()
    cfg = config.competitors_config()
    client = CompetitorAdapter._build_client(cfg, ua)
    response = client.get(url)
    return extract_offers(
        response.text, base_url=url, competitor=competitor,
        region=region, captured_at=_today(),
    )
