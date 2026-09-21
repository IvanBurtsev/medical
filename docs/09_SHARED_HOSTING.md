# Развёртывание на виртуальном хостинге (CGI)

Docker на виртуальном хостинге недоступен, но приложение работает через
**Python CGI** (Python 3.10+). Данные синтетические; для продакшена —
VPS + Docker (см. `07_DEPLOYMENT.md`) или хостинг с поддержкой CGI.

## 1. Требования

- Виртуальный хостинг с SSH, Python 3.10+, каталогом `~/public_html/cgi-bin`.
- Внешний вид в примере: Timeweb (`ci384326.tw1.ru`).

## 2. Структура на сервере

```
~/medax-radar/                # код приложения (ВНЕ public_html)
├── medax_radar/
├── config/
├── data/
├── run.py
└── runtime/                  # SQLite и отчёты (создаётся автоматически)

~/public_html/
├── index.html                # страница-переход на дашборд
└── cgi-bin/
    ├── index.cgi             # HTML-дашборд
    └── api.cgi               # JSON API
```

## 3. Установка

```bash
# 1. Загрузить код
tar czf medaxapp.tar.gz medax_radar config data run.py
scp medaxapp.tar.gz user@HOST:/tmp/
ssh user@HOST 'mkdir -p ~/medax-radar && cd ~/medax-radar && tar xzf /tmp/medaxapp.tar.gz'

# 2. Собрать данные
ssh user@HOST 'cd ~/medax-radar && python3 run.py run --competitors'

# 3. Загрузить CGI
scp deploy/cgi/index.cgi deploy/cgi/api.cgi user@HOST:public_html/cgi-bin/
scp deploy/cgi/index.html user@HOST:public_html/
ssh user@HOST 'chmod +x ~/public_html/cgi-bin/*.cgi'
```

## 4. Адреса

| Что | URL |
|---|---|
| Дашборд | `http://<техдомен>/cgi-bin/index.cgi` |
| JSON API | `http://<техдомен>/cgi-bin/api.cgi` |
| Корень | `http://<техдомен>/` (переход на дашборд) |

## 5. Обновление данных

```bash
ssh user@HOST 'cd ~/medax-radar && python3 run.py run --competitors'
```

Либо настроить задание cron в панели хостинга.

## 6. Ограничения CGI

- Нет Docker/root, порты 80/443 принадлежат хостингу.
- Авторизация на уровне приложения невозможна: nginx **не передаёт**
  заголовок `Authorization` в CGI. Для защиты используйте пароль на каталог
  в панели хостинга или переходите на VPS.
- Одновременная нагрузка ограничена; для реальных пользователей — VPS.

## 7. Обновление кода

```bash
scp medaxapp.tar.gz user@HOST:/tmp/
ssh user@HOST 'cd ~/medax-radar && tar xzf /tmp/medaxapp.tar.gz'
```

CGI перечитывает код на каждом запросе — перезапуск не нужен.
