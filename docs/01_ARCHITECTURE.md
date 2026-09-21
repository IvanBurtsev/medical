# Архитектура MedAX Radar v4.0

## 1. Принципы

1. **Минимализм.** Никакой инфраструктуры сверх необходимого для пилота.
2. **Compliance by default.** Открытые данные в основе; персональные данные не хранятся.
3. **Сменные адаптеры.** Новый источник = новый класс, без правок ядра.
4. **Объяснимость.** Каждый лид содержит причины скоринга.
5. **Развитие по спросу.** Сложные слои (графы, агенты) — только после подтверждения ценности.

## 2. Слои (уровень пилота)

```
┌───────────────────────────────────────────────┐
│ CLI / Веб-дашборд / Экспорт (CSV, JSON, MD)   │
├───────────────────────────────────────────────┤
│ Скоринг (scoring.py)                          │
│ Матчинг (matching.py)                         │
│ Дедупликация (dedupe.py)                      │
│ Нормализация (normalize.py)                   │
├───────────────────────────────────────────────┤
│ Пайплайн-оркестратор (pipeline.py)            │
├───────────────────────────────────────────────┤
│ Адаптеры источников (ingestion/)              │
│  Росздравнадзор • ФНС • zakupki • конкуренты  │
├───────────────────────────────────────────────┤
│ Хранилище (db.py — SQLite → PostgreSQL)       │
└───────────────────────────────────────────────┘
```

## 3. Модули кода

| Модуль | Ответственность |
|---|---|
| `config.py` | Загрузка каталога, источников, весов, валидация |
| `models.py` | Доменные модели (Clinic, Tender, CompetitorOffer, Lead) |
| `ingestion/base.py` | Интерфейс адаптера `fetch()` / `fetch_live()` |
| `ingestion/*.py` | Конкретные источники |
| `net/ratelimit.py` | Token bucket, per-host лимиты |
| `net/robots.py` | Соблюдение robots.txt с кэшем |
| `net/client.py` | HTTP-клиент: retry/backoff, UA, robots |
| `normalize.py` | Очистка, классификация, даты, регионы |
| `dedupe.py` | Слияние дублей, отсечение конкурентов |
| `matching.py` | Матчинг с каталогом и услугами |
| `scoring.py` | Объяснимый скоринг |
| `pipeline.py` | Оркестрация, метрики источников, идемпотентность |
| `storage/base.py` | Интерфейс `Repository` |
| `storage/sqlite.py` | Реализация SQLite (пилот) |
| `storage/postgres.py` | Реализация PostgreSQL (прод) |
| `storage/__init__.py` | Фабрика `create_repository()` |
| `report.py` | Экспорт отчётов |
| `dashboard.py` | Веб-дашборд (`http.server`) + `/health`, `/api/report` |
| `cli.py` | Команды `run/report/leads/dashboard/sources/validate/health` |

## 4. Путь данных

```
RawRecord(type, source, payload)
   │  ingestion.fetch()
   ▼
Clinic / Tender / CompetitorOffer        (models)
   │  normalize + dedupe
   ▼
merged clinics  +  tenders
   │  matching.recommend_for_clinic / match_tender
   ▼
Lead (score, tier, reasons, signals)     (scoring.score_lead)
   │  db.save_*
   ▼
SQLite  →  dashboard / report / CSV
```

## 5. Расширение

### 5.1. Добавить источник

1. Создать класс-наследник `SourceAdapter` в `medax_radar/ingestion/`.
2. Реализовать `fetch()` (и при необходимости `fetch_live()`).
3. Зарегистрировать в `ingestion/__init__.py → ADAPTERS`.
4. Добавить запись в `config/sources.json → sources`.

### 5.2. Изменить скоринг

Только через `config/sources.json → scoring`. Код `scoring.py` не меняется.

### 5.3. Перейти на PostgreSQL

Заменить реализацию `db.Database` (интерфейс методов сохраняется).
Демо-схема совместима с Postgres после правки типов.

## 6. Переход к продакшену (при доказанном спросе)

| Компонент | Пилот | Прод |
|---|---|---|
| Хранилище | SQLite | PostgreSQL 16 (РФ) |
| Очередь | нет | Redis / RabbitMQ (по нагрузке) |
| Извлечение из PDF/сложных страниц | эвристики | LLM-извлечение (compliance-провайдер) |
| Дашборд | `http.server` | внутренний портал / Bitrix-виджет |
| Секреты | нет | Vault / переменные окружения |
| Мониторинг | логи | метрики + алерты |

> GraphRAG, multi-agent, Confidential Computing, Event Backbone **не входят**
> в прод по умолчанию. Решение о них принимается отдельно по измеримой выгоде.

## 7. Схема БД (пилот)

- `clinics` — организации-лиды (ИНН, регион, лицензия, контакты, виды деятельности).
- `tenders` — госзакупки (реестровый номер, заказчик, НМЦК, ОКПД2, категории).
- `competitor_offers` — предложения конкурентов (модуль 2).
- `leads` — скорингованные лиды (балл, уровень, причины, рекомендации).
- `run_meta` — метаданные последнего прогона.
