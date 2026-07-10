# User Project Review Export Extension Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add first-admin bootstrap, fixed-role user administration, mixed shared/private projects, project-aware invoice workflows, complete review and export pages, and a production-quality authentication landing page.

**Architecture:** Extend the existing FastAPI/SQLAlchemy domain modules with focused system, user, and project services while preserving current invoice, OCR, and export behavior. Add one Alembic revision that backfills existing documents into an immutable uncategorized project. Put authentication state above the React app shell, then build role-aware operational pages using the existing hash router and API envelope.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2, Alembic, PostgreSQL, Redis/Celery, React 19, TypeScript, Vite, Vitest, Docker Compose.

---

### Task 1: First-Administrator Bootstrap And Versioned Sessions

**Files:**
- Create: `backend/app/domain/system/__init__.py`
- Create: `backend/app/domain/system/models.py`
- Create: `backend/app/domain/system/service.py`
- Modify: `backend/app/db/base.py`
- Modify: `backend/app/domain/user/models.py`
- Modify: `backend/app/domain/user/service.py`
- Modify: `backend/app/api/routes/auth.py`
- Modify: `backend/tests/test_auth.py`

**Step 1: Write failing bootstrap and session-version tests**

Add tests proving:

```python
def test_bootstrap_creates_only_first_admin(client, db_session):
    assert client.get("/api/v1/auth/bootstrap-status").json()["data"]["initialized"] is False
    created = client.post("/api/v1/auth/bootstrap", json={
        "email": "owner@example.com",
        "password": "strong-password-123",
        "display_name": "Owner",
    })
    assert created.status_code == 200
    assert created.json()["data"]["role"] == "admin"
    assert client.post("/api/v1/auth/bootstrap", json={...}).status_code == 409

def test_password_change_invalidates_previous_session(client, db_session):
    # Log in with two clients, change the password with one, and assert the other gets 401.
```

**Step 2: Run tests and verify RED**

Run:

```bash
cd backend
uv run --frozen --extra test pytest tests/test_auth.py -k "bootstrap or session_version or password_change" -v
```

Expected: FAIL because the endpoints, system state, and session version do not exist.

**Step 3: Implement minimal bootstrap and versioned sessions**

Implement:

```python
class SystemState(Base):
    __tablename__ = "system_state"
    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    initialized_at: Mapped[datetime | None]
    initialized_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

class User(...):
    session_version: Mapped[int] = mapped_column(default=1, nullable=False)
```

Add `session_version` to signed session payloads and reject mismatches. Add bootstrap status, transactional bootstrap, and authenticated password-change endpoints. Lock the singleton system-state row before checking whether users exist.

**Step 4: Run targeted and auth tests**

```bash
cd backend
uv run --frozen --extra test pytest tests/test_auth.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/app/domain/system backend/app/db/base.py backend/app/domain/user backend/app/api/routes/auth.py backend/tests/test_auth.py
git commit -m "feat: bootstrap first administrator"
```

### Task 2: Administrator User Management

**Files:**
- Create: `backend/app/api/routes/admin_users.py`
- Create: `backend/app/domain/user/admin_service.py`
- Create: `backend/tests/test_admin_users.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/core/audit.py` only if a shared audit helper is needed

**Step 1: Write failing user-management tests**

Cover list/create/update/reset behavior, ordinary-user denial, default `user` role, duplicate email, disabled login, and last-active-admin protection.

```python
def test_admin_created_user_defaults_to_user_role(admin_client):
    response = admin_client.post("/api/v1/admin/users", json={
        "email": "member@example.com",
        "password": "temporary-password",
        "display_name": "Member",
    })
    assert response.json()["data"]["role"] == "user"

def test_cannot_disable_last_active_admin(admin_client):
    response = admin_client.patch(f"/api/v1/admin/users/{admin_id}", json={"status": "disabled"})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "AUTH_LAST_ADMIN_REQUIRED"
```

**Step 2: Verify RED**

```bash
cd backend
uv run --frozen --extra test pytest tests/test_admin_users.py -v
```

Expected: FAIL with missing routes.

**Step 3: Implement admin user service and routes**

Return safe user DTOs containing id, email, display name, department, role, status, and timestamps. Use `require_role(UserRole.admin)`. Increment `session_version` for password resets. Record create, role change, status change, and password reset audits without storing plaintext passwords.

**Step 4: Run tests**

```bash
cd backend
uv run --frozen --extra test pytest tests/test_admin_users.py tests/test_auth.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/app/api/routes/admin_users.py backend/app/domain/user/admin_service.py backend/app/main.py backend/tests/test_admin_users.py
git commit -m "feat: manage users and roles"
```

### Task 3: Project Domain And Access Rules

**Files:**
- Create: `backend/app/domain/project/__init__.py`
- Create: `backend/app/domain/project/models.py`
- Create: `backend/app/domain/project/service.py`
- Create: `backend/app/api/routes/projects.py`
- Create: `backend/tests/test_projects.py`
- Modify: `backend/app/db/base.py`
- Modify: `backend/app/domain/user/models.py`
- Modify: `backend/app/main.py`

**Step 1: Write failing project tests**

Cover visible project sets, user-private creation, finance/admin shared creation, duplicate names, archive/restore, immutable uncategorized project, and forbidden private-project access.

```python
def test_normal_user_sees_shared_uncategorized_and_own_private_projects(...):
    response = user_client.get("/api/v1/projects")
    assert {item["name"] for item in response.json()["data"]} == {
        "未分类", "共享差旅", "我的采购"
    }

def test_normal_user_cannot_create_shared_project(user_client):
    response = user_client.post("/api/v1/projects", json={"name": "共享", "visibility": "shared"})
    assert response.status_code == 403
```

**Step 2: Verify RED**

```bash
cd backend
uv run --frozen --extra test pytest tests/test_projects.py -v
```

Expected: FAIL because the project model and routes are absent.

**Step 3: Implement project model, service, and API**

```python
class ProjectVisibility(str, enum.Enum):
    private = "private"
    shared = "shared"
    system = "system"

class ProjectStatus(str, enum.Enum):
    active = "active"
    archived = "archived"
```

Centralize `list_visible_projects()`, `assert_project_visible()`, `assert_project_assignable()`, and project-management permissions in the service. Never physically delete projects.

**Step 4: Run project and authorization tests**

```bash
cd backend
uv run --frozen --extra test pytest tests/test_projects.py tests/test_auth.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/app/domain/project backend/app/api/routes/projects.py backend/app/db/base.py backend/app/domain/user/models.py backend/app/main.py backend/tests/test_projects.py
git commit -m "feat: organize invoices with projects"
```

### Task 4: Project-Aware Upload, Invoice Queries, Movement, And Line Items

**Files:**
- Modify: `backend/app/domain/file/models.py`
- Modify: `backend/app/domain/invoice/models.py`
- Modify: `backend/app/domain/invoice/service.py`
- Modify: `backend/app/api/routes/documents.py`
- Modify: `backend/app/api/routes/invoices.py`
- Modify: `backend/tests/test_file_validation.py`
- Modify: `backend/tests/test_invoice_api.py`
- Create: `backend/tests/test_invoice_items.py`

**Step 1: Write failing integration tests**

Test upload defaults to uncategorized, explicit visible project assignment, private-project denial, project filtering, finance `uploaded_by` filtering, project movement, archived-project rejection, and line-item replacement with correction records.

```python
def test_upload_defaults_to_uncategorized_project(authenticated_client, seeded_projects):
    response = authenticated_client.post("/api/v1/documents", files={...})
    document = db.get(InvoiceDocument, UUID(response.json()["data"]["document_id"]))
    assert document.project.system_key == "uncategorized"

def test_replace_invoice_items_persists_corrections(...):
    response = client.put(f"/api/v1/invoices/{invoice.id}/items", json={"items": [...]})
    assert response.status_code == 200
```

**Step 2: Verify RED**

```bash
cd backend
uv run --frozen --extra test pytest tests/test_invoice_api.py tests/test_invoice_items.py -v
```

Expected: FAIL on missing project fields and items route.

**Step 3: Implement project-aware behavior**

Add `project_id` and relationship on `InvoiceDocument`. Accept `project_id` and persist `scene` during upload. Extend list/detail serialization with project summary. Extend invoice PATCH with `project_id`; validate visibility and active status before movement. Implement transactional item replacement or ID-aware upsert, validating decimal fields and recording correction/audit entries.

**Step 4: Run invoice, upload, duplicate, and export regressions**

```bash
cd backend
uv run --frozen --extra test pytest tests/test_invoice_api.py tests/test_invoice_items.py tests/test_file_validation.py tests/test_duplicate_detection.py tests/test_exports.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/app/domain/file/models.py backend/app/domain/invoice backend/app/api/routes/documents.py backend/app/api/routes/invoices.py backend/tests
git commit -m "feat: classify and correct project invoices"
```

### Task 5: Review Queue And Dashboard Summary APIs

**Files:**
- Create: `backend/app/domain/dashboard/__init__.py`
- Create: `backend/app/domain/dashboard/service.py`
- Create: `backend/app/api/routes/dashboard.py`
- Create: `backend/tests/test_dashboard.py`
- Create: `backend/tests/test_review_queue.py`
- Modify: `backend/app/api/routes/invoices.py`
- Modify: `backend/app/main.py`

**Step 1: Write failing dashboard and bulk-review tests**

Cover role-scoped counts, 30-day confirmed amount, queued OCR count, recent exports, review status filters, and bulk confirmation rejection for duplicates or inaccessible invoices.

```python
def test_dashboard_summary_uses_role_scoped_real_data(client):
    data = client.get("/api/v1/dashboard/summary").json()["data"]
    assert data["needs_review"] == 2
    assert data["ocr_failed"] == 1

def test_bulk_confirm_rejects_duplicate_suspected_invoice(client):
    response = client.post("/api/v1/invoices/bulk-confirm", json={"invoice_ids": [str(invoice.id)]})
    assert response.status_code == 409
```

**Step 2: Verify RED**

```bash
cd backend
uv run --frozen --extra test pytest tests/test_dashboard.py tests/test_review_queue.py -v
```

Expected: FAIL on missing routes.

**Step 3: Implement dashboard and bulk-confirm services**

Reuse existing owner-versus-finance/admin visibility rules. Keep the review list on the invoice list endpoint using real backend statuses. Add `POST /api/v1/invoices/bulk-confirm` before the UUID route and audit each confirmed invoice plus the batch operation.

**Step 4: Run tests**

```bash
cd backend
uv run --frozen --extra test pytest tests/test_dashboard.py tests/test_review_queue.py tests/test_invoice_api.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/app/domain/dashboard backend/app/api/routes/dashboard.py backend/app/api/routes/invoices.py backend/app/main.py backend/tests/test_dashboard.py backend/tests/test_review_queue.py
git commit -m "feat: add invoice review queue metrics"
```

### Task 6: Project-Aware Export Tasks And Safe Failure Status

**Files:**
- Modify: `backend/app/domain/export/models.py`
- Modify: `backend/app/domain/export/service.py`
- Modify: `backend/app/api/routes/exports.py`
- Modify: `backend/app/workers/tasks.py`
- Modify: `backend/tests/test_exports.py`

**Step 1: Write failing export tests**

Cover project filters, uploader filters for finance/admin, project columns and metadata, creator display name, safe failure message, and re-creating an export from previous filters.

```python
def test_export_filters_by_visible_project(...):
    task = create_and_run_export(filters={"project_id": str(project.id)})
    payload = json.loads(download(task))
    assert {row["project_name"] for row in payload["invoices"]} == {project.name}

def test_export_worker_records_safe_failure_message(...):
    assert failed_task.status == ExportStatus.failed
    assert "/data/" not in failed_task.error_message
```

**Step 2: Verify RED**

```bash
cd backend
uv run --frozen --extra test pytest tests/test_exports.py -v
```

Expected: FAIL on missing fields and filters.

**Step 3: Implement export extensions**

Add `error_message`, project/uploader filters, project columns, project metadata, creator summary, and safe worker failure handling. Keep download authorization unchanged.

**Step 4: Run export and worker tests**

```bash
cd backend
uv run --frozen --extra test pytest tests/test_exports.py tests/test_ocr_jobs.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/app/domain/export backend/app/api/routes/exports.py backend/app/workers/tasks.py backend/tests/test_exports.py
git commit -m "feat: export project invoice records"
```

### Task 7: Alembic Upgrade And Existing-Data Backfill

**Files:**
- Create: `backend/app/db/migrations/versions/<revision>_user_projects_workflows.py`
- Modify: `backend/tests/test_models.py`
- Create: `backend/tests/test_migration_upgrade.py`

**Step 1: Write a failing PostgreSQL migration test**

The test should start from the current `e5c7bce239f0` schema, insert an existing user/document/invoice, upgrade to head, and assert:

```python
assert upgraded_document.project_id is not None
assert uncategorized.system_key == "uncategorized"
assert upgraded_user.session_version == 1
```

**Step 2: Verify RED**

```bash
cd backend
TEST_DATABASE_URL=postgresql+psycopg://invoice_app:change-me@localhost:55432/invoice_app \
uv run --frozen --extra test pytest tests/test_migration_upgrade.py -v
```

Expected: FAIL because the revision does not exist.

**Step 3: Create the migration**

Create system state, projects, indexes and uniqueness constraints; add `users.session_version`, `invoice_documents.project_id`, and `export_tasks.error_message`; insert uncategorized; backfill documents; then make `project_id` non-null and add its foreign key.

Downgrade must remove the extension columns and tables in dependency order without changing the original revision.

**Step 4: Run migration and model tests**

```bash
cd backend
TEST_DATABASE_URL=postgresql+psycopg://invoice_app:change-me@localhost:55432/invoice_app \
uv run --frozen --extra test pytest tests/test_migration_upgrade.py tests/test_models.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/app/db/migrations/versions backend/tests/test_models.py backend/tests/test_migration_upgrade.py
git commit -m "feat: migrate users and invoice projects"
```

### Task 8: Authentication Landing Page And App Authentication Boundary

**Files:**
- Create: `frontend/src/auth/AuthContext.tsx`
- Create: `frontend/src/auth/authState.ts`
- Create: `frontend/src/pages/AuthLandingPage.tsx`
- Create: `frontend/src/components/UserMenu.tsx`
- Create: `frontend/src/__tests__/authState.test.ts`
- Create: `frontend/public/auth-invoice-workspace.webp`
- Modify: `frontend/src/app/App.tsx`
- Modify: `frontend/src/components/AppShell.tsx`
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/styles.css`
- Modify: `frontend/package.json`
- Modify: `frontend/package-lock.json`

**Step 1: Invoke frontend design guidance before implementation**

Use `@impeccable` for the authenticated product register and `@imagegen` to create one production bitmap asset showing an editorial overhead invoice scanning/archival workspace. Preserve the existing restrained product identity inside the application.

**Step 2: Write failing auth-state tests**

```typescript
describe("resolveAuthScreen", () => {
  it("shows bootstrap before the first user exists", () => {
    expect(resolveAuthScreen({ initialized: false, user: null })).toBe("bootstrap");
  });

  it("shows the workspace for an authenticated user", () => {
    expect(resolveAuthScreen({ initialized: true, user: admin })).toBe("workspace");
  });
});
```

**Step 3: Verify RED**

```bash
cd frontend
npm test -- authState
```

Expected: FAIL because auth state does not exist.

**Step 4: Implement auth boundary and landing page**

Load bootstrap status, then `/auth/me`; render loading, bootstrap, login, disabled/error, or workspace. Add user menu, own-password dialog, and logout. Map authentication error codes to Chinese copy. The hero uses a real bitmap background with readable text overlay and a compact form panel; it must work at desktop and mobile widths with reduced motion.

**Step 5: Run frontend tests and build**

```bash
cd frontend
npm test -- authState
npm run build
```

Expected: PASS.

**Step 6: Commit**

```bash
git add frontend
git commit -m "feat: add secure authentication landing"
```

### Task 9: User And Project Management Frontend

**Files:**
- Create: `frontend/src/pages/UserManagementPage.tsx`
- Create: `frontend/src/pages/ProjectManagementPage.tsx`
- Create: `frontend/src/components/UserEditorDialog.tsx`
- Create: `frontend/src/components/ProjectEditorDialog.tsx`
- Create: `frontend/src/lib/permissions.ts`
- Create: `frontend/src/lib/projects.ts`
- Create: `frontend/src/__tests__/permissions.test.ts`
- Create: `frontend/src/__tests__/projects.test.ts`
- Modify: `frontend/src/app/router.tsx`
- Modify: `frontend/src/components/AppShell.tsx`
- Modify: `frontend/src/styles.css`

**Step 1: Write failing permission and project-group tests**

Test role-aware navigation, allowed project creation modes, and shared/private/archived grouping.

**Step 2: Verify RED**

```bash
cd frontend
npm test -- permissions projects
```

Expected: FAIL because helpers and pages are missing.

**Step 3: Implement the pages**

Build compact tables and native dialogs for user creation/edit/reset and project create/edit/archive/restore. Use role and status text plus icons. Do not nest cards or expose controls the current role cannot use.

**Step 4: Run tests and build**

```bash
cd frontend
npm test -- permissions projects
npm run build
```

Expected: PASS.

**Step 5: Commit**

```bash
git add frontend/src
git commit -m "feat: add user and project administration ui"
```

### Task 10: Project-Aware Invoice Library, Upload, And Review UI

**Files:**
- Create: `frontend/src/pages/ReviewQueuePage.tsx`
- Create: `frontend/src/components/ProjectFilter.tsx`
- Create: `frontend/src/lib/invoiceStatus.ts`
- Create: `frontend/src/__tests__/invoiceStatus.test.ts`
- Modify: `frontend/src/pages/InvoiceListPage.tsx`
- Modify: `frontend/src/pages/InvoiceDetailPage.tsx`
- Modify: `frontend/src/pages/UploadPage.tsx`
- Modify: `frontend/src/components/InvoiceTable.tsx`
- Modify: `frontend/src/app/router.tsx`
- Modify: `frontend/src/styles.css`

**Step 1: Write failing status and review-action tests**

Test backend status labels, tab-to-filter mapping, bulk-confirm eligibility, and project option grouping.

```typescript
expect(reviewFilterForTab("duplicates")).toEqual({ status: "duplicate_suspected" });
expect(canBulkConfirm({ status: "needs_review", is_duplicate_suspected: false })).toBe(true);
```

**Step 2: Verify RED**

```bash
cd frontend
npm test -- invoiceStatus
```

Expected: FAIL.

**Step 3: Implement project-aware invoice workflows**

Add project side filtering and project column, upload project selection, detail project movement, corrected status labels, and real line-item save refresh. Build review tabs with counts, filters, row selection, guarded bulk confirm, retry, and detail actions.

**Step 4: Run tests and build**

```bash
cd frontend
npm test -- invoiceStatus fileValidation
npm run build
```

Expected: PASS.

**Step 5: Commit**

```bash
git add frontend/src
git commit -m "feat: complete project invoice review workflow"
```

### Task 11: Export Records And Live Dashboard Frontend

**Files:**
- Create: `frontend/src/pages/ExportRecordsPage.tsx`
- Create: `frontend/src/lib/exportTasks.ts`
- Create: `frontend/src/__tests__/exportTasks.test.ts`
- Modify: `frontend/src/pages/DashboardPage.tsx`
- Modify: `frontend/src/app/router.tsx`
- Modify: `frontend/src/styles.css`

**Step 1: Write failing export-state tests**

Test status labels, polling eligibility, download eligibility, expiry, and recreating a task payload from previous filters.

**Step 2: Verify RED**

```bash
cd frontend
npm test -- exportTasks
```

Expected: FAIL.

**Step 3: Implement export records and live metrics**

Build the export creation controls and task table. Poll only queued/running tasks, allow download only for completed non-expired tasks, and create a fresh task for re-export. Replace Dashboard constants with `/dashboard/summary` data and role-appropriate recent activity.

**Step 4: Run frontend verification**

```bash
cd frontend
npm test
npm run build
```

Expected: all frontend tests and production build PASS.

**Step 5: Commit**

```bash
git add frontend/src
git commit -m "feat: complete exports and dashboard"
```

### Task 12: End-To-End, Docker, Migration, And Browser Verification

**Files:**
- Modify: `tests/e2e/invoice_flow.spec.ts`
- Modify: `tests/e2e/docker-compose.e2e.yml`
- Modify: `tests/e2e/run.sh`
- Modify: `.github/workflows/ci.yml` if migration coverage needs a separate service step
- Modify: `README.md`
- Modify: `docs/operations/runbook.md`
- Modify: `docs/deployment/linux-amd64-docker-deployment.md`

**Step 1: Extend E2E assertions before production changes are considered complete**

Cover:

1. First-admin bootstrap without CLI user creation.
2. Admin-created ordinary user.
3. Shared and private project creation and visibility.
4. Upload into a project and default uncategorized fallback.
5. Mock OCR completion and line-item correction.
6. Review confirmation.
7. Project-filtered export and download.
8. Restart with persistence checks.

**Step 2: Run full backend verification**

```bash
cd backend
uv run --frozen --extra test pytest -v
```

Expected: all tests PASS, with only the documented optional PostgreSQL skip when no test URL is provided.

**Step 3: Run frontend verification**

```bash
cd frontend
npm test
npm run build
```

Expected: PASS.

**Step 4: Run Docker E2E**

```bash
tests/e2e/run.sh
```

Expected: bootstrap, user, project, OCR, review, export, and persistence checks PASS.

**Step 5: Build and inspect the release image**

```bash
docker buildx build --platform linux/amd64 --load -t invoice-ocr-app:0.2.0 .
docker inspect invoice-ocr-app:0.2.0 --format '{{.Config.User}} {{.Architecture}}'
```

Expected: `invoice amd64`.

**Step 6: Upgrade the running local stack and smoke test**

```bash
INVOICE_OCR_IMAGE=invoice-ocr-app:0.2.0 docker compose run --rm app migrate
INVOICE_OCR_IMAGE=invoice-ocr-app:0.2.0 docker compose up -d
curl -fsS http://localhost:8080/healthz
curl -fsS http://localhost:8080/readyz
```

Expected: healthy application, database, Redis, and worker.

**Step 7: Browser QA**

Use the in-app browser to verify login/bootstrap, user management, projects, upload, invoices, review, exports, and Dashboard at desktop and mobile viewports. Confirm no overflow, overlap, clipped menus, inaccessible controls, console errors, or blank generated image.

**Step 8: Update operational documentation and commit**

```bash
git add tests/e2e .github/workflows/ci.yml README.md docs/operations docs/deployment
git commit -m "test: verify user project review export workflows"
```

### Task 13: Final Review And Release Readiness

**Files:**
- Review all changed files
- Update: `task_plan.md`, `findings.md`, `progress.md` (ignored working records)

**Step 1: Inspect repository state**

```bash
git status --short --branch
git log --oneline --decorate -15
```

**Step 2: Re-run fresh verification**

Run the full backend suite, frontend suite/build, Docker E2E, Compose health checks, and browser checks again after the final edit.

**Step 3: Review security invariants**

Confirm no plaintext passwords, session tokens, OCR credentials, internal paths, or stack traces appear in API responses, audit metadata, logs, `.env.example`, fixtures, or committed files.

**Step 4: Review requirements line by line**

Compare the implementation against `docs/plans/2026-07-10-user-project-review-export-design.md` and record any intentionally deferred item before claiming completion.

**Step 5: Commit final documentation-only corrections if needed**

```bash
git add <reviewed-files>
git commit -m "chore: finalize extended invoice workflows"
```
