"""Источник: госзакупки 44-ФЗ/223-ФЗ (zakupki.gov.ru).

Live-режим использует официальный RSS поиска закупок. Только открытые данные;
соблюдаются robots.txt и rate limiting. TLS проверяется с российским корневым CA.
"""

from __future__ import annotations

import html
import json
import logging
import re
import urllib.parse
from datetime import datetime

from .. import config
from ..normalize import clean_text
from .base import RawRecord, SourceAdapter

logger = logging.getLogger("medax_radar.zakupki")

_ITEM_RE = re.compile(r"<item>(.*?)</item>", re.DOTALL | re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")

_LABELS = {
    "Наименование объекта закупки:": "title",
    "Начальная цена контракта:": "price",
    "Наименование Заказчика:": "customer",
    "Размещено:": "published_at",
    "Этап размещения:": "stage",
}


def _field(block: str, tag: str) -> str:
    match = re.search(rf"<{tag}>(.*?)</{tag}>", block, re.DOTALL | re.IGNORECASE)
    return html.unescape(match.group(1)).strip() if match else ""


def parse_rss(xml: str) -> list[dict]:
    """Разбирает RSS zakupki в список словарей закупок."""
    results: list[dict] = []
    for block in _ITEM_RE.findall(xml):
        link = _field(block, "link")
        link = link.replace("https://zakupki.gov.ruhttps://zakupki.gov.ru", "https://zakupki.gov.ru")
        link = link.replace("http://zakupki.gov.ruhttp://zakupki.gov.ru", "http://zakupki.gov.ru")
        link = clean_text(link)
        if link.startswith("/epz"):
            link = "https://zakupki.gov.ru" + link

        reg_match = re.search(r"regNumber=(\d+)", link)
        reg_number = reg_match.group(1) if reg_match else ""

        description = html.unescape(_field(block, "description"))
        tokens = [t.strip() for t in _TAG_RE.split(description) if t.strip()]

        values: dict[str, str] = {}
        current: str | None = None
        for token in tokens:
            if token in _LABELS:
                current = _LABELS[token]
                continue
            if current and current not in values:
                values[current] = token
                current = None

        price = _to_price(values.get("price", ""))
        published = _to_iso_date(values.get("published_at", "")) or _to_iso_pubdate(_field(block, "pubDate"))

        title = values.get("title") or _field(block, "title")
        if not reg_number and not title:
            continue

        results.append({
            "reg_number": reg_number or clean_text(title),
            "title": clean_text(title),
            "customer": clean_text(values.get("customer", "")),
            "customer_inn": "",
            "region": "",
            "city": "",
            "price": price,
            "published_at": published,
            "deadline_at": "",
            "okpd2": "",
            "url": link,
        })
    return results


def _to_price(value: str) -> float:
    text = re.sub(r"[^\d.,]", "", str(value))
    text = text.replace(" ", "").replace("\u00a0", "")
    if not text:
        return 0.0
    if "," in text and "." not in text:
        text = text.replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return 0.0


def _to_iso_date(value: str) -> str:
    match = re.search(r"(\d{2})\.(\d{2})\.(\d{4})", value)
    if match:
        day, month, year = match.groups()
        return f"{year}-{month}-{day}"
    return ""


def _to_iso_pubdate(value: str) -> str:
    try:
        dt = datetime.strptime(value, "%a, %d %b %Y %H:%M:%S %Z")
        return dt.date().isoformat()
    except (ValueError, TypeError):
        return ""


class ZakupkiAdapter(SourceAdapter):
    source_key = "zakupki_tenders"

    def fetch(self) -> list[RawRecord]:
        if self.live:
            try:
                return self.fetch_live()
            except Exception as exc:  # noqa: BLE001 - не роняем прогон
                logger.warning("Live-сбор zakupki не удался (%s); демо-данные", exc)
        return self._fetch_sample()

    def _fetch_sample(self) -> list[RawRecord]:
        path = config.SAMPLES_DIR / "tenders.json"
        if not path.exists():
            return []
        with path.open("r", encoding="utf-8") as fh:
            rows = json.load(fh).get("records", [])
        return [RawRecord("tender", self.source_key, row) for row in rows]

    def fetch_live(self) -> list[RawRecord]:
        cfg = config.zakupki_config()
        client = self._build_client(cfg)
        records: list[RawRecord] = []
        seen: set[str] = set()
        for query in cfg.get("queries", []):
            url = self._build_url(cfg, query)
            try:
                xml = client.get(url).text
            except Exception as exc:  # noqa: BLE001
                logger.warning("Запрос zakupki не удался (%s): %s", query, exc)
                continue
            items = parse_rss(xml)[: int(cfg.get("max_items_per_query", 20))]
            logger.info("zakupki «%s»: %d закупок", query, len(items))
            for item in items:
                if item["reg_number"] in seen:
                    continue
                seen.add(item["reg_number"])
                records.append(RawRecord("tender", self.source_key, item))
        return records

    @staticmethod
    def _build_client(cfg: dict):
        from ..net.client import HttpClient
        from ..net.ratelimit import HostRateLimiter
        from ..net.robots import RobotsCache
        from ..net.tls import russian_ssl_context

        ua = config.http_user_agent()
        robots = RobotsCache(fetcher=lambda url: _fetch_text(url, ua), user_agent=ua)
        return HttpClient(
            user_agent=ua,
            robots=robots,
            limiter=HostRateLimiter(rate_per_sec=1.0, burst=1.0),
            retries=2,
            ssl_context=russian_ssl_context(),
        )

    @staticmethod
    def _build_url(cfg: dict, query: str) -> str:
        params = {
            "searchString": query,
            "morphology": "on" if cfg.get("morphology", True) else "off",
        }
        if cfg.get("fz44", True):
            params["fz44"] = "on"
        if cfg.get("fz223", False):
            params["fz223"] = "on"
        return f"{cfg.get('base_url')}?{urllib.parse.urlencode(params)}"


def _fetch_text(url: str, user_agent: str) -> str | None:
    import ssl
    import urllib.request

    from ..net.tls import russian_ssl_context

    try:
        request = urllib.request.Request(url, headers={"User-Agent": user_agent})
        with urllib.request.urlopen(  # noqa: S310
            request, timeout=15, context=russian_ssl_context()
        ) as response:
            return response.read().decode("utf-8", errors="replace")
    except ssl.SSLError:
        return None
    except Exception:  # noqa: BLE001
        return None
