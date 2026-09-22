"""Реализация хранилища на SQLite (стандартная библиотека, потокобезопасно)."""

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path

from .. import config
from ..models import Clinic, CompetitorOffer, Lead, Tender
from .base import Repository

SCHEMA = """
CREATE TABLE IF NOT EXISTS clinics (
    key TEXT PRIMARY KEY,
    name TEXT, inn TEXT, ogrn TEXT, region TEXT, city TEXT, address TEXT,
    phone TEXT, email TEXT, license_number TEXT, license_issued TEXT,
    registered_at TEXT, activities TEXT, sources TEXT, source_urls TEXT
);
CREATE TABLE IF NOT EXISTS tenders (
    reg_number TEXT PRIMARY KEY,
    title TEXT, customer TEXT, customer_inn TEXT, region TEXT, city TEXT,
    price REAL, published_at TEXT, deadline_at TEXT, okpd2 TEXT, url TEXT,
    matched_categories TEXT
);
CREATE TABLE IF NOT EXISTS competitor_offers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    competitor TEXT, product_name TEXT, category TEXT, brand TEXT,
    price REAL, currency TEXT, region TEXT, url TEXT, captured_at TEXT, promo TEXT,
    UNIQUE(competitor, product_name, captured_at)
);
CREATE TABLE IF NOT EXISTS leads (
    key TEXT PRIMARY KEY,
    name TEXT, region TEXT, city TEXT, score REAL, tier TEXT,
    reasons TEXT, signals TEXT, recommended_categories TEXT,
    recommended_services TEXT, contacts TEXT, sources TEXT
);
CREATE TABLE IF NOT EXISTS run_meta (
    id INTEGER PRIMARY KEY CHECK (id = 1),
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

_CLINIC_COLS = (
    "key", "name", "inn", "ogrn", "region", "city", "address", "phone",
    "email", "license_number", "license_issued", "registered_at",
    "activities", "sources", "source_urls",
)
_TENDER_COLS = (
    "reg_number", "title", "customer", "customer_inn", "region", "city",
    "price", "published_at", "deadline_at", "okpd2", "url", "matched_categories",
)
_OFFER_COLS = (
    "competitor", "product_name", "category", "brand", "price", "currency",
    "region", "url", "captured_at", "promo",
)
_LEAD_COLS = (
    "key", "name", "region", "city", "score", "tier", "reasons",
    "signals", "recommended_categories", "recommended_services", "contacts", "sources",
)
_LEAD_JSON = (
    "reasons", "signals", "recommended_categories",
    "recommended_services", "contacts", "sources",
)


class SQLiteRepository(Repository):
    """Репозиторий на SQLite. Подходит для пилота и одиночного узла."""

    def __init__(self, path: Path | str | None = None) -> None:
        config.RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
        self.path = Path(path) if path else config.DB_PATH
        self._lock = threading.Lock()
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.execute("PRAGMA journal_mode=wal")
        self._migrate()
        self.conn.commit()

    def _migrate(self) -> None:
        """Добавляет колонки, отсутствующие в старой схеме (версирование без ALTER IF EXISTS)."""
        for col_sql in [
            "ALTER TABLE leads ADD COLUMN sources TEXT",
        ]:
            try:
                self.conn.execute(col_sql)
            except sqlite3.OperationalError:
                pass

    # --- низкий уровень ---------------------------------------------------
    def _exec(self, query: str, params: tuple = ()):
        with self._lock:
            return self.conn.execute(query, params)

    def _rows(self, query: str, params: tuple = ()) -> list[dict]:
        with self._lock:
            return [dict(r) for r in self.conn.execute(query, params).fetchall()]

    @staticmethod
    def _dump(row: dict, names: tuple[str, ...]) -> list:
        for name in names:
            if name in row and not isinstance(row[name], str):
                row[name] = json.dumps(row[name], ensure_ascii=False)
        return [row.get(c, "") for c in names]

    @staticmethod
    def _insert(repo: "SQLiteRepository", table: str, cols: tuple[str, ...], row: dict) -> None:
        values = repo._dump(row, cols)
        placeholders = ",".join("?" for _ in cols)
        repo._exec(
            f"INSERT OR REPLACE INTO {table} ({','.join(cols)}) VALUES ({placeholders})",
            values,
        )

    # --- запись -----------------------------------------------------------
    def save_clinic(self, clinic: Clinic) -> None:
        self._insert(self, "clinics", _CLINIC_COLS, clinic.to_dict())

    def save_tender(self, tender: Tender) -> None:
        self._insert(self, "tenders", _TENDER_COLS, tender.to_dict())

    def save_competitor_offer(self, offer: CompetitorOffer) -> None:
        self._insert(self, "competitor_offers", _OFFER_COLS, offer.to_dict())

    def save_lead(self, lead: Lead) -> None:
        self._insert(self, "leads", _LEAD_COLS, lead.to_dict())

    def save_run_meta(self, generated_at: str, version: str, stats: dict) -> None:
        self._exec(
            "INSERT OR REPLACE INTO run_meta (id, generated_at, version, stats) "
            "VALUES (1, ?, ?, ?)",
            (generated_at, version, json.dumps(stats, ensure_ascii=False)),
        )

    def save_source_health(self, metrics: list[dict]) -> None:
        for metric in metrics:
            self._exec(
                "INSERT OR REPLACE INTO source_health "
                "(source, status, records, message, checked_at) VALUES (?, ?, ?, ?, ?)",
                (
                    metric.get("source", ""),
                    metric.get("status", ""),
                    int(metric.get("records", 0)),
                    metric.get("message", ""),
                    metric.get("checked_at", ""),
                ),
            )

    def clear(self) -> None:
        for table in ("clinics", "tenders", "competitor_offers", "leads",
                      "run_meta", "source_health"):
            self._exec(f"DELETE FROM {table}")

    def commit(self) -> None:
        with self._lock:
            self.conn.commit()

    # --- чтение -----------------------------------------------------------
    def leads(self, min_score: float = 0.0) -> list[dict]:
        rows = self._rows(
            "SELECT * FROM leads WHERE score >= ? ORDER BY score DESC", (min_score,)
        )
        for row in rows:
            for name in _LEAD_JSON:
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
        def count(table: str) -> int:
            return int(self._exec(f"SELECT COUNT(*) FROM {table}").fetchone()[0])

        return {
            "clinics": count("clinics"),
            "tenders": count("tenders"),
            "competitor_offers": count("competitor_offers"),
            "leads": count("leads"),
        }

    def close(self) -> None:
        self.conn.close()
