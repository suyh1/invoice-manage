#!/bin/sh
set -e

should_auto_migrate() {
  case "${AUTO_MIGRATE:-true}" in
    false | FALSE | 0 | no | NO | off | OFF)
      return 1
      ;;
    *)
      return 0
      ;;
  esac
}

run_migrations() {
  if ! should_auto_migrate; then
    echo "Skipping database migrations because AUTO_MIGRATE=${AUTO_MIGRATE}"
    return 0
  fi

  attempts="${MIGRATION_RETRIES:-15}"
  interval="${MIGRATION_RETRY_INTERVAL_SECONDS:-2}"
  attempt=1

  while :; do
    echo "Running database migrations (attempt ${attempt}/${attempts})..."
    if alembic -c /app/alembic.ini upgrade head; then
      echo "Database migrations complete."
      return 0
    fi

    if [ "${attempt}" -ge "${attempts}" ]; then
      echo "Database migrations failed after ${attempts} attempts."
      return 1
    fi

    attempt=$((attempt + 1))
    echo "Database migration failed; retrying in ${interval}s..."
    sleep "${interval}"
  done
}

case "$1" in
  web)
    shift
    run_migrations
    exec uvicorn app.main:app --host 0.0.0.0 --port "${APP_PORT:-8080}" "$@"
    ;;
  worker)
    shift
    exec celery -A app.workers.celery_app worker --loglevel="${CELERY_LOGLEVEL:-INFO}" --concurrency="${WORKER_CONCURRENCY:-4}" "$@"
    ;;
  migrate)
    shift
    exec alembic -c /app/alembic.ini upgrade head "$@"
    ;;
  *)
    exec "$@"
    ;;
esac
