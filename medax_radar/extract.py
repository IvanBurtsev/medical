"""Извлечение товарных предложений из HTML публичных страниц.

Порядок стратегий (от надёжной к запасной):
1. JSON-LD (schema.org Product/Offer).
2. Microdata (itemtype=Product, itemprop name/price).
3. Регулярное выражение по цене в тексте.

Без внешних зависимостей — только стандартная библиотека.
"""

from __future__ import annotations

import json
import re
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin, urlparse

_JSONLD_RE = re.compile(
    r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.IGNORECASE | re.DOTALL,
)
_PRICE_RE = re.compile(
    r"(\d[\d \t\u00a0]{2,}(?:[.,]\d{1,2})?)[ \t\u00a0]*(?:₽|руб\.?|rub|р\.)",
    re.IGNORECASE,
)
_BLOCK_RE = re.compile(r"</?(p|div|br|li|tr|h[1-6]|section|article)[^>]*>", re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"[ \t]+")

_PRODUCT_TYPES = {"Product", "IndividualProduct", "ProductModel"}

#: Мусорные «товары» (виджеты лизинга, служебные подписи).
_NOISE_RE = re.compile(
    r"(лизинг|авансов|финансирован|минимальн|рассрочк|сумма\n|сумма |"
    r"trade-?in|доставк|гаранти|скидк|под заказ|нет в продаже|цена по запросу|"
    r"сравнени|добавить в корзину|обратный звонок)",
    re.IGNORECASE,
)

_LINK_RE = re.compile(r'href=["\']([^"\'#]+)["\']', re.IGNORECASE)
_SITEMAP_LOC_RE = re.compile(r"<loc>\s*([^<\s]+)\s*</loc>", re.IGNORECASE)


def parse_sitemap(xml: str) -> tuple[bool, list[str]]:
    """Разбирает sitemap. Возвращает (это_индекс, список_url)."""
    is_index = "<sitemapindex" in xml[:5000].lower()
    return is_index, _SITEMAP_LOC_RE.findall(xml)


def _is_product_type(node_type: Any) -> bool:
    """True, если @type указывает на Product (в т.ч. полным URL schema.org)."""
    types = node_type if isinstance(node_type, list) else [node_type]
    for item in types:
        if not isinstance(item, str):
            continue
        if item.rstrip("/").split("/")[-1].split("#")[-1] in _PRODUCT_TYPES:
            return True
    return False


def strip_tags(html: str) -> str:
    text = _BLOCK_RE.sub("\n", html)
    text = _TAG_RE.sub(" ", text)
    text = _WS_RE.sub(" ", text)
    return "\n".join(line.strip() for line in text.splitlines() if line.strip())


def to_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    text = re.sub(r"[^\d.,]", "", text.replace("\u00a0", "").replace(" ", ""))
    if not text:
        return None
    # 1 234,56 -> 1234.56 ; 1,234.56 -> 1234.56 ; 1999 -> 1999
    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        text = text.replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def _offer_fields(offer: Any) -> tuple[float | None, str, str]:
    """Возвращает (price, currency, url) из блока offers (dict или list)."""
    if isinstance(offer, list):
        for item in offer:
            price, currency, url = _offer_fields(item)
            if price is not None:
                return price, currency, url
        return None, "", ""
    if isinstance(offer, dict):
        price = to_float(offer.get("price") or offer.get("lowPrice") or offer.get("highPrice"))
        currency = str(offer.get("priceCurrency") or "")
        url = str(offer.get("url") or "")
        return price, currency, url
    return None, "", ""


def _walk_jsonld(node: Any, out: list[dict]) -> None:
    if isinstance(node, list):
        for item in node:
            _walk_jsonld(item, out)
    elif isinstance(node, dict):
        if _is_product_type(node.get("@type")):
            name = node.get("name")
            price, currency, url = _offer_fields(node.get("offers"))
            if price is None:
                price = to_float(node.get("price"))
                currency = currency or str(node.get("priceCurrency") or "")
            brand = node.get("brand")
            if isinstance(brand, dict):
                brand = brand.get("name", "")
            if name and price is not None:
                out.append({
                    "product_name": str(name).strip(),
                    "price": price,
                    "currency": currency or "RUB",
                    "url": url or str(node.get("url") or ""),
                    "brand": str(brand or "").strip(),
                    "category_text": str(node.get("category") or ""),
                })
        for value in node.values():
            _walk_jsonld(value, out)


def parse_jsonld(html: str) -> list[dict]:
    results: list[dict] = []
    for match in _JSONLD_RE.finditer(html):
        raw = match.group(1).strip()
        try:
            data = json.loads(raw)
        except (ValueError, TypeError):
            continue
        _walk_jsonld(data, results)
    return results


class _MicrodataParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.products: list[dict] = []
        self._stack: list[dict] = []
        self._capture: str | None = None
        self._buf: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_d = {k: (v or "") for k, v in attrs}
        itemtype = attrs_d.get("itemtype", "")
        if any(t in itemtype for t in _PRODUCT_TYPES):
            self._stack.append({})
        itemprop = attrs_d.get("itemprop")
        if itemprop in ("name", "price", "priceCurrency") and self._stack:
            self._capture = itemprop
            self._buf = []
        if tag in ("meta", "img") and itemprop in ("price", "name") and self._stack:
            content = attrs_d.get("content", "")
            if content:
                self._stack[-1][itemprop] = content

    def handle_data(self, data: str) -> None:
        if self._capture:
            self._buf.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self._capture:
            value = " ".join("".join(self._buf).split())
            if value and self._stack:
                self._stack[-1][self._capture] = value
            self._capture = None
            self._buf = []
        if self._stack and "name" in self._stack[-1] and "price" in self._stack[-1]:
            self.products.append(self._stack[-1])
            self._stack.pop()


def parse_microdata(html: str) -> list[dict]:
    parser = _MicrodataParser()
    try:
        parser.feed(html)
    except Exception:  # noqa: BLE001 - парсер не должен ронять сбор
        pass
    results: list[dict] = []
    for product in parser.products:
        price = to_float(product.get("price"))
        name = product.get("name")
        if name and price is not None:
            results.append({
                "product_name": str(name).strip(),
                "price": price,
                "currency": str(product.get("priceCurrency") or "RUB"),
                "url": "",
                "brand": "",
                "category_text": "",
            })
    return results


def parse_price_regex(html: str) -> list[dict]:
    text = strip_tags(html)
    results: list[dict] = []
    for match in _PRICE_RE.finditer(text):
        price = to_float(match.group(1))
        if price is None or price < 100:
            continue
        context = text[max(0, match.start() - 140):match.start()]
        name = context.splitlines()[-1].strip() if context.strip() else ""
        name = name[-90:].strip(" -–—•\t")
        if len(name) < 3:
            continue
        results.append({
            "product_name": name,
            "price": price,
            "currency": "RUB",
            "url": "",
            "brand": "",
            "category_text": "",
        })
    return results


def extract_offers(
    html: str,
    base_url: str,
    competitor: str,
    region: str = "",
    captured_at: str = "",
) -> list[dict]:
    """Извлекает предложения конкурента из HTML.

    Возвращает список payload-словарей, совместимых с CompetitorOffer.
    """
    candidates = parse_jsonld(html)
    if not candidates:
        candidates = parse_microdata(html)
    if not candidates:
        candidates = parse_price_regex(html)

    offers: list[dict] = []
    seen: set[tuple[str, int]] = set()
    _emit(offers, seen, candidates, base_url, competitor, region, captured_at)
    return offers


def _emit(
    offers: list[dict],
    seen: set[tuple[str, int]],
    candidates: list[dict],
    base_url: str,
    competitor: str,
    region: str,
    captured_at: str,
) -> None:
    for item in candidates:
        name = str(item.get("product_name", "")).strip()
        price = float(item.get("price", 0))
        if not name or price < 100 or _NOISE_RE.search(name):
            continue
        key = (name.lower(), int(price))
        if key in seen:
            continue
        seen.add(key)
        offers.append({
            "competitor": competitor,
            "product_name": name,
            "category": "",
            "brand": str(item.get("brand", "")),
            "price": price,
            "currency": str(item.get("currency", "RUB")) or "RUB",
            "region": region,
            "url": str(item.get("url") or base_url),
            "captured_at": captured_at,
            "promo": "",
        })


def collect_links(
    html: str,
    base_url: str,
    pattern: str | None = None,
    exclude: str | None = None,
    same_host: bool = True,
    limit: int = 100,
) -> list[str]:
    """Собирает ссылки со страницы, отфильтрованные по regex, хосту и exclude."""
    host = urlparse(base_url).netloc.lower()
    rx = re.compile(pattern, re.IGNORECASE) if pattern else None
    rx_exclude = re.compile(exclude, re.IGNORECASE) if exclude else None
    result: list[str] = []
    seen: set[str] = set()
    for raw in _LINK_RE.findall(html):
        url = urljoin(base_url, raw)
        if same_host and urlparse(url).netloc.lower() != host:
            continue
        if rx and not rx.search(url):
            continue
        if rx_exclude and rx_exclude.search(url):
            continue
        if url in seen:
            continue
        seen.add(url)
        result.append(url)
        if len(result) >= limit:
            break
    return result
