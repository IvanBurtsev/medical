#!/usr/bin/env sh
# Entrypoint MedAX Radar.
#   serve   — собрать данные (если нужно) и запустить дашборд
#   run     — выполнить пайплайн и выйти
#   report  — сформировать отчёты
#   <любое> — передать аргументы напрямую в run.py
set -eu

cd "$(dirname "$0")/.."

MODE="${1:-serve}"

case "$MODE" in
  serve)
    python run.py run --competitors --export || true
    exec python run.py dashboard --host "${MEDAX_HOST:-0.0.0.0}" --port "${MEDAX_PORT:-8080}"
    ;;
  run)
    exec python run.py run --competitors --export
    ;;
  report)
    exec python run.py report
    ;;
  *)
    exec python run.py "$@"
    ;;
esac
