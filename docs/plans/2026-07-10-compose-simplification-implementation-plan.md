# Docker Compose and Database Configuration Simplification Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Simplify the production Docker Compose deployment so users configure PostgreSQL with separate fields, customize only the host port, and no longer see unused proxy/default environment settings.

**Architecture:** `Settings` will accept split PostgreSQL fields and expose a generated SQLAlchemy URL, while retaining `DATABASE_URL` as an optional compatibility override. The root Compose file will share credentials through YAML anchors, pass only service-relevant variables, and keep the container port fixed at 8080. Deployment examples will match the self-contained Compose workflow.

**Tech Stack:** Python 3.12, Pydantic Settings, SQLAlchemy URL utilities, Pytest, Docker Compose YAML

---

### Task 1: Specify split PostgreSQL configuration behavior

**Files:**
- Modify: `backend/tests/test_config.py`
- Test: `backend/tests/test_config.py`

**Step 1: Write the failing construction test**

Add:

```python
def test_settings_build_database_url_from_postgres_fields() -> None:
    settings = Settings(
        _env_file=None,
        POSTGRES_HOST="db.internal",
        POSTGRES_PORT="5544",
        POSTGRES_DB="invoice_app",
        POSTGRES_USER="invoice_user",
        POSTGRES_PASSWORD="p@ss:/word",
    )

    assert settings.database_url == (
        "postgresql+psycopg://invoice_user:p%40ss%3A%2Fword@db.internal:5544/invoice_app"
    )
```

**Step 2: Write the failing override-precedence test**

Add:

```python
def test_database_url_override_takes_precedence_over_postgres_fields() -> None:
    override = "postgresql+psycopg://override:secret@database:5432/override_db"
    settings = Settings(
        _env_file=None,
        DATABASE_URL=override,
        POSTGRES_PASSWORD="ignored",
    )

    assert settings.database_url == override
```

**Step 3: Write the failing proxy-removal test**

Add:

```python
def test_unused_trusted_proxies_setting_is_not_exposed() -> None:
    settings = Settings(_env_file=None, TRUSTED_PROXIES="0.0.0.0/0")

    assert "trusted_proxies" not in Settings.model_fields
    assert "trusted_proxies" not in settings.safe_dict()
```

**Step 4: Run the targeted tests and confirm RED**

Run from `backend/`:

```bash
UV_CACHE_DIR=/private/tmp/invoice-uv-cache \
UV_PYTHON_INSTALL_DIR=/private/tmp/invoice-uv-python \
uv run --frozen --extra test pytest tests/test_config.py -v
```

Expected: the new split-field and proxy-removal assertions fail because `Settings` still uses a fixed `DATABASE_URL` default and still exposes `trusted_proxies`.

### Task 2: Implement split PostgreSQL settings

**Files:**
- Modify: `backend/app/core/config.py`
- Test: `backend/tests/test_config.py`

**Step 1: Import SQLAlchemy's URL builder**

Add:

```python
from sqlalchemy.engine import URL
```

**Step 2: Replace the fixed database field with split settings and an override**

Replace the current `database_url` field and remove the unused `trusted_proxies` field:

```python
    database_url_override: str | None = Field(default=None, validation_alias="DATABASE_URL")
    postgres_host: str = Field(default="postgres", validation_alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, validation_alias="POSTGRES_PORT")
    postgres_db: str = Field(default="invoice_app", validation_alias="POSTGRES_DB")
    postgres_user: str = Field(default="invoice_app", validation_alias="POSTGRES_USER")
    postgres_password: str = Field(default="change-me", validation_alias="POSTGRES_PASSWORD")
```

**Step 3: Expose the resolved URL through a property**

Add to `Settings` before `safe_dict()`:

```python
    @property
    def database_url(self) -> str:
        if self.database_url_override:
            return self.database_url_override
        return URL.create(
            drivername="postgresql+psycopg",
            username=self.postgres_user,
            password=self.postgres_password,
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_db,
        ).render_as_string(hide_password=False)
```

Remove `trusted_proxies` from `safe_dict()`. Keep its existing `database_url` entry so diagnostics continue to return a redacted resolved URL.

**Step 4: Run the targeted tests and confirm GREEN**

Run:

```bash
UV_CACHE_DIR=/private/tmp/invoice-uv-cache \
UV_PYTHON_INSTALL_DIR=/private/tmp/invoice-uv-python \
uv run --frozen --extra test pytest tests/test_config.py -v
```

Expected: all configuration tests pass.

**Step 5: Commit the backend configuration behavior**

```bash
git add backend/app/core/config.py backend/tests/test_config.py
git commit -m "feat: support split postgres settings"
```

### Task 3: Simplify the root Docker Compose file

**Files:**
- Modify: `docker-compose.yml`

**Step 1: Add shared credential and application-environment anchors**

Add below `name`:

```yaml
x-postgres-credentials: &postgres-credentials
  POSTGRES_DB: invoice_app
  POSTGRES_USER: invoice_app
  POSTGRES_PASSWORD: change-me

x-app-environment: &app-environment
  <<: *postgres-credentials
  POSTGRES_HOST: postgres
  POSTGRES_PORT: 5432
  OCR_CONFIG_ENCRYPTION_KEY: change-me-use-openssl-rand-base64-32
```

**Step 2: Replace the app environment list**

Use:

```yaml
    environment:
      <<: *app-environment
      APP_SECRET_KEY: change-me-use-openssl-rand-hex-32
```

This removes `APP_ENV`, `APP_BASE_URL`, `APP_PORT`, `TZ`, cookie defaults, `TRUSTED_PROXIES`, `DATABASE_URL`, Redis defaults, storage defaults, temp defaults, and worker defaults from the web service.

**Step 3: Replace the worker environment list**

Use:

```yaml
    environment: *app-environment
```

This intentionally does not pass `APP_SECRET_KEY` to the worker.

**Step 4: Reuse the PostgreSQL credential anchor**

Use:

```yaml
    environment: *postgres-credentials
```

Update its healthcheck to read the container environment:

```yaml
      test: ["CMD-SHELL", "pg_isready -U $$POSTGRES_USER -d $$POSTGRES_DB"]
```

**Step 5: Clarify host-port customization**

Keep the container port fixed and add a focused comment:

```yaml
    ports:
      # 只修改左侧的宿主机端口，容器端口保持 8080。
      - "8080:8080"
```

**Step 6: Validate the Compose model**

Run:

```bash
docker compose config --quiet
docker compose config
```

Expected: configuration succeeds; rendered app/worker environments contain split PostgreSQL variables but no `DATABASE_URL` or `TRUSTED_PROXIES`; only app contains `APP_SECRET_KEY`.

### Task 4: Remove dotenv deployment support and align documentation

**Files:**
- Delete: `.env`
- Delete: `.env.example`
- Modify: `.gitignore`
- Modify: `backend/tests/test_config.py`
- Modify: `backend/app/core/config.py`
- Modify: `README.md`
- Modify: `docs/adr/0001-core-architecture.md`
- Modify: `docs/design/01-overall-design.md`
- Modify: `docs/design/02-api-data-model.md`
- Modify: `docs/deployment/linux-amd64-docker-deployment.md`
- Modify: `docs/operations/runbook.md`

**Step 1: Write a failing test proving dotenv files are ignored**

Add to `backend/tests/test_config.py`:

```python
def test_settings_do_not_load_dotenv_files(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("POSTGRES_PASSWORD", raising=False)
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("POSTGRES_PASSWORD=from-dotenv\n", encoding="utf-8")

    settings = Settings()

    assert settings.postgres_password == "change-me"
```

**Step 2: Run the targeted test and confirm RED**

Run from `backend/`:

```bash
UV_CACHE_DIR=/private/tmp/invoice-uv-cache \
UV_PYTHON_INSTALL_DIR=/private/tmp/invoice-uv-python \
uv run --frozen --extra test pytest tests/test_config.py::test_settings_do_not_load_dotenv_files -v
```

Expected: FAIL because the current `SettingsConfigDict(env_file=".env")` loads `from-dotenv`.

**Step 3: Remove dotenv loading and the template files**

- Change `SettingsConfigDict(env_file=".env", extra="ignore")` to `SettingsConfigDict(extra="ignore")`.
- Delete the ignored root `.env` file without reading or exposing its contents.
- Delete tracked `.env.example`.
- Remove only the `!.env.example` exception from `.gitignore`; keep `.env` and `.env.*` ignored as a defensive secret-leak guard.
- Keep `.env` in `.dockerignore` for the same defensive reason.

**Step 4: Run the configuration suite and confirm GREEN**

Run:

```bash
UV_CACHE_DIR=/private/tmp/invoice-uv-cache \
UV_PYTHON_INSTALL_DIR=/private/tmp/invoice-uv-python \
uv run --frozen --extra test pytest tests/test_config.py -v
```

Expected: all configuration tests pass, including the new no-dotenv behavior.

**Step 5: Update active documentation**

- Replace `.env` setup steps with direct edits to `docker-compose.yml`.
- Tell users to change the image, the left side of `ports`, `APP_SECRET_KEY`, `OCR_CONFIG_ENCRYPTION_KEY`, and `POSTGRES_PASSWORD` before startup.
- Document split PostgreSQL fields and remove `DATABASE_URL`/`TRUSTED_PROXIES` from standard production examples.
- Explain that process environment variables remain available for tests and special deployments, but dotenv files are not part of the project workflow.
- Update backup/rotation/checklist instructions to protect the edited Compose file and its application encryption key instead of backing up `.env`.
- Remove `.env.example` from architecture trees and active security wording.

**Step 6: Search for stale active-project instructions**

Run:

```bash
rg -n "\.env|env_file|TRUSTED_PROXIES|APP_BASE_URL" \
  README.md docker-compose.yml .gitignore .dockerignore \
  docs/adr docs/design docs/deployment docs/operations

rg -n 'SettingsConfigDict\([^)]*env_file' backend/app || true
```

Expected: `.env` appears only in defensive ignore rules; no active deployment instruction references `env_file`, `TRUSTED_PROXIES`, or `APP_BASE_URL`; backend settings do not configure an dotenv file.

**Step 7: Commit Compose, dotenv removal, and documentation**

```bash
git add docker-compose.yml .gitignore backend/app/core/config.py backend/tests/test_config.py \
  README.md docs/adr docs/design docs/deployment docs/operations \
  docs/plans/2026-07-10-compose-simplification-implementation-plan.md
git add -u .env.example
git commit -m "chore: simplify compose deployment settings"
```

### Task 5: Full verification and review

**Files:**
- Review: all modified files

**Step 1: Run the full backend test suite**

Run from `backend/`:

```bash
UV_CACHE_DIR=/private/tmp/invoice-uv-cache \
UV_PYTHON_INSTALL_DIR=/private/tmp/invoice-uv-python \
uv run --frozen --extra test pytest -v
```

Expected: all tests pass, with only pre-existing integration skips when external test services are not configured.

**Step 2: Revalidate Compose and inspect resolved environments**

Run from the repository root:

```bash
docker compose config --quiet
docker compose config
```

Expected: Compose is valid and the rendered service environments match Task 3.

**Step 3: Check formatting and unintended changes**

Run:

```bash
git diff --check
git status --short
git log -3 --oneline --decorate
```

Expected: no whitespace errors; only intended files are changed or committed; work remains on `main`.

**Step 4: Apply @superpowers:verification-before-completion**

Review fresh command output before reporting success. Do not claim completion from earlier or partial results.
