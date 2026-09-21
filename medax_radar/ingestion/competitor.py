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
import urllib.request
from urllib.parse import urlparse

from .. import config
from ..extract import extract_offers
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
        for site in cfg.get("sites", []):
            if not site.get("enabled"):
                continue
            base_url = site.get("base_url", "")
            for url in site.get("catalog_urls", []):
                if not self._allowed(url, base_url, cfg):
                    logger.warning("Домен вне allowlist, пропуск: %s", url)
                    continue
                try:
                    response = client.get(url)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Не удалось забрать %s: %s", url, exc)
                    continue
                offers = extract_offers(
                    response.text,
                    base_url=url,
                    competitor=clean_text(site.get("name", "")),
                    region=clean_text(site.get("region", "")),
                    captured_at=_today(),
                )
                logger.info("%s: извлечено %d предложений с %s",
                            site.get("name"), len(offers), url)
                for offer in offers:
                    records.append(RawRecord("competitor", self.source_key, offer))
        return records

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
