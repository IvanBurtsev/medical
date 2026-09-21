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

## Тесты

```bash
python -m unittest tests.test_extract tests.test_competitor_live -v
```

Проверяются: JSON-LD, microdata, regex-фолбэк, дедупликация, allowlist,
запрет robots.txt и полный live-путь через локальный HTTP-сервер.
