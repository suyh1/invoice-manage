# Auto Migration Startup Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Automatically run Alembic migrations before the web server starts so first-time Docker/NAS deployments show the first-administrator setup page without manual migration commands.

**Architecture:** Replace the inline generated Docker entrypoint with a versioned shell script copied into the image. The `web` command runs migrations first, then starts Uvicorn. The `migrate` command remains a manual explicit command.

**Tech Stack:** Dockerfile, POSIX `sh`, Alembic, Docker Compose, pytest documentation/entrypoint checks.

---

### Task 1: Add failing container entrypoint tests

**Files:**
- Create: `backend/tests/test_container_entrypoint.py`

**Steps:**
1. Assert `docker/invoice-entrypoint.sh` exists.
2. Run `sh -n docker/invoice-entrypoint.sh`.
3. Assert the script contains an `AUTO_MIGRATE` guard.
4. Assert the `web` branch runs `alembic -c /app/alembic.ini upgrade head` before `uvicorn`.
5. Run the test and confirm it fails before the script exists.

### Task 2: Add the entrypoint script and wire the Dockerfile

**Files:**
- Create: `docker/invoice-entrypoint.sh`
- Modify: `Dockerfile`

**Steps:**
1. Implement `run_migrations`.
2. Respect `AUTO_MIGRATE=false|0|no`.
3. Retry migration briefly to tolerate database startup timing.
4. Keep `web`, `worker`, `migrate`, and fallback command behavior.
5. Copy the script in `Dockerfile` and mark it executable.
6. Run the entrypoint tests and confirm they pass.

### Task 3: Exercise auto migration in E2E Compose

**Files:**
- Modify: `tests/e2e/docker-compose.e2e.yml`

**Steps:**
1. Replace the E2E `app` service custom shell command with `command: ["web"]`.
2. Replace the E2E `worker` direct Celery command with `command: ["worker"]`.
3. Keep `WORKER_CONCURRENCY=1` in the environment.
4. Run the relevant test/build checks.

### Task 4: Update deployment docs

**Files:**
- Modify: `README.md`
- Modify: `docs/deployment/linux-amd64-docker-deployment.md`
- Modify: `docs/operations/runbook.md`

**Steps:**
1. Remove manual migration from the default first-time and upgrade command blocks.
2. Explain that the web container runs Alembic automatically before startup.
3. Keep manual `migrate` as an advanced recovery command.
4. Warn again that `docker compose down -v` deletes volumes.
