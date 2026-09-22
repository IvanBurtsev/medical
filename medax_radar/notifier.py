"""Уведомления (Telegram) и дайджест.

Триггерятся ежедневным cron-заданием. Токен и chat_id задаются переменными
окружения ``TELEGRAM_BOT_TOKEN`` и ``TELEGRAM_CHAT_ID``.
"""

from __future__ import annotations

import io
import json
import logging
import os
import urllib.request

logger = logging.getLogger("medax_radar.notifier")


def send_telegram(
    text: str,
    token: str | None = None,
    chat_id: str | None = None,
) -> bool:
    """Отправляет сообщение в Telegram. Возвращает True при успехе."""
    token = token or os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        logger.info("Telegram не настроен: задайте TELEGRAM_BOT_TOKEN и TELEGRAM_CHAT_ID")
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = json.dumps({"chat_id": chat_id, "text": text, "parse_mode": "HTML"}).encode("utf-8")
    try:
        request = urllib.request.Request(url, data=payload,
                                         headers={"Content-Type": "application/json"},
                                         method="POST")
        with urllib.request.urlopen(request, timeout=15) as response:
            return response.status == 200
    except Exception as exc:  # noqa: BLE001
        logger.warning("Telegram send error: %s", exc)
        return False


def build_summary(report: dict) -> str:
    """Собирает текстовый дайджест из отчёта pipeline."""
    stats = report.get("stats", {})
    lines = [
        "<b>MedAX Radar — ежедневный дайджест</b>",
        "",
        f"▸ Лиды: {stats.get('leads', 0)} (HOT {stats.get('hot', 0)} / "
        f"WARM {stats.get('warm', 0)} / COLD {stats.get('cold', 0)})",
        f"▸ Тендеры: {stats.get('tenders', 0)}",
        f"▸ Предложений конкурентов: {stats.get('competitor_offers', 0)}",
        f"▸ Собрано: {report.get('generated_at', '-')}",
    ]
    return "\n".join(lines)


def notify() -> None:
    """Основная функция: собирает данные, формирует дайджест и отправляет."""
    from . import pipeline
    from .storage import create_repository

    repo = create_repository()
    try:
        if repo.stats()["leads"] == 0:
            pipeline.run(repo=repo, include_competitors=True, live=True)
        stats = repo.stats()
        meta = repo.run_meta()
    finally:
        repo.close()

    report = {"stats": stats, "generated_at": meta.get("generated_at", "-")}
    text = build_summary(report)
    ok = send_telegram(text)
    if ok:
        logger.info("Telegram-дайджест отправлен")