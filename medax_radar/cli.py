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
        live=args.live,
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


def cmd_compare(args: argparse.Namespace) -> int:
    import json

    from . import compare, config

    db = create_repository()
    offers = db.competitor_offers()
    db.close()

    if args.live:
        from .medax_catalog import scrape_catalog, snapshot

        products = scrape_catalog()
        if products:
            path = config.RUNTIME_DIR / "medax_catalog.json"
            path.write_text(json.dumps(snapshot(products), ensure_ascii=False, indent=2),
                            encoding="utf-8")
            print(f"Собрано товаров MedAX: {len(products)} → {path}")
    else:
        products = compare.load_medax_snapshot()

    if not products:
        print("Нет каталога MedAX. Запустите: python run.py compare --live")
        return 1
    if not offers:
        print("Нет предложений конкурентов. Запустите: python run.py run --competitors --live")
        return 1

    report = compare.build_report(products, offers, threshold=args.threshold)
    out_dir = config.RUNTIME_DIR / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "price_comparison.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md = compare.render_markdown(report)
    (out_dir / "price_comparison.md").write_text(md, encoding="utf-8")

    print("=" * 62)
    print(" Сравнение цен MedAX ↔ конкуренты")
    print("=" * 62)
    print(f"  Товаров MedAX:        {report['medax_products']}")
    print(f"  Предложений конкурентов: {report['competitor_offers']}")
    print(f"  Сопоставлено пар:     {len(report['matches'])}")
    for row in report["positioning"]:
        print(f"    {row['category']:<14} пар={row['pairs']:<3} "
              f"Δ={row['delta_pct']:+.1f}%")
    print("  Отчёт: runtime/reports/price_comparison.md")
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


def cmd_scrape(args: argparse.Namespace) -> int:
    import json

    from .ingestion.competitor import scrape_url

    try:
        offers = scrape_url(args.url, args.competitor, region=args.region)
    except Exception as exc:  # noqa: BLE001
        print(f"Ошибка сбора: {exc}")
        return 1
    if not offers:
        print("Предложения не найдены (нет JSON-LD/microdata/цен).")
        return 0
    print(f"Найдено предложений: {len(offers)}")
    for offer in offers[: args.limit]:
        print(f"  - {offer['product_name'][:70]} — {offer['price']:,.0f} ₽")
    if args.json:
        print(json.dumps(offers, ensure_ascii=False, indent=2))
    return 0


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
    p_run.add_argument("--live", action="store_true",
                       help="Live-сбор: парсинг сайтов конкурентов из config/competitors.json")
    p_run.set_defaults(func=cmd_run)

    p_cmp = sub.add_parser("compare",
                           help="Сравнить цены MedAX и конкурентов")
    p_cmp.add_argument("--live", action="store_true",
                       help="Собрать каталог MedAX с medaxgroup.ru")
    p_cmp.add_argument("--threshold", type=float, default=0.2,
                       help="Порог схожести названий (0..1)")
    p_cmp.add_argument("--json", action="store_true", help="Вывести JSON")
    p_cmp.set_defaults(func=cmd_compare)

    p_scrape = sub.add_parser("scrape",
                              help="Разовый сбор публичной страницы конкурента (модуль 2)")
    p_scrape.add_argument("url", help="Публичный URL каталога")
    p_scrape.add_argument("--competitor", default="Неизвестный конкурент",
                          help="Название конкурента")
    p_scrape.add_argument("--region", default="", help="Регион конкурента")
    p_scrape.add_argument("--limit", type=int, default=20, help="Сколько вывести")
    p_scrape.add_argument("--json", action="store_true", help="Вывести JSON")
    p_scrape.set_defaults(func=cmd_scrape)

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
