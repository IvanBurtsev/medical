# Модуль 2 — «Радар конкуренции»: включение и использование

Модуль собирает **публичные** предложения конкурентов (цена, бренд, ссылка) и
сопоставляет с каталогом MedAX. Включён по решению владельца продукта; юридическое
заключение оформляется параллельно.

## Что реализовано

- **Живой сбор** через `medax_radar/net/`: соблюдение `robots.txt`, rate limiting
  (token bucket на домен), идентификация бота, повторные попытки.
- **Allowlist**: собираются только домены из `config/competitors.json`.
- **Извлечение** без внешних зависимостей (`medax_radar/extract.py`):
  1. JSON-LD (`schema.org Product/Offer`) — приоритет;
  2. Microdata (`itemtype=Product`, `itemprop=name/price`);
  3. запасной разбор цен регулярным выражением.
- Запрещено: обход авторизации/капчи/paywall, сбор персональных данных.

## Конфигурация — `config/competitors.json`

```json
{
  "allowlist_enforced": true,
  "rate_limit_per_sec": 0.5,
  "sites": [
    {
      "name": "Название конкурента",
      "base_url": "https://competitor.ru",
      "catalog_urls": ["https://competitor.ru/catalog/"],
      "region": "Ставропольский край",
      "enabled": true
    }
  ]
}
```

Перед включением сайта проверьте его `robots.txt` вручную.

## Команды

```bash
# Разовый сбор одной страницы (проверка правил извлечения)
python run.py scrape https://competitor.ru/catalog/ --competitor "Конкурент" --json

# Полный цикл с живым сбором конкурентов
python run.py run --competitors --live --export --verbose

# Без live — используются демо-данные data/samples/competitors.json
python run.py run --competitors --export
```

## Безопасность и этика

| Механизм | Реализация |
|---|---|
| robots.txt | `net/robots.py`, по умолчанию обязателен |
| Ограничение частоты | `net/ratelimit.py`, 1 запрос / 2 c по умолчанию |
| Allowlist доменов | `ingestion/competitor.py::_allowed` |
| Идентификация | `MEDAX_USER_AGENT` с контактом |
| Персональные данные | не извлекаются |
| Остановка | отключить `enabled` у сайта или убрать источник |

## Ограничения

- Сайты без JSON-LD/microdata могут требовать настройки под конкретную вёрстку
  (добавляется в `extract.py` или через конфиг).
- Юридическое заключение — `docs/legal/`.

## Настроенные конкуренты

| Конкурент | Сайт | Статус | Источник товаров |
|---|---|---|---|
| Dealmed | dealmed.ru | включён | sitemap-iblock-3.xml → карточки `.html` |
| MEDLIGA | medliga.ru | включён | каталог → карточки `/products/…/` |
| М.П.А. медицинские партнёры | mpamed.ru | выключен | анти-бот-защита, нужен браузер |
| РТ-Медицинские технологии | rt-mt.ru | выключен | каталог рендерится JS |

Для `dealmed` используется `sitemap_urls` (обход карточек по карте сайта),
для `medliga` — `catalog_urls` + `follow_product_links`.

### Пример результата live-прогона

```
Dealmed:  26 предложений
MEDLIGA:  13 предложений
```

## Регламент запуска (важно)

Live-сбор занимает ~1–2 минуты, поэтому он **не выполняется в веб-запросе**.
Он запускается отдельным заданием (cron) и наполняет базу; дашборд только читает БД.

```bash
# ежедневно в 04:00
0 4 * * * cd /path/to/app && python3 run.py run --competitors --live --export >> runtime/cron.log 2>&1
```

## Тесты

```bash
python -m unittest tests.test_extract tests.test_competitor_live -v
```

Проверяются: JSON-LD, microdata, regex-фолбэк, дедупликация, allowlist,
запрет robots.txt, sitemap и полный live-путь через локальный HTTP-сервер.
