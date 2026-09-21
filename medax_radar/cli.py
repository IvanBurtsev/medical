"""CLI MedAX Radar."""

from __future__ import annotations

import argparse
import os
import sys

from . import __version__
from . import config
from . import pipeline
from . import report
from .storage import Repository, create_repository


TIER_LABEL = {"hot": "HOT", "warm": "WARM", "cold": "cold"}


def _print_summary(result: dict) -> None:
    stats = result["stats"]
    print("=" * 62)
    print(f" MedAX Radar v{result['version']}  •  {result['generated_at']}")
    print("=" * 62)
    print(f"  Организаций:        {stats['clinics']}")
    print(f"  Тендеров:           {stats['tenders']} (релевантных: {stats['tenders_matched']})")
    print(f"  Лидов:              {stats['leads']}")
    print(f"    HOT:  {stats['hot']}   WARM: {stats['warm']}   COLD: {stats['cold']}")
    print(f"  Предложений конкурентов: {stats['competitor_offers']}")
    print(f"  Отсеяно конкурентов:     {stats['skipped_competitors']}")
    print("=" * 62)


def _print_leads(db: Repository, limit: int = 10) -> None:
    leads = db.leads()
    print(f"\nТоп-{min(limit, len(leads))} лидов:\n")
    for i, lead in enumerate(leads[:limit], 1):
        print(f"{i:>2}. [{TIER_LABEL.get(lead['tier'], lead['tier'])} {lead['score']:>5}] "
              f"{lead['name']} — {lead['city']}, {lead['region']}")
        if lead["recommended_categories"]:
            print(f"     Категории: {', '.join(lead['recommended_categories'][:6])}")
        for reason in lead["reasons"][:2]:
            print(f"     - {reason}")
    print()


def cmd_run(args: argparse.Namespace) -> int:
    db = create_repository()
    result = pipeline.run(
        repo=db,
        include_competitors=args.competitors,
        reset=not args.no_reset,
        verbose=args.verbose,
    )
    _print_summary(result)
    if not args.no_leads:
        _print_leads(db, limit=args.limit)
    if args.export:
        paths = report.export_all(db)
        print("Отчёты:")
        for path in paths:
            print(f"  - {path}")
    db.close()
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    db = create_repository()
    if db.stats()["leads"] == 0:
        print("Нет данных. Сначала выполните: python run.py run --competitors")
        db.close()
        return 1
    paths = report.export_all(db)
    print("Отчёты сформированы:")
    for path in paths:
        print(f"  - {path}")
    db.close()
    return 0


def cmd_leads(args: argparse.Namespace) -> int:
    db = create_repository()
    _print_leads(db, limit=args.limit)
    db.close()
    return 0


def cmd_dashboard(args: argparse.Namespace) -> int:
    from .dashboard import serve

    serve(host=args.host, port=args.port)
    return 0


def cmd_sources(_: argparse.Namespace) -> int:
    sources = config.sources_config().get("sources", {})
    print(f"{'Источник':<28} {'Вкл':<5} {'Вес':<5} Риск")
    print("-" * 55)
    for key, meta in sources.items():
        print(f"{key:<28} {str(meta.get('enabled')):<5} "
              f"{meta.get('weight', 0):<5} {meta.get('legal_risk', '')}")
    return 0


def cmd_validate(_: argparse.Namespace) -> int:
    problems = config.validate()
    if not problems:
        print("Конфигурация корректна.")
        return 0
    print("Обнаружены проблемы конфигурации:")
    for problem in problems:
        print(f"  - {problem}")
    return 1


def cmd_health(_: argparse.Namespace) -> int:
    db = create_repository()
    rows = db.source_health() if hasattr(db, "source_health") else []
    if not rows:
        print("Нет данных о состоянии источников. Выполните: python run.py run")
    else:
        print(f"{'Источник':<28} {'Статус':<9} {'Записей':<8} Проверено")
        print("-" * 70)
        for row in rows:
            print(f"{row['source']:<28} {row['status']:<9} "
                  f"{row['records']:<8} {row.get('checked_at', '')}")
    db.close()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="medax-radar",
        description="MedAX Radar — рыночная разведка и лид-радар для MedAX Group",
    )
    parser.add_argument("--version", action="version", version=f"MedAX Radar {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="Запустить пайплайн сбора и скоринга")
    p_run.add_argument("--competitors", action="store_true",
                       help="Включить модуль 2 (парсинг конкурентов, демо-данные)")
    p_run.add_argument("--export", action="store_true", help="Экспортировать отчёты")
    p_run.add_argument("--verbose", action="store_true", help="Подробный лог")
    p_run.add_argument("--limit", type=int, default=10, help="Сколько лидов показать")
    p_run.add_argument("--no-leads", action="store_true", help="Не печатать лиды")
    p_run.add_argument("--no-reset", action="store_true",
                       help="Не очищать хранилище (идемпотентный upsert)")
    p_run.set_defaults(func=cmd_run)

    p_report = sub.add_parser("report", help="Сформировать отчёты из БД")
    p_report.set_defaults(func=cmd_report)

    p_leads = sub.add_parser("leads", help="Показать лиды из БД")
    p_leads.add_argument("--limit", type=int, default=10)
    p_leads.set_defaults(func=cmd_leads)

    p_dash = sub.add_parser("dashboard", help="Запустить веб-дашборд")
    p_dash.add_argument("--host", default=os.environ.get("MEDAX_HOST", "127.0.0.1"))
    p_dash.add_argument("--port", type=int, default=int(os.environ.get("MEDAX_PORT", "8080")))
    p_dash.set_defaults(func=cmd_dashboard)

    p_src = sub.add_parser("sources", help="Показать источники и их статус")
    p_src.set_defaults(func=cmd_sources)

    p_val = sub.add_parser("validate", help="Проверить конфигурацию проекта")
    p_val.set_defaults(func=cmd_validate)

    p_health = sub.add_parser("health", help="Показать состояние источников")
    p_health.set_defaults(func=cmd_health)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
