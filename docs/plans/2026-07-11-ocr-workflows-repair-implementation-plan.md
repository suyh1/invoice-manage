# OCR Workflows Repair Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make OCR configurations independently manageable, correct quota feedback, fix multipart uploads, and streamline settings/upload workflows.

**Architecture:** Keep the existing FastAPI, SQLAlchemy, React, and native-dialog patterns. Make OCR jobs provider-independent and resolve the unique active configuration at worker execution time, preserve only execution snapshots on jobs, expose focused lifecycle APIs, and separate page-level and row-level UI state.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2, Alembic, Pytest, React 19, TypeScript, Vitest, Testing Library, Vite.

---

### Task 1: Correct multipart API requests

**Files:**
- Modify: `frontend/src/lib/api.ts`
- Create: `frontend/src/__tests__/api.test.ts`

1. Write a failing Vitest test that calls `apiPostForm` and asserts `fetch` receives `FormData` without an explicit `content-type` header.
2. Run `cd frontend && npm test -- src/__tests__/api.test.ts` and confirm it fails because the header is `application/json`.
3. Change `apiRequest` to add JSON content type only for non-`FormData` bodies and parse FastAPI `detail` responses into a useful message.
4. Re-run the focused test and the existing file-validation tests.

### Task 2: Enforce quota semantics and refresh alerts

**Files:**
- Modify: `backend/app/api/routes/admin_ocr.py`
- Modify: `backend/app/domain/ocr/provider_config.py`
- Modify: `backend/app/domain/ocr/quota.py`
- Modify: `backend/tests/test_admin_ocr_provider_api.py`
- Modify: `backend/tests/test_ocr_quota_alerts.py`

1. Add failing tests for total 1000/used 4 producing remaining 996 without an alert, rejecting used greater than total, and refreshing an existing warning snapshot.
2. Run the focused Pytest cases and confirm the new assertions fail.
3. Add typed quota validation at the API boundary and update same-level active alerts in place.
4. Re-run the focused tests.

### Task 3: Make OCR jobs provider-independent and configurations deletable

**Files:**
- Create: `backend/app/db/migrations/versions/<revision>_decouple_ocr_provider_configs.py`
- Modify: `backend/app/domain/ocr/models.py`
- Modify: `backend/app/domain/ocr/provider_config.py`
- Modify: `backend/app/api/routes/admin_ocr.py`
- Modify: `backend/app/api/routes/ocr_jobs.py`
- Modify: `backend/app/workers/tasks.py`
- Modify: `backend/tests/test_admin_ocr_provider_api.py`
- Modify: `backend/tests/test_ocr_jobs.py`
- Modify: `backend/tests/test_migration_upgrade.py`

1. Add failing tests proving job creation succeeds without binding a provider, a queued job uses the configuration active when the worker starts, and a retry uses a newly activated configuration without user intervention.
2. Add failing tests proving a configuration can be deleted without changing queued or historical jobs and activating one configuration deactivates all others.
3. Run focused tests and confirm failure under the current job foreign key, upload-time binding, and missing DELETE route.
4. Add an Alembic migration removing `ocr_jobs.provider_config_id` and making provider snapshot columns nullable before first execution.
5. Move active-provider lookup and snapshot assignment into the worker attempt, handle no-active-provider as retryable, and make usage recording tolerate a configuration deleted while an attempt is in flight.
6. Add service deletion, DELETE API/audit logging, and single-active behavior.
7. Re-run model, migration, provider API, document upload, and OCR job tests.

### Task 4: Build provider management dialogs

**Files:**
- Create: `frontend/src/components/OcrProviderDialog.tsx`
- Rewrite: `frontend/src/components/OcrProviderSettings.tsx`
- Modify: `frontend/src/pages/SettingsPage.tsx`
- Modify: `frontend/src/lib/api.ts`
- Create: `frontend/src/__tests__/OcrProviderSettings.test.tsx`

1. Add failing Testing Library cases for opening add/view/edit dialogs, activating, deleting, editing without replacing credentials, and row-scoped connection-test feedback.
2. Run the focused test and confirm the current flat form and missing actions fail.
3. Add `apiDelete`, dialog actions, isolated row operation state, quota summaries, and accessible confirmation behavior.
4. Re-run the focused tests.

### Task 5: Show active-provider quota state

**Files:**
- Modify: `frontend/src/components/OcrQuotaStatus.tsx`
- Create: `frontend/src/__tests__/OcrQuotaStatus.test.tsx`

1. Add a failing test with alerts from two providers proving only the active provider is presented with its display name and current values.
2. Add the provider identifier/display name needed to the alert response or derive the status from the provider list.
3. Implement loading, no-active-provider, normal, warning, and critical states.
4. Re-run the focused tests.

### Task 6: Restructure the upload workflow

**Files:**
- Modify: `frontend/src/pages/UploadPage.tsx`
- Modify: `frontend/src/components/UploadDropzone.tsx`
- Modify: `frontend/src/components/UploadQueue.tsx`
- Create: `frontend/src/__tests__/UploadPage.test.tsx`

1. Add failing tests for the three stages, validated-file transition, upload request fields, detailed 422 messages, retry behavior, and disabled actions while busy.
2. Implement staged progressive disclosure while preserving multi-file validation and polling.
3. Re-run upload and file-validation tests.

### Task 7: Apply focused visual polish

**Files:**
- Modify: `frontend/src/styles.css`

1. Reuse existing dialog and management-page tokens for provider dialogs and upload stages.
2. Keep cards limited to actual records/dialogs, align actions, add stable responsive grids, visible focus states, compact quota treatment, and mobile-safe text wrapping.
3. Run frontend typecheck, tests, and build.

### Task 8: End-to-end verification

**Files:**
- Modify as needed: `tests/e2e/invoice_flow.spec.ts`

1. Add or update E2E coverage for provider create/activate/edit/test/delete and PDF upload.
2. Run `cd backend && uv run --frozen --extra test pytest -v`.
3. Run `cd frontend && npm test && npm run build`.
4. Run migration upgrade tests and the isolated E2E suite when Docker is available.
5. Start the local application and verify settings/upload at desktop and mobile widths in the in-app browser.
