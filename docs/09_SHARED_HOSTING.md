# Развёртывание на виртуальном хостинге (CGI)

Docker на виртуальном хостинге недоступен, но приложение работает через
**Python CGI** (Python 3.10+). Данные синтетические; для продакшена —
VPS + Docker (см. `07_DEPLOYMENT.md`) или хостинг с поддержкой CGI.

## 1. Требования

- Виртуальный хостинг с SSH, Python 3.10+, каталогом `~/public_html/cgi-bin`.
- Внешний вид в примере: Timeweb (`ci384326.tw1.ru`).

## 2. Важное ограничение хостинга (AppArmor + PrivateTmp)

На Timeweb CGI-процесс ограничен профилем AppArmor и **видит только
`public_html`**: домашний каталог и общий `/tmp` ему недоступны
(`/tmp` изолирован, PrivateTmp). Поэтому код и база размещаются **внутри
`public_html/cgi-bin`** (в скрытом по имени подкаталоге).

> Следствие: файлы приложения (и SQLite-база) технически доступны по прямому
> URL. Для демо на временном домене допустимо; для продакшена — VPS.

## 3. Структура на сервере (рабочая)

```
~/public_html/
├── index.html                        # страница-переход на дашборд
└── cgi-bin/
    ├── index.cgi                     # HTML-дашборд
    ├── api.cgi                       # JSON API
    └── app_7m2k9x/                   # приложение (AppArmor-доступно)
        ├── medax_radar/
        ├── config/
        ├── data/
        ├── certs/
        ├── run.py
        └── runtime/                  # SQLite и отчёты
```

CGI-скрипты находят приложение относительно себя (`app_7m2k9x`).

## 4. Установка

```bash
# 1. Загрузить код
tar czf medaxapp.tar.gz medax_radar config data run.py
scp medaxapp.tar.gz user@HOST:/tmp/
ssh user@HOST 'mkdir -p ~/public_html/cgi-bin/app_7m2k9x && tar xzf /tmp/medaxapp.tar.gz -C ~/public_html/cgi-bin/app_7m2k9x'

# 2. Собрать данные
ssh user@HOST 'cd ~/public_html/cgi-bin/app_7m2k9x && python3 run.py run --competitors'

# 3. Загрузить CGI
scp deploy/cgi/index.cgi deploy/cgi/api.cgi user@HOST:public_html/cgi-bin/
scp deploy/cgi/index.html user@HOST:public_html/
ssh user@HOST 'chmod +x ~/public_html/cgi-bin/*.cgi'
```

## 5. Адреса

| Что | URL |
|---|---|
| Дашборд | `http://<техдомен>/cgi-bin/index.cgi` |
| JSON API | `http://<техдомен>/cgi-bin/api.cgi` |
| Корень | `http://<техдомен>/` (переход на дашборд) |

## 6. Обновление данных

Live-сбор занимает ~3–4 минуты (zakupki отвечает ~60 с на запрос), поэтому его
запускают отдельным заданием, а не в веб-запросе.

```bash
ssh user@HOST 'cd ~/public_html/cgi-bin/app_7m2k9x && python3 run.py run --competitors --live --export'
```

Cron (только через панель Timeweb, crontab закрыт) — команда задания:

```
cd /home/c/ci384326/public_html/cgi-bin/app_7m2k9x && python3 run.py run --competitors --live --export
```

## 7. Ограничения CGI

- Нет Docker/root, порты 80/443 принадлежат хостингу.
- Авторизация на уровне приложения невозможна: nginx **не передаёт**
  заголовок `Authorization` в CGI. Для защиты используйте пароль на каталог
  в панели хостинга или переходите на VPS.
- Одновременная нагрузка ограничена; для реальных пользователей — VPS.

## 8. Обновление кода

```bash
scp medaxapp.tar.gz user@HOST:/tmp/
ssh user@HOST 'cd ~/public_html/cgi-bin/app_7m2k9x && tar xzf /tmp/medaxapp.tar.gz'
```

CGI перечитывает код на каждом запросе — перезапуск не нужен.
