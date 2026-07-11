# Project Files and ZIP Export Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add non-OCR project file management and ZIP exports containing project invoice originals and ordinary files.

**Architecture:** Reuse `invoice_documents` with an explicit document kind, split OCR and project-file validation profiles, and extend the existing asynchronous export task pipeline for ZIP packages. Keep permissions aligned with current document and invoice access rules.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, Celery, PostgreSQL/SQLite tests, React 19, TypeScript, Vitest, vanilla CSS.

---

### Task 1: Document kind migration and model

**Files:**
- Create: `backend/app/db/migrations/versions/<revision>_project_document_kind.py`
- Modify: `backend/app/domain/file/models.py`
- Test: `backend/tests/test_migration_upgrade.py`
- Test: `backend/tests/test_models.py`

**Steps:**

1. Add failing tests requiring `invoice_documents.document_kind`, an `invoice` default for existing rows, and enum values `invoice` and `project_file`.
2. Run the focused tests and confirm they fail.
3. Add `DocumentKind`, the model column, and an Alembic migration that backfills existing rows as `invoice` before making the column non-null.
4. Re-run the focused tests and confirm they pass.

### Task 2: Project-file validation and upload

**Files:**
- Modify: `backend/app/core/config.py`
- Modify: `backend/app/domain/file/validators.py`
- Modify: `backend/app/api/routes/documents.py`
- Test: `backend/tests/test_file_validation.py`

**Steps:**

1. Add failing tests for PDF/PNG/JPEG/DOCX/XLSX project files, extension/content mismatches, executable rejection, and the 50 MiB limit.
2. Add failing upload tests asserting `document_kind=project_file` creates no OCR job and stores no scene.
3. Run the focused tests and confirm the new cases fail.
4. Introduce `validate_project_file_upload` while preserving the stricter OCR validator.
5. Parse DOCX/XLSX ZIP packages using `zipfile` and required package paths.
6. Accept `document_kind` in the upload route and force project files to skip OCR.
7. Re-run the focused tests and confirm they pass.

### Task 3: Project-file list and soft delete API

**Files:**
- Modify: `backend/app/api/routes/documents.py`
- Modify: `backend/app/api/dependencies.py` if a shared access helper is needed
- Test: `backend/tests/test_file_validation.py`

**Steps:**

1. Add failing tests for project filtering, owner/finance visibility, serialized metadata, and soft deletion.
2. Add failing tests preventing ordinary users from deleting another user's file and preventing invoice deletion through the project-file endpoint.
3. Implement `GET /api/v1/documents` and `DELETE /api/v1/documents/{id}` with shared access checks and audit logs.
4. Re-run the focused tests and confirm they pass.

### Task 4: Upload mode frontend

**Files:**
- Modify: `frontend/src/pages/UploadPage.tsx`
- Modify: `frontend/src/components/UploadDropzone.tsx`
- Modify: `frontend/src/components/UploadQueue.tsx`
- Modify: `frontend/src/lib/fileValidation.ts`
- Modify: `frontend/src/styles.css`
- Test: `frontend/src/__tests__/fileValidation.test.ts`
- Create: `frontend/src/__tests__/UploadPage.test.tsx`

**Steps:**

1. Add failing validation tests for the project-file formats and 50 MiB limit.
2. Add failing page tests for the segmented mode, hidden OCR/scene controls, and multipart `document_kind=project_file` payload.
3. Run focused tests and confirm they fail.
4. Add separate frontend validation profiles and mode-specific copy.
5. Implement the segmented upload mode and mode-aware queue status text.
6. Re-run focused tests and confirm they pass.

### Task 5: Project files in the invoice archive

**Files:**
- Create: `frontend/src/components/ProjectFileTable.tsx`
- Modify: `frontend/src/pages/InvoiceListPage.tsx`
- Modify: `frontend/src/styles.css`
- Create: `frontend/src/__tests__/ProjectFileTable.test.tsx`
- Modify: `frontend/src/__tests__/invoiceWorkbench.test.ts`

**Steps:**

1. Add failing tests for `发票 / 项目文件` views, project-aware loading, metadata columns, download, empty state, and delete confirmation.
2. Run focused tests and confirm they fail.
3. Implement the view control, project-file API loading, table, and soft-delete refresh.
4. Keep the project index and archive inside the existing workspace at all breakpoints.
5. Re-run focused tests and confirm they pass.

### Task 6: ZIP export backend

**Files:**
- Modify: `backend/app/api/routes/exports.py`
- Modify: `backend/app/domain/export/service.py`
- Modify: `backend/app/workers/tasks.py`
- Test: `backend/tests/test_exports.py`

**Steps:**

1. Add failing API tests requiring `project_id` for ZIP exports.
2. Add failing service tests for the two archive folders, manifest fields, duplicate names, permission filtering, and missing source failure.
3. Run focused export tests and confirm they fail.
4. Pass the upload storage root into export execution and select visible documents by project and kind.
5. Implement safe ZIP paths, deterministic collision suffixes, and `manifest.json`.
6. Re-run focused export tests and confirm they pass.

### Task 7: ZIP export frontend

**Files:**
- Modify: `frontend/src/pages/ExportRecordsPage.tsx`
- Modify: `frontend/src/lib/exportTasks.ts`
- Modify: `frontend/src/styles.css`
- Test: `frontend/src/__tests__/exportTasks.test.ts`
- Create: `frontend/src/__tests__/ExportRecordsPage.test.tsx`

**Steps:**

1. Add failing tests for the ZIP option, mandatory project selection, hidden invoice-only options, labels, and re-export payloads.
2. Run focused tests and confirm they fail.
3. Add the ZIP format to frontend types and render mode-aware controls.
4. Send `scope=project_files` with the selected project and display `项目文件包` in records.
5. Re-run focused tests and confirm they pass.

### Task 8: Full verification and runtime update

**Files:**
- Verify only

**Steps:**

1. Run `npm test -- --run` and `npm run build` from `frontend`.
2. Run focused backend suites for migrations, files, exports, and permissions.
3. Run the full backend suite and record the known baseline OCR item-mapping failure separately if it remains unchanged.
4. Build `invoice-ocr-local:dev`, recreate app and worker containers, and wait for health.
5. Use the in-app browser to verify project-file upload, project-file listing/download/delete, ZIP creation/download, and desktop/mobile overflow.
