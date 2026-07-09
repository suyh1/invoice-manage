FROM node:24.13.0-bookworm-slim AS frontend-build

WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12.11-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_PORT=8080

WORKDIR /app

RUN pip install --no-cache-dir \
    "alembic==1.16.5" \
    "celery==5.6.3" \
    "cryptography==46.0.3" \
    "fastapi==0.116.0" \
    "python-multipart==0.0.20" \
    "psycopg[binary]==3.2.13" \
    "redis==8.0.1" \
    "tencentcloud-sdk-python-common==3.1.129" \
    "tencentcloud-sdk-python-ocr==3.1.128" \
    "sqlalchemy==2.0.51" \
    "uvicorn[standard]==0.35.0" \
    "pydantic-settings==2.10.1" \
  && addgroup --system invoice \
  && adduser --system --ingroup invoice invoice

COPY backend/alembic.ini ./alembic.ini
COPY backend/app ./app
COPY --from=frontend-build /frontend/dist ./app/static

RUN mkdir -p /data/uploads /data/exports /data/tmp \
  && printf '#!/bin/sh\nexec python -m app.cli "$@"\n' > /usr/local/bin/invoice-app \
  && printf '%s\n' \
    '#!/bin/sh' \
    'set -e' \
    'case "$1" in' \
    '  web)' \
    '    shift' \
    '    exec uvicorn app.main:app --host 0.0.0.0 --port "${APP_PORT:-8080}" "$@"' \
    '    ;;' \
    '  worker)' \
    '    shift' \
    '    exec celery -A app.workers.celery_app worker --loglevel="${CELERY_LOGLEVEL:-INFO}" --concurrency="${WORKER_CONCURRENCY:-4}" "$@"' \
    '    ;;' \
    '  migrate)' \
    '    shift' \
    '    exec alembic -c /app/alembic.ini upgrade head "$@"' \
    '    ;;' \
    '  *)' \
    '    exec "$@"' \
    '    ;;' \
    'esac' \
    > /usr/local/bin/invoice-entrypoint \
  && chmod +x /usr/local/bin/invoice-app \
  && chmod +x /usr/local/bin/invoice-entrypoint \
  && chown -R invoice:invoice /app /data

USER invoice
EXPOSE 8080

ENTRYPOINT ["invoice-entrypoint"]
CMD ["web"]
