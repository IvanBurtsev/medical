"""Экспорт отчётов: CSV, JSON и Markdown."""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

from . import config
from .storage import Repository


def _out_dir(out_dir: Path | None = None) -> Path:
    target = Path(out_dir) if out_dir else config.RUNTIME_DIR / "reports"
    target.mkdir(parents=True, exist_ok=True)
    return target


def export_leads_csv(db: Repository, out_dir: Path | None = None) -> Path:
    path = _out_dir(out_dir) / "leads.csv"
    leads = db.leads()
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.writer(fh, delimiter=";")
        writer.writerow([
            "score", "tier", "name", "region", "city", "phone", "email",
            "categories", "services",
        ])
        for lead in leads:
            writer.writerow([
                lead["score"], lead["tier"], lead["name"], lead["region"],
                lead["city"], lead["contacts"].get("phone", ""),
                lead["contacts"].get("email", ""),
                ", ".join(lead["recommended_categories"]),
                ", ".join(lead["recommended_services"]),
            ])
    return path


def export_json(db: Repository, out_dir: Path | None = None) -> Path:
    path = _out_dir(out_dir) / "report.json"
    payload = {
        "generated_at": datetime.now(tz=timezone.utc).isoformat(timespec="seconds"),
        "run": db.run_meta(),
        "stats": db.stats(),
        "leads": db.leads(),
        "tenders": db.tenders(),
        "competitor_offers": db.competitor_offers(),
    }
    if hasattr(db, "source_health"):
        payload["source_health"] = db.source_health()  # type: ignore[attr-defined]
    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    return path


def export_markdown(db: Repository, out_dir: Path | None = None) -> Path:
    path = _out_dir(out_dir) / "report.md"
    meta = db.run_meta()
    leads = db.leads()
    tenders = db.tenders()
    offers = db.competitor_offers()

    lines: list[str] = []
    lines.append("# MedAX Radar — отчёт о рыночных сигналах")
    lines.append("")
    lines.append(f"- Сформирован: {meta.get('generated_at', 'н/д')}")
    lines.append(f"- Версия: {meta.get('version', 'н/д')}")
    stats = meta.get("stats", {})
    lines.append(
        f"- Организаций: {stats.get('clinics', 0)}, "
        f"тендеров: {stats.get('tenders', 0)}, "
        f"лидов: {stats.get('leads', 0)}"
    )
    lines.append("")

    lines.append("## Топ лидов")
    lines.append("")
    lines.append("| Балл | Уровень | Организация | Регион | Категории |")
    lines.append("|---:|---|---|---|---|")
    for lead in leads[:15]:
        lines.append(
            f"| {lead['score']} | {lead['tier']} | {lead['name']} | "
            f"{lead['region']} | {', '.join(lead['recommended_categories'][:4])} |"
        )
    lines.append("")

    lines.append("## Активные тендеры")
    lines.append("")
    lines.append("| Публикация | Регион | НМЦК | Категории | Заказчик |")
    lines.append("|---|---|---:|---|---|")
    for tender in tenders:
        lines.append(
            f"| {tender['published_at']} | {tender['region']} | "
            f"{tender['price']:,.0f} | {', '.join(tender['matched_categories'][:3])} | "
            f"{tender['customer']} |"
        )
    lines.append("")

    if offers:
        lines.append("## Предложения конкурентов (модуль 2)")
        lines.append("")
        lines.append("| Конкурент | Товар | Цена | Регион |")
        lines.append("|---|---|---:|---|")
        for offer in offers:
            lines.append(
                f"| {offer['competitor']} | {offer['product_name']} | "
                f"{offer['price']:,.0f} | {offer['region']} |"
            )
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def export_all(db: Repository, out_dir: Path | None = None) -> list[Path]:
    return [
        export_leads_csv(db, out_dir),
        export_json(db, out_dir),
        export_markdown(db, out_dir),
    ]
