# Invoice OCR Application Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a linux/amd64 Docker-delivered invoice storage, management, and OCR recognition system. MVP defaults to Tencent Cloud `VatInvoiceOCR`, but OCR providers, credentials, rate limits, and quota reminders are configured in the admin settings page instead of `.env` or Docker `environment`.

**Architecture:** Use a modular monolith: FastAPI serves REST APIs and the React SPA, Celery workers process OCR/export jobs asynchronously, PostgreSQL stores structured data, OCR JSON, encrypted provider configs, and quota alerts, Redis provides queueing and rate limiting, and Docker volumes store original invoices and exported files. OCR is encapsulated behind a provider adapter registry with Tencent Cloud and mock adapters in MVP and an extension point for Aliyun.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2, Alembic, Celery, Redis, PostgreSQL 16, React, Vite, TypeScript, Docker Buildx, Tencent Cloud SDK 3.0, application-level encryption for OCR provider credentials.

---

## Task 1: Repository Skeleton

**Files:**

- Create: `backend/pyproject.toml`
- Create: `backend/app/main.py`
- Create: `backend/app/core/config.py`
- Create: `backend/app/core/errors.py`
- Create: `backend/tests/test_health.py`
- Create: `frontend/package.json`
- Create: `frontend/src/main.tsx`
- Create: `Dockerfile`
- Create: `.env.example`

**Steps:**

1. Create backend package with FastAPI app and `/healthz`.
2. Create frontend Vite React app shell.
3. Add root Dockerfile skeleton with multi-stage build.
4. Add `.env.example` matching deployment guide.
5. Run backend unit test for `/healthz`.
6. Commit as `chore: initialize project skeleton`.

**Verification:**

```bash
cd backend && pytest tests/test_health.py -v
cd frontend && npm run build
docker buildx build --platform linux/amd64 -t invoice-ocr-app:dev .
```

## Task 2: Configuration And Credential Encryption Foundation

**Files:**

- Modify: `backend/app/core/config.py`
- Create: `backend/tests/test_config.py`

**Steps:**

1. Define settings for app, database, Redis, storage, worker concurrency, and `OCR_CONFIG_ENCRYPTION_KEY`.
2. Do not define or load Tencent Cloud SecretId/SecretKey from environment variables.
3. Keep OCR provider, upload constraints, QPS, retry, and quota reminder defaults in application code and admin-managed records, not deployment environment variables.
4. Add helper for encrypting/decrypting OCR provider credential payloads stored in the database.
5. Add secret redaction helper for logs/errors.
6. Test that OCR credential values never appear in serialized settings, logs, or API-safe config dumps.
7. Commit as `feat: add typed application configuration`.

**Verification:**

```bash
cd backend && pytest tests/test_config.py -v
```

## Task 3: Database Models And Migrations

**Files:**

- Create: `backend/app/db/session.py`
- Create: `backend/app/db/base.py`
- Create: `backend/app/domain/user/models.py`
- Create: `backend/app/domain/file/models.py`
- Create: `backend/app/domain/ocr/models.py`
- Create: `backend/app/domain/invoice/models.py`
- Create: `backend/app/domain/export/models.py`
- Create: `backend/alembic.ini`
- Create: `backend/app/db/migrations/`
- Create: `backend/tests/test_models.py`

**Steps:**

1. Implement SQLAlchemy models from `docs/design/02-api-data-model.md`, including OCR provider configs, daily usage, and quota alerts.
2. Add enums for document, OCR job, invoice, duplicate check, export statuses.
3. Add indexes and unique constraints.
4. Generate Alembic initial migration.
5. Test model creation in temporary PostgreSQL or test database.
6. Commit as `feat: add persistence models`.

**Verification:**

```bash
cd backend && alembic upgrade head
cd backend && pytest tests/test_models.py -v
```

## Task 4: Authentication And Authorization

**Files:**

- Create: `backend/app/domain/user/service.py`
- Create: `backend/app/api/routes/auth.py`
- Create: `backend/app/api/dependencies.py`
- Create: `backend/tests/test_auth.py`

**Steps:**

1. Implement password hashing.
2. Implement login/logout/current user.
3. Implement roles: `user`, `finance`, `admin`.
4. Add permission checks for own invoices vs finance/admin access.
5. Add admin creation CLI.
6. Commit as `feat: add local authentication`.

**Verification:**

```bash
cd backend && pytest tests/test_auth.py -v
```

## Task 5: File Upload Storage And Validation

**Files:**

- Create: `backend/app/domain/file/storage.py`
- Create: `backend/app/domain/file/validators.py`
- Create: `backend/app/domain/file/pdf.py`
- Create: `backend/app/api/routes/documents.py`
- Create: `backend/tests/test_file_validation.py`
- Create: `backend/tests/fixtures/files/`

**Steps:**

1. Implement `LocalFileStorage` writing to `/data/uploads/{yyyy}/{mm}/{sha256}.{ext}`.
2. Validate extension, MIME, and magic bytes.
3. Allow PNG/JPG/JPEG/PDF.
4. Reject GIF with `OCR_GIF_NOT_SUPPORTED`.
5. Calculate exact Base64 size and reject over 10MB.
6. Validate image dimensions 20-10000px.
7. Reject multi-page PDF for MVP.
8. Create document record and optional OCR job.
9. Commit as `feat: add invoice document upload`.

**Verification:**

```bash
cd backend && pytest tests/test_file_validation.py -v
```

## Task 6: OCR Provider Registry, Tencent Adapter, And Mock Adapter

**Files:**

- Create: `backend/app/domain/ocr/client.py`
- Create: `backend/app/domain/ocr/provider_config.py`
- Create: `backend/app/domain/ocr/registry.py`
- Create: `backend/app/domain/ocr/mock_client.py`
- Create: `backend/app/domain/ocr/quota.py`
- Create: `backend/app/domain/ocr/errors.py`
- Create: `backend/app/api/routes/admin_ocr.py`
- Create: `backend/tests/test_tencent_ocr_client.py`
- Create: `backend/tests/test_ocr_provider_config.py`
- Create: `backend/tests/test_ocr_quota_alerts.py`
- Create: `backend/tests/test_admin_ocr_provider_api.py`
- Create: `backend/tests/fixtures/ocr/vat_invoice_success.json`
- Create: `backend/tests/fixtures/ocr/vat_invoice_error_rate_limit.json`

**Steps:**

1. Define `OcrProviderClient` protocol and provider capability metadata.
2. Implement `OcrProviderRegistry` with `tencent` and `mock` adapters; reserve `aliyun` as an unsupported-but-modeled provider.
3. Implement encrypted CRUD service for `ocr_provider_configs`.
4. Implement production `TencentVatInvoiceOcrClient` with Tencent Cloud SDK.
5. Tencent default non-secret values:
   - endpoint `ocr.tencentcloudapi.com`
   - action `VatInvoiceOCR`
   - version `2018-11-19`
6. Load Tencent SecretId/SecretKey only from encrypted provider config records, never environment variables.
7. Use `ImageBase64` for local files.
8. Set `IsPdf=true` and `PdfPageNumber=1` for PDF.
9. Implement fixture/mock client for tests and demo.
10. Map Tencent exceptions to system errors.
11. Track successful and failed calls in daily provider usage.
12. Generate active quota alerts when configured free quota/resource package thresholds are crossed.
13. Implement admin APIs for provider list/create/update/test/set-default/credential rotation/quota calibration/alert acknowledge.
14. Commit as `feat: add ocr provider registry and tencent adapter`.

**Verification:**

```bash
cd backend && pytest tests/test_tencent_ocr_client.py tests/test_ocr_provider_config.py tests/test_ocr_quota_alerts.py tests/test_admin_ocr_provider_api.py -v
```

## Task 7: OCR Result Mapping

**Files:**

- Create: `backend/app/domain/ocr/mapper.py`
- Create: `backend/tests/test_ocr_mapper.py`

**Steps:**

1. Map `VatInvoiceInfos` to standard invoice fields.
2. Map `Items` to `invoice_items`.
3. Normalize Decimal, dates, tax rates, strings.
4. Save unrecognized fields in `extra_fields`.
5. Preserve full raw JSON.
6. Test official and fixture responses.
7. Commit as `feat: normalize vat invoice ocr results`.

**Verification:**

```bash
cd backend && pytest tests/test_ocr_mapper.py -v
```

## Task 8: Async Queue, Rate Limiting, And Retries

**Files:**

- Create: `backend/app/workers/celery_app.py`
- Create: `backend/app/workers/tasks.py`
- Create: `backend/app/domain/ocr/rate_limiter.py`
- Create: `backend/tests/test_ocr_jobs.py`
- Create: `backend/tests/test_rate_limiter.py`

**Steps:**

1. Add Celery app using Redis broker.
2. Implement OCR job worker state transitions.
3. Add Redis token bucket per `{provider}:{region}:{action}`.
4. Default Tencent QPS is 8, hard cap must not exceed configured provider limit.
5. Retry only retryable errors with 10s/30s/120s backoff.
6. Store `RequestId`, provider error code, duration, attempt count.
7. Commit as `feat: process ocr jobs asynchronously`.

**Verification:**

```bash
cd backend && pytest tests/test_ocr_jobs.py tests/test_rate_limiter.py -v
```

## Task 9: Invoice APIs

**Files:**

- Create: `backend/app/domain/invoice/service.py`
- Create: `backend/app/api/routes/invoices.py`
- Create: `backend/tests/test_invoice_api.py`

**Steps:**

1. Implement invoice list filters from API design.
2. Implement detail API with document, OCR meta, items, correction logs.
3. Implement patch with correction logging.
4. Implement confirm/archive/soft delete.
5. Enforce role permissions.
6. Commit as `feat: add invoice management api`.

**Verification:**

```bash
cd backend && pytest tests/test_invoice_api.py -v
```

## Task 10: Duplicate Detection

**Files:**

- Create: `backend/app/domain/invoice/duplicate.py`
- Modify: `backend/app/domain/invoice/service.py`
- Create: `backend/tests/test_duplicate_detection.py`

**Steps:**

1. Implement strong rule: invoice code + invoice number + invoice date + total amount.
2. Implement weak rule: invoice number + invoice date + seller + total amount.
3. Create `DuplicateCheck` records.
4. Add confirm/ignore APIs.
5. Commit as `feat: detect duplicate invoices`.

**Verification:**

```bash
cd backend && pytest tests/test_duplicate_detection.py -v
```

## Task 11: Export Tasks

**Files:**

- Create: `backend/app/domain/export/service.py`
- Create: `backend/app/api/routes/exports.py`
- Modify: `backend/app/workers/tasks.py`
- Create: `backend/tests/test_exports.py`

**Steps:**

1. Implement async export task creation.
2. Support CSV, XLSX, JSON.
3. XLSX sheets: `Invoices`, `Items`, `OCR Jobs`, `Export Metadata`.
4. Store files in `/data/exports`.
5. Require auth for download and expiry check.
6. Commit as `feat: add invoice exports`.

**Verification:**

```bash
cd backend && pytest tests/test_exports.py -v
```

## Task 12: Frontend Application Shell

**Files:**

- Create: `frontend/src/app/App.tsx`
- Create: `frontend/src/app/router.tsx`
- Create: `frontend/src/components/AppShell.tsx`
- Create: `frontend/src/pages/DashboardPage.tsx`
- Create: `frontend/src/pages/SettingsPage.tsx`
- Create: `frontend/src/components/OcrProviderSettings.tsx`
- Create: `frontend/src/components/OcrQuotaStatus.tsx`

**Steps:**

1. Implement left navigation: 总览、发票库、上传识别、待校对、导出记录、设置。
2. Add API client with auth handling.
3. Add settings page for OCR provider list, Tencent credential entry, connection test, default provider toggle, QPS, and quota warning thresholds.
4. Show configured status and credential fingerprint without echoing SecretId or SecretKey.
5. Show active OCR free quota/resource package alerts in settings and dashboard shell.
6. Commit as `feat: add frontend app shell`.

**Verification:**

```bash
cd frontend && npm run typecheck && npm run build
```

## Task 13: Frontend Upload Workflow

**Files:**

- Create: `frontend/src/pages/UploadPage.tsx`
- Create: `frontend/src/components/UploadDropzone.tsx`
- Create: `frontend/src/components/UploadQueue.tsx`
- Create: `frontend/src/lib/fileValidation.ts`
- Create: `frontend/src/__tests__/fileValidation.test.ts`

**Steps:**

1. Implement drag/drop and file picker.
2. Pre-warn for unsupported types, GIF, likely Base64 > 10MB, image dimensions.
3. Show upload queue states.
4. Poll OCR job status.
5. Show retry action for failed jobs.
6. Show active OCR quota warning/critical alert before batch upload starts.
7. Commit as `feat: add upload and recognition workflow`.

**Verification:**

```bash
cd frontend && npm test -- fileValidation
cd frontend && npm run build
```

## Task 14: Frontend Invoice Library And Detail

**Files:**

- Create: `frontend/src/pages/InvoiceListPage.tsx`
- Create: `frontend/src/pages/InvoiceDetailPage.tsx`
- Create: `frontend/src/components/InvoiceTable.tsx`
- Create: `frontend/src/components/InvoicePreview.tsx`
- Create: `frontend/src/components/FieldEditor.tsx`
- Create: `frontend/src/components/LineItemsEditor.tsx`

**Steps:**

1. Implement searchable filterable invoice table.
2. Implement saved views for common filters.
3. Implement detail page left preview/right field editor.
4. Preserve OCR original value and edited value.
5. Add confirm, archive, retry OCR actions.
6. Commit as `feat: add invoice library ui`.

**Verification:**

```bash
cd frontend && npm run typecheck && npm run build
```

## Task 15: E2E Mock Flow

**Files:**

- Create: `tests/e2e/docker-compose.e2e.yml`
- Create: `tests/e2e/invoice_flow.spec.ts`
- Create: `.github/workflows/ci.yml`

**Steps:**

1. Build linux/amd64 image.
2. Start app, worker, postgres, redis with mock OCR.
3. Create admin user.
4. Upload fixture invoice.
5. Wait for OCR completion.
6. Verify invoice fields, items, RequestId, export.
7. Restart containers and verify data persists.
8. Commit as `test: add e2e mock invoice flow`.

**Verification:**

```bash
docker compose -f tests/e2e/docker-compose.e2e.yml up --build --abort-on-container-exit
```

## Task 16: Security, Observability, And Release Hardening

**Files:**

- Modify: `Dockerfile`
- Modify: `docker-compose.yml`
- Create: `backend/app/api/routes/health.py`
- Create: `backend/app/core/audit.py`
- Create: `docs/operations/runbook.md`

**Steps:**

1. Ensure image runs as non-root.
2. Add `/healthz`, `/readyz`, optional `/metrics`.
3. Add audit logs for login, upload, OCR, correction, export, OCR provider config change, credential rotation, and quota threshold change.
4. Add secret redaction to all logs.
5. Add SBOM and vulnerability scanning in CI.
6. Add release checklist.
7. Commit as `chore: harden release operations`.

**Verification:**

```bash
docker inspect invoice-ocr-app:dev --format '{{.Config.User}}'
cd backend && pytest -v
```

## Final MVP Acceptance

- `docker buildx build --platform linux/amd64` succeeds.
- `docker compose up -d` starts app, worker, PostgreSQL, Redis.
- Admin configures Tencent Cloud OCR credentials in settings; `.env` and Docker `environment` do not contain SecretId/SecretKey.
- OCR provider model preserves future Aliyun adapter support.
- PNG/JPG/JPEG/PDF upload works.
- GIF, oversized Base64, invalid dimensions, multi-page PDF fail clearly.
- OCR jobs are async and limited to default 8 QPS, never exceeding 10 QPS.
- OCR results preserve raw JSON and normalized invoice/items.
- `RequestId` is visible to admins for troubleshooting.
- Free quota/resource package usage is visible and warning/critical alerts appear before configured thresholds are exhausted.
- Users can search, filter, correct, confirm, archive, and export invoices.
- Secrets never appear in logs, front-end responses, plaintext database fields, or exports.
- Unit, integration, E2E mock tests pass in CI.
- Release image is linux/amd64, scanned, tagged, and documented.
