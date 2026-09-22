"""Реализация хранилища на PostgreSQL (опциональная, для продакшена).

Требует установленного драйвера ``psycopg`` (psycopg[binary] или psycopg2).
Пока драйвер не установлен, импорт модуля безопасен, а создание репозитория
завершается понятной ошибкой. SQL написан переносимо и совместим с psycopg3.
"""

from __future__ import annotations

import json
from typing import Any

from ..models import Clinic, CompetitorOffer, Lead, Tender
from .base import Repository

DDL = """
CREATE TABLE IF NOT EXISTS clinics (
    key TEXT PRIMARY KEY,
    name TEXT, inn TEXT, ogrn TEXT, region TEXT, city TEXT, address TEXT,
    phone TEXT, email TEXT, license_number TEXT, license_issued TEXT,
    registered_at TEXT, activities TEXT, sources TEXT, source_urls TEXT
);
CREATE TABLE IF NOT EXISTS tenders (
    reg_number TEXT PRIMARY KEY,
    title TEXT, customer TEXT, customer_inn TEXT, region TEXT, city TEXT,
    price DOUBLE PRECISION, published_at TEXT, deadline_at TEXT, okpd2 TEXT,
    url TEXT, matched_categories TEXT
);
CREATE TABLE IF NOT EXISTS competitor_offers (
    id BIGSERIAL PRIMARY KEY,
    competitor TEXT, product_name TEXT, category TEXT, brand TEXT,
    price DOUBLE PRECISION, currency TEXT, region TEXT, url TEXT,
    captured_at TEXT, promo TEXT,
    UNIQUE(competitor, product_name, captured_at)
);
CREATE TABLE IF NOT EXISTS leads (
    key TEXT PRIMARY KEY,
    name TEXT, region TEXT, city TEXT, score DOUBLE PRECISION, tier TEXT,
    reasons TEXT, signals TEXT, recommended_categories TEXT,
    recommended_services TEXT, contacts TEXT, sources TEXT
);
CREATE TABLE IF NOT EXISTS run_meta (
    id INTEGER PRIMARY KEY,
    generated_at TEXT, version TEXT, stats TEXT
);
CREATE TABLE IF NOT EXISTS source_health (
    source TEXT PRIMARY KEY,
    status TEXT, records INTEGER, message TEXT, checked_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_leads_score ON leads(score DESC);
CREATE INDEX IF NOT EXISTS idx_tenders_region ON tenders(region);
CREATE INDEX IF NOT EXISTS idx_clinics_region ON clinics(region);
"""

_COLS: dict[str, tuple[str, ...]] = {
    "clinics": (
        "key", "name", "inn", "ogrn", "region", "city", "address", "phone",
        "email", "license_number", "license_issued", "registered_at",
        "activities", "sources", "source_urls",
    ),
    "tenders": (
        "reg_number", "title", "customer", "customer_inn", "region", "city",
        "price", "published_at", "deadline_at", "okpd2", "url", "matched_categories",
    ),
    "competitor_offers": (
        "competitor", "product_name", "category", "brand", "price", "currency",
        "region", "url", "captured_at", "promo",
    ),
    "leads": (
        "key", "name", "region", "city", "score", "tier", "reasons",
        "signals", "recommended_categories", "recommended_services", "contacts", "sources",
    ),
}

_LIST_FIELDS = {
    "activities", "sources", "source_urls", "matched_categories",
    "reasons", "signals", "recommended_categories", "recommended_services",
    "contacts",
}


def _import_driver() -> Any:
    try:
        import psycopg  # type: ignore
        return psycopg
    except ImportError:
        try:
            import psycopg2 as psycopg  # type: ignore
            return psycopg
        except ImportError as exc:  # pragma: no cover
            raise ImportError(
                "Для backend='postgres' установите драйвер: pip install 'psycopg[binary]'"
            ) from exc


class PostgresRepository(Repository):
    """Репозиторий на PostgreSQL."""

    def __init__(self, dsn: str | None = None) -> None:
        from .. import config

        driver = _import_driver()
        dsn = dsn or config.database_url()
        if not dsn:
            raise ValueError(
                "Не задан DSN PostgreSQL (параметр dsn или переменная MEDAX_DATABASE_URL)."
            )
        self._driver = driver
        self.conn = driver.connect(dsn)
        self.conn.autocommit = False
        self._init_schema()

    def _init_schema(self) -> None:
        with self.conn.cursor() as cur:
            cur.execute(DDL)
        self.conn.commit()

    @staticmethod
    def _dump(row: dict, names: tuple[str, ...]) -> list:
        for name in names:
            if name in row and not isinstance(row[name], str):
                row[name] = json.dumps(row[name], ensure_ascii=False)
        return [row.get(c) for c in names]

    def _upsert(self, table: str, row: dict, conflict: str) -> None:
        cols = _COLS[table]
        values = self._dump(row, cols)
        placeholders = ",".join("%s" for _ in cols)
        updates = ",".join(f"{c}=EXCLUDED.{c}" for c in cols if c != conflict)
        sql = (
            f"INSERT INTO {table} ({','.join(cols)}) VALUES ({placeholders}) "
            f"ON CONFLICT ({conflict}) DO UPDATE SET {updates}"
        )
        with self.conn.cursor() as cur:
            cur.execute(sql, values)

    def save_clinic(self, clinic: Clinic) -> None:
        self._upsert("clinics", clinic.to_dict(), "key")

    def save_tender(self, tender: Tender) -> None:
        self._upsert("tenders", tender.to_dict(), "reg_number")

    def save_competitor_offer(self, offer: CompetitorOffer) -> None:
        row = offer.to_dict()
        cols = _COLS["competitor_offers"]
        values = self._dump(row, cols)
        placeholders = ",".join("%s" for _ in cols)
        sql = (
            f"INSERT INTO competitor_offers ({','.join(cols)}) "
            f"VALUES ({placeholders}) "
            f"ON CONFLICT (competitor, product_name, captured_at) DO UPDATE SET "
            f"price=EXCLUDED.price, promo=EXCLUDED.promo, category=EXCLUDED.category"
        )
        with self.conn.cursor() as cur:
            cur.execute(sql, values)

    def save_lead(self, lead: Lead) -> None:
        self._upsert("leads", lead.to_dict(), "key")

    def save_run_meta(self, generated_at: str, version: str, stats: dict) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                "INSERT INTO run_meta (id, generated_at, version, stats) "
                "VALUES (1, %s, %s, %s) "
                "ON CONFLICT (id) DO UPDATE SET generated_at=EXCLUDED.generated_at, "
                "version=EXCLUDED.version, stats=EXCLUDED.stats",
                (generated_at, version, json.dumps(stats, ensure_ascii=False)),
            )

    def save_source_health(self, metrics: list[dict]) -> None:
        with self.conn.cursor() as cur:
            for metric in metrics:
                cur.execute(
                    "INSERT INTO source_health (source, status, records, message, checked_at) "
                    "VALUES (%s, %s, %s, %s, %s) "
                    "ON CONFLICT (source) DO UPDATE SET status=EXCLUDED.status, "
                    "records=EXCLUDED.records, message=EXCLUDED.message, "
                    "checked_at=EXCLUDED.checked_at",
                    (
                        metric.get("source", ""),
                        metric.get("status", ""),
                        int(metric.get("records", 0)),
                        metric.get("message", ""),
                        metric.get("checked_at", ""),
                    ),
                )

    def clear(self) -> None:
        with self.conn.cursor() as cur:
            for table in ("clinics", "tenders", "competitor_offers", "leads",
                          "run_meta", "source_health"):
                cur.execute(f"DELETE FROM {table}")

    def commit(self) -> None:
        self.conn.commit()

    def _rows(self, query: str, params: tuple = ()) -> list[dict]:
        with self.conn.cursor() as cur:
            cur.execute(query, params)
            columns = [d[0] for d in cur.description]
            return [dict(zip(columns, r)) for r in cur.fetchall()]

    def leads(self, min_score: float = 0.0) -> list[dict]:
        rows = self._rows(
            "SELECT * FROM leads WHERE score >= %s ORDER BY score DESC", (min_score,)
        )
        for row in rows:
            for name in _LIST_FIELDS:
                if name in row:
                    row[name] = json.loads(row.get(name) or "[]")
        return rows

    def tenders(self) -> list[dict]:
        rows = self._rows("SELECT * FROM tenders ORDER BY published_at DESC")
        for row in rows:
            row["matched_categories"] = json.loads(row.get("matched_categories") or "[]")
        return rows

    def competitor_offers(self) -> list[dict]:
        return self._rows(
            "SELECT * FROM competitor_offers ORDER BY captured_at DESC, competitor"
        )

    def clinics(self) -> list[dict]:
        rows = self._rows("SELECT * FROM clinics ORDER BY name")
        for row in rows:
            for name in ("activities", "sources", "source_urls"):
                row[name] = json.loads(row.get(name) or "[]")
        return rows

    def run_meta(self) -> dict:
        rows = self._rows("SELECT * FROM run_meta WHERE id = 1")
        if not rows:
            return {}
        row = rows[0]
        row["stats"] = json.loads(row.get("stats") or "{}")
        return row

    def source_health(self) -> list[dict]:
        return self._rows("SELECT * FROM source_health ORDER BY source")

    def stats(self) -> dict:
        with self.conn.cursor() as cur:
            result = {}
            for table in ("clinics", "tenders", "competitor_offers", "leads"):
                cur.execute(f"SELECT COUNT(*) FROM {table}")
                result[table] = int(cur.fetchone()[0])
        return result

    def close(self) -> None:
        self.conn.close()
