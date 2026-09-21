"""Сравнение цен MedAX и конкурентов.

Сопоставление товаров по категории и схожести названий (токены).
Результат: пары «наш товар ↔ конкурент» с разницей цен и позиционирование
по категориям.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from . import config

_TOKEN_RE = re.compile(r"[a-zа-яё0-9]{3,}")
_STOP = {
    "для", "или", "the", "and", "с", "на", "по", "шт", "мм", "см", "мл", "гр",
    "комплект", "набор",
}


def _stem(token: str) -> str:
    """Грубое усечение основы: 'аспиратор'/'аспирационная' -> 'аспи'."""
    return token[:5] if len(token) > 5 else token


def tokenize(name: str) -> set[str]:
    return {
        _stem(t) for t in _TOKEN_RE.findall(name.lower()) if t not in _STOP
    }


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def match_products(
    medax_products: list[dict],
    competitor_offers: list[dict],
    threshold: float = 0.2,
) -> list[dict]:
    """Для каждого товара MedAX находит ближайшее предложение конкурента."""
    matches: list[dict] = []
    for ours in medax_products:
        our_tokens = tokenize(ours["name"])
        best: tuple[float, dict] | None = None
        for offer in competitor_offers:
            if ours.get("category") and offer.get("category") != ours["category"]:
                continue
            score = jaccard(our_tokens, tokenize(offer["product_name"]))
            if score >= threshold and (best is None or score > best[0]):
                best = (score, offer)
        if best is None:
            continue
        score, offer = best
        diff = ours["price"] - offer["price"]
        matches.append({
            "category": ours.get("category", ""),
            "medax_name": ours["name"],
            "medax_price": ours["price"],
            "competitor": offer["competitor"],
            "competitor_name": offer["product_name"],
            "competitor_price": offer["price"],
            "similarity": round(score, 3),
            "diff": round(diff, 2),
            "cheaper": "MedAX" if diff < 0 else ("конкурент" if diff > 0 else "="),
        })
    matches.sort(key=lambda m: abs(m["diff"]), reverse=True)
    return matches


def positioning(matches: list[dict]) -> list[dict]:
    """Агрегирует позиционирование по категориям."""
    by_category: dict[str, list[dict]] = {}
    for match in matches:
        by_category.setdefault(match["category"] or "_", []).append(match)
    result: list[dict] = []
    for category, items in by_category.items():
        our = sum(i["medax_price"] for i in items) / len(items)
        comp = sum(i["competitor_price"] for i in items) / len(items)
        delta = (our - comp) / comp * 100 if comp else 0.0
        result.append({
            "category": category,
            "pairs": len(items),
            "medax_avg": round(our, 2),
            "competitor_avg": round(comp, 2),
            "delta_pct": round(delta, 1),
        })
    result.sort(key=lambda r: r["delta_pct"], reverse=True)
    return result


def build_report(
    medax_products: list[dict],
    competitor_offers: list[dict],
    threshold: float = 0.2,
) -> dict:
    matches = match_products(medax_products, competitor_offers, threshold)
    return {
        "generated_at": datetime.now(tz=timezone.utc).isoformat(timespec="seconds"),
        "medax_products": len(medax_products),
        "competitor_offers": len(competitor_offers),
        "matches": matches,
        "positioning": positioning(matches),
    }


def load_medax_snapshot(path: Path | None = None) -> list[dict]:
    path = path or (config.DATA_DIR / "samples" / "medax_products.json")
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    return list(data.get("products", []))


def render_markdown(report: dict) -> str:
    lines = ["# Сравнение цен MedAX и конкурентов", ""]
    lines.append(f"- Сформировано: {report['generated_at']}")
    lines.append(f"- Товаров MedAX: {report['medax_products']}, "
                 f"предложений конкурентов: {report['competitor_offers']}")
    lines.append(f"- Сопоставлено пар: {len(report['matches'])}")
    lines.append("")

    lines.append("## Позиционирование по категориям")
    lines.append("")
    lines.append("| Категория | Пар | MedAX, ср. | Конкуренты, ср. | Δ, % |")
    lines.append("|---|---:|---:|---:|---:|")
    for row in report["positioning"]:
        lines.append(
            f"| {row['category']} | {row['pairs']} | {row['medax_avg']:,.0f} | "
            f"{row['competitor_avg']:,.0f} | {row['delta_pct']:+.1f} |"
        )
    lines.append("")

    lines.append("## Пары товаров")
    lines.append("")
    lines.append("| Категория | MedAX | ₽ | Конкурент | Конкурент | ₽ | Дешевле |")
    lines.append("|---|---|---:|---|---|---:|---|")
    for match in report["matches"][:40]:
        lines.append(
            f"| {match['category']} | {match['medax_name'][:40]} | "
            f"{match['medax_price']:,.0f} | {match['competitor']} | "
            f"{match['competitor_name'][:35]} | {match['competitor_price']:,.0f} | "
            f"{match['cheaper']} |"
        )
    return "\n".join(lines)
