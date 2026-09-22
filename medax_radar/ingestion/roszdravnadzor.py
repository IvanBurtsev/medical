"""Источник: открытые данные Росздравнадзора.

Live-режим скачивает еженедельный ZIP с реестром лицензий (техобслуживание
медицинских изделий) и разбирает XML. Только открытые данные; TLS проверяется
российским корневым сертификатом.
"""

from __future__ import annotations

import io
import json
import logging
import re
import urllib.request
import zipfile
import xml.etree.ElementTree as ET

from .. import config
from ..normalize import clean_text
from .base import RawRecord, SourceAdapter

logger = logging.getLogger("medax_radar.roszdravnadzor")

_DATA_FILE_RE = re.compile(r"data-\d{8}-structure-\d{8}\.zip")


def _text(element: ET.Element, tag: str) -> str:
    node = element.find(tag)
    if node is None or node.text is None:
        return ""
    return clean_text(node.text)


def parse_licenses_xml(xml_text: str, activity: str = "", max_records: int = 0) -> list[dict]:
    """Разбирает XML реестра лицензий в payload-словари клиник."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []
    records: list[dict] = []
    for node in root.iter():
        if node.tag.split("}")[-1] != "licenses":
            continue
        name = _text(node, "abbreviated_name_licensee") or _text(node, "full_name_licensee")
        if not name:
            continue
        city = ""
        place = node.find("work_address_list/address_place")
        if place is not None:
            city = _text(place, "city")
        number = _text(node, "number")
        records.append({
            "name": name,
            "inn": _text(node, "inn"),
            "ogrn": _text(node, "ogrn"),
            "region": _text(node, "address_region"),
            "city": city,
            "address": _text(node, "address"),
            "phone": "",
            "email": "",
            "license_number": number,
            "issued_at": _text(node, "date_register") or _text(node, "date"),
            "activities": [activity] if activity else [],
        })
        if max_records and len(records) >= max_records:
            break
    return records


class RoszdravnadzorAdapter(SourceAdapter):
    source_key = "roszdravnadzor_licenses"

    def fetch(self) -> list[RawRecord]:
        if self.live:
            try:
                return self.fetch_live()
            except Exception as exc:  # noqa: BLE001 - не роняем прогон
                logger.warning("Live-сбор Росздравнадзора не удался (%s); демо-данные", exc)
        return self._fetch_sample()

    def _fetch_sample(self) -> list[RawRecord]:
        path = config.SAMPLES_DIR / "licenses.json"
        if not path.exists():
            return []
        with path.open("r", encoding="utf-8") as fh:
            rows = json.load(fh).get("records", [])
        return [RawRecord("clinic", self.source_key, row) for row in rows]

    def fetch_live(self) -> list[RawRecord]:
        cfg = config.roszdravnadzor_config()
        page_url = cfg["dataset_page"]
        html = self._get_text(page_url)
        files = _DATA_FILE_RE.findall(html)
        if not files:
            raise RuntimeError("Не найдены файлы набора данных Росздравнадзора")
        latest = max(files)  # имя содержит дату data-YYYYMMDD-...
        zip_url = page_url.rstrip("/") + "/" + latest
        logger.info("Росздравнадзор: скачиваю %s", latest)
        raw = self._get_bytes(zip_url)
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            xml_name = next(n for n in archive.namelist() if n.lower().endswith(".xml"))
            xml_text = archive.read(xml_name).decode("utf-8", errors="replace")
        records = parse_licenses_xml(
            xml_text,
            activity=cfg.get("activity", ""),
            max_records=int(cfg.get("max_records", 0)),
        )
        logger.info("Росздравнадзор: %d лицензиатов", len(records))
        for record in records:
            record["source_url"] = zip_url
        return [RawRecord("clinic", self.source_key, record) for record in records]

    @staticmethod
    def _get_text(url: str) -> str:
        from ..net.tls import russian_ssl_context

        request = urllib.request.Request(url, headers={"User-Agent": config.http_user_agent()})
        with urllib.request.urlopen(  # noqa: S310
            request, timeout=60, context=russian_ssl_context()
        ) as response:
            return response.read().decode("utf-8", errors="replace")

    @staticmethod
    def _get_bytes(url: str) -> bytes:
        from ..net.tls import russian_ssl_context

        request = urllib.request.Request(url, headers={"User-Agent": config.http_user_agent()})
        with urllib.request.urlopen(  # noqa: S310
            request, timeout=120, context=russian_ssl_context()
        ) as response:
            return response.read()
