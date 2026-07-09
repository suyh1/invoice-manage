#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd -- "${SCRIPT_DIR}/../.." && pwd)"
COMPOSE_FILE="${ROOT_DIR}/tests/e2e/docker-compose.e2e.yml"

cleanup() {
  docker compose -f "${COMPOSE_FILE}" down -v --remove-orphans >/dev/null 2>&1 || true
}

trap cleanup EXIT

docker compose -f "${COMPOSE_FILE}" down -v --remove-orphans
docker compose -f "${COMPOSE_FILE}" up --build --abort-on-container-exit --exit-code-from e2e

docker compose -f "${COMPOSE_FILE}" up -d app worker
for _ in $(seq 1 40); do
  if curl -fsS http://localhost:18090/healthz >/dev/null; then
    break
  fi
  sleep 1
done
curl -fsS http://localhost:18090/healthz >/dev/null

docker compose -f "${COMPOSE_FILE}" run --rm -e E2E_PHASE=persistence e2e
