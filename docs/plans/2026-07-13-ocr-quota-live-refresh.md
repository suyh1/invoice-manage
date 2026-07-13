# OCR Quota Live Refresh Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Count every OCR provider call against quota and refresh all visible quota indicators as soon as each provider attempt returns.

**Architecture:** Keep quota as backend-owned state. Publish a browser event when frontend OCR polling observes a returned provider attempt, and make every shared quota component reload on that event. Add a reusable bounded watcher for retry flows that currently enqueue OCR without polling the result.

**Tech Stack:** Python, SQLAlchemy, pytest, React 19, TypeScript, Vitest, Testing Library.

---

### Task 1: Count failed provider calls against quota

**Files:**
- Modify: `backend/tests/test_ocr_quota_alerts.py`
- Modify: `backend/app/domain/ocr/quota.py`

**Step 1: Write the failing billing test**

Add a test that starts a provider at 79/100, records a failed provider call, and asserts:

```python
assert usage.successful_calls == 0
assert usage.failed_calls == 1
assert usage.estimated_billable_calls == 1
assert provider.free_quota_used == 80
```

**Step 2: Run the test to verify RED**

Run: `cd backend && uv run pytest tests/test_ocr_quota_alerts.py -q`

Expected: FAIL because failed calls currently leave billable usage and used quota unchanged.

**Step 3: Implement the minimal billing change**

Keep success/failure counters conditional, but move billable and quota increments outside the success branch:

```python
if success:
    usage.successful_calls += 1
else:
    usage.failed_calls += 1
usage.estimated_billable_calls += 1
if provider_config.free_quota_used is not None:
    provider_config.free_quota_used += 1
```

**Step 4: Run the focused tests to verify GREEN**

Run: `cd backend && uv run pytest tests/test_ocr_quota_alerts.py tests/test_ocr_jobs.py::test_process_ocr_job_schedules_retry_for_retryable_provider_error tests/test_ocr_jobs.py::test_process_ocr_job_marks_final_failure_for_non_retryable_error -q`

Expected: all focused tests pass.

**Step 5: Commit**

```bash
git add backend/app/domain/ocr/quota.py backend/tests/test_ocr_quota_alerts.py
git commit -m "fix: count failed OCR calls against quota"
```

### Task 2: Refresh every mounted quota component from a shared event

**Files:**
- Create: `frontend/src/lib/ocrQuotaRefresh.ts`
- Modify: `frontend/src/components/OcrQuotaStatus.tsx`
- Modify: `frontend/src/__tests__/OcrQuotaStatus.test.tsx`

**Step 1: Write failing component refresh tests**

Mock sequential quota responses and render two `OcrQuotaStatus` instances. After the initial `250/1000` response, publish the shared refresh event and assert both instances request again and render `251/1000`.

Add focused tests that dispatch window focus and a visible `visibilitychange`, asserting each causes a reload.

**Step 2: Run the component tests to verify RED**

Run: `cd frontend && npm test -- OcrQuotaStatus.test.tsx`

Expected: FAIL because no refresh module or event listener exists.

**Step 3: Implement the shared refresh event**

Create:

```ts
export const OCR_QUOTA_REFRESH_EVENT = "invoice-ocr:quota-refresh";

export function notifyOcrQuotaRefresh() {
  window.dispatchEvent(new Event(OCR_QUOTA_REFRESH_EVENT));
}
```

Refactor the component effect to use one request-versioned `loadQuota` function. Call it on mount and on the shared event, window focus, and visible document state. Remove all listeners on unmount.

**Step 4: Run the component tests to verify GREEN**

Run: `cd frontend && npm test -- OcrQuotaStatus.test.tsx`

Expected: all component tests pass.

**Step 5: Commit**

```bash
git add frontend/src/lib/ocrQuotaRefresh.ts frontend/src/components/OcrQuotaStatus.tsx frontend/src/__tests__/OcrQuotaStatus.test.tsx
git commit -m "feat: refresh OCR quota indicators on demand"
```

### Task 3: Observe provider-result statuses once per OCR attempt

**Files:**
- Create: `frontend/src/lib/ocrJobQuotaWatcher.ts`
- Create: `frontend/src/__tests__/ocrJobQuotaWatcher.test.ts`

**Step 1: Write failing watcher tests**

Test a pure result observer and the bounded watcher with injected request/wait functions:

- `completed` attempt 1 publishes once;
- `failed_final` attempt 1 publishes once;
- `retry_scheduled` attempt 1 publishes, repeated polls for attempt 1 do not, and attempt 2 publishes again;
- `queued`, `running`, and `canceled` do not publish;
- terminal statuses stop polling;
- request failures stop quietly.

**Step 2: Run the watcher tests to verify RED**

Run: `cd frontend && npm test -- ocrJobQuotaWatcher.test.ts`

Expected: FAIL because the watcher module does not exist.

**Step 3: Implement the watcher**

Define the shared snapshot type:

```ts
export type OcrJobQuotaSnapshot = {
  attempt_count: number;
  status: string;
};
```

Use provider-result statuses `completed`, `failed_final`, `failed`, and `retry_scheduled`. Deduplicate notifications by increasing `attempt_count`. Treat `completed`, `failed_final`, `failed`, and `canceled` as terminal. Poll at the upload page's existing 1s initial and 2.5s subsequent intervals, bounded to 24 checks.

**Step 4: Run the watcher tests to verify GREEN**

Run: `cd frontend && npm test -- ocrJobQuotaWatcher.test.ts`

Expected: all watcher tests pass.

**Step 5: Commit**

```bash
git add frontend/src/lib/ocrJobQuotaWatcher.ts frontend/src/__tests__/ocrJobQuotaWatcher.test.ts
git commit -m "feat: watch OCR attempts for quota changes"
```

### Task 4: Connect upload and retry flows to quota refresh

**Files:**
- Modify: `frontend/src/pages/UploadPage.tsx`
- Modify: `frontend/src/pages/InvoiceDetailPage.tsx`
- Modify: `frontend/src/pages/ReviewQueuePage.tsx`
- Modify: `frontend/src/__tests__/InvoiceDetailPage.test.tsx`
- Create: `frontend/src/__tests__/ocrQuotaRefreshIntegration.test.ts`

**Step 1: Write failing integration tests**

Add an invoice-detail test with an OCR job that clicks `重新识别`, then asserts the retry endpoint is called and `watchOcrJobQuota(jobId)` starts.

Add a narrow source integration test that asserts:

- `UploadPage` calls `refreshQuotaForOcrJob` inside its polling loop;
- `ReviewQueuePage` calls `watchOcrJobQuota` after retry submission.

**Step 2: Run the integration tests to verify RED**

Run: `cd frontend && npm test -- InvoiceDetailPage.test.tsx ocrQuotaRefreshIntegration.test.ts`

Expected: FAIL because the pages are not connected to the refresh utilities.

**Step 3: Implement the page integrations**

In `UploadPage`, extend the job response type with `attempt_count`, keep a `lastQuotaRefreshAttempt` local to each polling loop, and pass every fetched snapshot through `refreshQuotaForOcrJob` before terminal handling.

In invoice detail and review queue, call `void watchOcrJobQuota(jobId)` only after the retry endpoint succeeds.

**Step 4: Run focused frontend tests to verify GREEN**

Run: `cd frontend && npm test -- OcrQuotaStatus.test.tsx ocrJobQuotaWatcher.test.ts InvoiceDetailPage.test.tsx ocrQuotaRefreshIntegration.test.ts UploadPage.test.tsx`

Expected: all focused tests pass.

**Step 5: Commit**

```bash
git add frontend/src/pages/UploadPage.tsx frontend/src/pages/InvoiceDetailPage.tsx frontend/src/pages/ReviewQueuePage.tsx frontend/src/__tests__/InvoiceDetailPage.test.tsx frontend/src/__tests__/ocrQuotaRefreshIntegration.test.ts
git commit -m "feat: refresh OCR quota after provider results"
```

### Task 5: Full verification

**Files:**
- Verify only.

**Step 1: Run backend feature and regression tests**

Run: `cd backend && uv run pytest tests/test_ocr_quota_alerts.py tests/test_ocr_quota_status_api.py tests/test_ocr_jobs.py -q`

Expected: quota tests pass. If the known stale `Amount` fixture failure remains, report it separately and verify all other selected tests with that case deselected.

**Step 2: Run all frontend tests and build**

Run: `cd frontend && npm test && npm run build`

Expected: all frontend tests and production build pass.

**Step 3: Verify the live workflow**

Run the local application with a temporary mock provider and quota. Submit an OCR job, observe its returned status, and verify the sidebar and page indicator update without reload. Repeat with a failing provider response if the local mock supports it; otherwise rely on the backend failure test and frontend watcher tests for that branch.

**Step 4: Check repository state**

Run: `git diff --check && git status --short`

Expected: no whitespace errors and no uncommitted changes.
