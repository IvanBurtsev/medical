# Размещение на хосте (бюджетный вариант)

Приложение очень лёгкое: чистый Python, без тяжёлых зависимостей и без GPU.
Для демо и первых пользователей достаточно **1 vCPU / 1 GB RAM / 10 GB SSD**.

> Цены ниже — ориентировочные (2026), проверяйте актуальные тарифы и промо.
> Для реального продукта нужен хостинг **на территории РФ** (152-ФЗ).

## 1. Сравнение бюджетных вариантов

| Провайдер | Тип | Ориентир/мес | Плюсы | Минусы |
|---|---|---|---|---|
| **Timeweb Cloud** | VPS | ~200–300 ₽ | RU, Docker в один клик, простая панель | — |
| Aeza | VPS | ~120–200 ₽ | дешёво, RU/др. | репутация под нагрузкой |
| VDSina | VPS | ~150–250 ₽ | RU, стабильно | панель проще |
| Beget | VPS | ~200–300 ₽ | RU, поддержка | — |
| RuVDS | VPS | ~150–250 ₽ | RU | — |
| FirstVDS | VPS | ~150–250 ₽ | RU, дешёвые тарифы | — |
| Timeweb Cloud Apps | PaaS-контейнер | ~200–400 ₽ | без администрирования ОС | меньше контроля |
| Selectel / Yandex / VK Cloud | IaaS | ~250–500 ₽ | масштабируемость | сложнее, дороже |

### Рекомендация

**Timeweb Cloud, VPS 1 vCPU / 1 GB (Ubuntu 24.04, Docker).**
Оптимум «цена / простота / RU-локация». Альтернатива по дешевизне — **Aeza**.

Если хочется вообще без администрирования ОС — **Timeweb Cloud Apps**
(деплой Docker-образа), но для нашего compose с Caddy удобнее обычный VPS.

## 2. Что понадобится

- VPS 1 vCPU / 1 GB (Ubuntu 24.04, с предустановленным Docker).
- Свободные порты 80 и 443.
- (Опционально) домен. **Если домена нет** — используйте бесплатный
  `<IP>.sslip.io`, Caddy сам получит TLS-сертификат Let's Encrypt.

## 3. Пошаговая инструкция

### 3.1. Создать сервер

При заказе выбрать образ **Ubuntu 24.04 + Docker**. Записать IP.

### 3.2. Подключиться и открыть порты

```bash
ssh root@<IP>
# firewall (если используется ufw)
ufw allow 22,80,443/tcp && ufw --force enable
```

### 3.3. Загрузить проект

Вариант A — через git (если репозиторий запушен):

```bash
git clone <REPO_URL> /opt/medax-radar
cd /opt/medax-radar
```

Вариант B — залить папку с локальной машины (Windows PowerShell):

```powershell
scp -r C:\copy\medax-radar root@<IP>:/opt/medax-radar
```

### 3.4. Настроить переменные

```bash
cd /opt/medax-radar
cp deploy/.env.prod.example .env
nano .env
```

Заполнить:

```
MEDAX_DOMAIN=<IP>.sslip.io
MEDAX_AUTH_USER=medax
MEDAX_AUTH_PASSWORD=<надёжный_пароль>
```

### 3.5. Запустить

```bash
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml ps
```

Приложение: `https://<IP>.sslip.io` (в браузере спросит логин/пароль).

### 3.6. Проверить

```bash
curl -sk https://<IP>.sslip.io/health
# {"status": "ok", "stats": {...}}
```

## 4. Обновление

```bash
cd /opt/medax-radar
git pull                         # или scp новой версии
docker compose -f docker-compose.prod.yml up -d --build
```

## 5. Резервное копирование

SQLite хранится в `runtime/medax_radar.db`.

```bash
# пример крона: ежедневный бэкап в 03:00
0 3 * * * cp /opt/medax-radar/runtime/medax_radar.db /opt/backups/medax_$(date +\%F).db
```

## 6. Экономия

- 1 GB RAM достаточно; не переплачивать за 2–4 GB.
- Домен не обязателен — `sslip.io` бесплатен.
- TLS через Let's Encrypt бесплатен (Caddy делает автоматически).
- PostgreSQL не нужен на старте — SQLite справляется.
- Не покупать managed-сервисы и enterprise-платформы (см. `05_ROLES_BUDGET.md`).

## 7. Безопасность при публикации

- Обязательно задан `MEDAX_AUTH_USER` / `MEDAX_AUTH_PASSWORD`.
- TLS включён (Caddy).
- Порт приложения (8080) наружу **не** публикуется — только через Caddy.
- Данные модуля 2 не публикуются (см. `docs/legal/`).
