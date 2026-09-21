#!/usr/bin/env bash
# Bootstrap-развёртывание MedAX Radar на чистом Ubuntu/Debian-сервере.
#
# Вариант 1 (одной командой, из репозитория):
#   MEDAX_AUTH_USER=medax MEDAX_AUTH_PASSWORD='сильный_пароль' \
#   bash -c "$(curl -fsSL https://raw.githubusercontent.com/IvanBurtsev/medical/main/deploy/install.sh)"
#
# Вариант 2 (уже клонирован репозиторий):
#   MEDAX_DOMAIN=<IP>.sslip.io MEDAX_AUTH_USER=medax \
#   MEDAX_AUTH_PASSWORD='сильный_пароль' bash deploy/install.sh
#
# Скрипт: ставит Docker (если нужно), клонирует репозиторий, пишет .env
# и поднимает продакшн-стек (приложение + Caddy с TLS).
set -euo pipefail

REPO="${MEDAX_REPO:-https://github.com/IvanBurtsev/medical.git}"
DIR="${MEDAX_DIR:-/opt/medax-radar}"
DOMAIN="${MEDAX_DOMAIN:-}"
AUTH_USER="${MEDAX_AUTH_USER:-}"
AUTH_PASSWORD="${MEDAX_AUTH_PASSWORD:-}"

log() { printf '\033[1;32m==>\033[0m %s\n' "$*"; }
err() { printf '\033[1;31m[!]\033[0m %s\n' "$*" >&2; }

# --- 0. Проверки и ввод ------------------------------------------------------
if [ -z "$DOMAIN" ]; then
  IP="$(curl -fsS4 ifconfig.me 2>/dev/null || hostname -I | awk '{print $1}')"
  DOMAIN="${IP}.sslip.io"
  log "Домен не задан, использую бесплатный: ${DOMAIN}"
fi
if [ -z "$AUTH_USER" ]; then read -r -p "Логин для дашборда: " AUTH_USER; fi
if [ -z "$AUTH_PASSWORD" ]; then
  read -r -s -p "Пароль для дашборда: " AUTH_PASSWORD; echo
fi
[ -n "$AUTH_USER" ] && [ -n "$AUTH_PASSWORD" ] || { err "Задайте логин и пароль"; exit 1; }

# --- 1. Docker ---------------------------------------------------------------
if ! command -v docker >/dev/null 2>&1; then
  log "Устанавливаю Docker..."
  curl -fsSL https://get.docker.com | sh
  systemctl enable --now docker
else
  log "Docker уже установлен: $(docker --version)"
fi

# --- 2. Код ------------------------------------------------------------------
if [ -d "$DIR/.git" ]; then
  log "Обновляю код в $DIR"
  git -C "$DIR" pull --ff-only
else
  log "Клонирую репозиторий в $DIR"
  mkdir -p "$(dirname "$DIR")"
  git clone --depth 1 "$REPO" "$DIR"
fi
cd "$DIR"

# --- 3. .env -----------------------------------------------------------------
log "Пишу .env"
cat > .env <<EOF
MEDAX_DOMAIN=${DOMAIN}
MEDAX_AUTH_USER=${AUTH_USER}
MEDAX_AUTH_PASSWORD=${AUTH_PASSWORD}
MEDAX_DB_BACKEND=sqlite
EOF
chmod 600 .env

# --- 4. Запуск ---------------------------------------------------------------
log "Собираю и запускаю контейнеры..."
docker compose -f docker-compose.prod.yml up -d --build

# --- 5. Итог -----------------------------------------------------------------
sleep 5
docker compose -f docker-compose.prod.yml ps

echo
log "Готово."
echo "  Дашборд: https://${DOMAIN}   (логин: ${AUTH_USER})"
echo "  Проверка: curl -k https://${DOMAIN}/health"
echo
echo "Если домен .sslip.io не резолвится сразу — подождите 1-2 минуты."
echo "Порты 80 и 443 должны быть открыты в firewall хостинга."
