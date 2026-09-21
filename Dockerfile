FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MEDAX_HOST=0.0.0.0 \
    MEDAX_PORT=8080 \
    MEDAX_DB_BACKEND=sqlite

WORKDIR /app

COPY pyproject.toml README.md ./
COPY config ./config
COPY data ./data
COPY certs ./certs
COPY docs ./docs
COPY medax_radar ./medax_radar
COPY tests ./tests
COPY run.py ./
COPY scripts ./scripts

RUN chmod +x scripts/entrypoint.sh \
    && useradd --create-home --uid 10001 app \
    && mkdir -p /app/runtime && chown -R app:app /app

USER app

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('MEDAX_PORT','8080')+'/health')" || exit 1

ENTRYPOINT ["scripts/entrypoint.sh"]
CMD ["serve"]
