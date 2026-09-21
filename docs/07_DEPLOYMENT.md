# Развёртывание MedAX Radar

## 1. Локальный запуск

```bash
python run.py validate
python run.py run --competitors --export
python run.py dashboard --host 127.0.0.1 --port 8080
```

Требуется только Python 3.11+ — внешних зависимостей нет.

## 2. Продакшн (TLS + авторизация)

```bash
cp deploy/.env.prod.example .env   # заполнить MEDAX_DOMAIN, MEDAX_AUTH_*
docker compose -f docker-compose.prod.yml up -d --build
```

Caddy поднимает HTTPS (Let's Encrypt), приложение закрыто HTTP Basic.
Без домена используйте `<IP>.sslip.io`. Подробно — `08_HOSTING.md`.

## 3. Docker (dev)

```bash
docker build -t medax-radar:4.0.0 .
docker run --rm -p 8080:8080 -v "$PWD/runtime:/app/runtime" medax-radar:4.0.0
# → http://localhost:8080
```

Контейнер при старте собирает данные (sample) и поднимает дашборд.
Healthcheck опрашивает `/health`.

## 4. Docker Compose (dev)

```bash
docker compose up --build -d
docker compose logs -f
```

С PostgreSQL (опционально):

```bash
docker compose --profile postgres up --build -d
```

и в `docker-compose.yml` раскомментировать `MEDAX_DB_BACKEND=postgres`
и `MEDAX_DATABASE_URL`.

## 5. Переменные окружения

| Переменная | Назначение | По умолчанию |
|---|---|---|
| `MEDAX_HOST` | адрес привязки дашборда | `127.0.0.1` |
| `MEDAX_PORT` | порт дашборда | `8080` |
| `MEDAX_DB_BACKEND` | `sqlite` или `postgres` | `sqlite` |
| `MEDAX_DATABASE_URL` | DSN PostgreSQL | — |
| `MEDAX_USER_AGENT` | User-Agent бота | `MedAXRadarBot/4.0 (...)` |
| `MEDAX_AUTH_USER` | Логин HTTP Basic (пусто — доступ открыт) | — |
| `MEDAX_AUTH_PASSWORD` | Пароль HTTP Basic | — |

При заданном `MEDAX_AUTH_USER` все страницы и API требуют Basic-авторизацию.
Публичным остаётся только `/health` (для healthcheck).

## 6. Эндпоинты

| Путь | Назначение |
|---|---|
| `/` | HTML-дашборд |
| `/api/report` | JSON: лиды, тендеры, конкуренты, статистика |
| `/health` | JSON: `{"status":"ok","stats":{...}}` |

## 7. Режимы entrypoint

```bash
docker run medax-radar:4.0.0 serve    # по умолчанию: собрать + дашборд
docker run medax-radar:4.0.0 run      # только пайплайн
docker run medax-radar:4.0.0 report   # только отчёты
docker run medax-radar:4.0.0 leads --limit 20
```

## 8. Публикация в интернет

Для внешнего доступа рекомендуется reverse-proxy (nginx/Caddy) с TLS:

```
client → nginx (TLS, basic-auth) → medax-radar:8080
```

Обязательно закрыть доступ аутентификацией: дашборд предназначен для
внутреннего использования. Материалы по модулю 2 не публикуются.

## 9. Обновление данных

- Полный цикл: `docker compose exec medax-radar python run.py run --competitors`
- Идемпотентно (без очистки): добавить `--no-reset`.
- Периодичность — по cron/systemd timer раз в 1–7 дней.

## 10. Резервное копирование

- SQLite: копировать `runtime/medax_radar.db`.
- PostgreSQL: `pg_dump`.
- Отчёты: `runtime/reports/`.
