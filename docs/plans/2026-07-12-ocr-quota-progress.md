# OCR Quota Progress Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Show used OCR quota against total quota as a shared black-or-red progress bar in the sidebar and upload page.

**Architecture:** Add a small authenticated quota status endpoint that reads the enabled default OCR provider and exposes only presentation-safe quota fields. Update the existing shared `OcrQuotaStatus` React component to consume that endpoint, so both current placements receive the same behavior and styling.

**Tech Stack:** FastAPI, SQLAlchemy, pytest, React 19, TypeScript, Vitest, Testing Library, CSS.

---

### Task 1: Authenticated OCR quota status endpoint

**Files:**
- Create: `backend/app/api/routes/ocr_quota.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_ocr_quota_status_api.py`

**Step 1: Write the failing endpoint tests**

Add tests that create an ordinary authenticated user and an enabled default provider. Assert `GET /api/v1/ocr-quota/status` returns:

```python
{
    "data": {
        "quota_total": 1000,
        "quota_used": 250,
        "used_percent": 25,
        "level": "none",
    }
}
```

Add a threshold case with `free_quota_used=800` and `quota_warning_percent=80`, expecting `level == "warning"`. Add an unconfigured case expecting all quota numbers to be null and `level == "none"`.

**Step 2: Run the endpoint tests to verify RED**

Run: `cd backend && uv run pytest tests/test_ocr_quota_status_api.py -q`

Expected: FAIL with 404 because the route does not exist.

**Step 3: Implement the minimal endpoint**

Create an `APIRouter` at `/api/v1/ocr-quota`. The `/status` handler must require `get_current_user`, select the enabled default `OcrProviderConfig`, and return null values when no matching config exists. When it exists, call `quota_snapshot(config)` and return only:

```python
{
    "quota_total": snapshot["free_quota_total"],
    "quota_used": snapshot["free_quota_used"],
    "used_percent": snapshot["used_percent"],
    "level": snapshot["alert_level"],
}
```

Register the router in `backend/app/main.py`.

**Step 4: Run the endpoint tests to verify GREEN**

Run: `cd backend && uv run pytest tests/test_ocr_quota_status_api.py -q`

Expected: all tests pass.

**Step 5: Commit the endpoint**

```bash
git add backend/app/api/routes/ocr_quota.py backend/app/main.py backend/tests/test_ocr_quota_status_api.py
git commit -m "feat: expose OCR quota status"
```

### Task 2: Shared quota progress component

**Files:**
- Modify: `frontend/src/components/OcrQuotaStatus.tsx`
- Create: `frontend/src/__tests__/OcrQuotaStatus.test.tsx`

**Step 1: Write the failing component tests**

Mock the status endpoint and assert the component:

- renders `250/1000`;
- exposes a progressbar with value 250 and maximum 1000;
- gives the fill a `25%` width in the normal state;
- applies the warning class and an `80%` fill for a warning response;
- clamps an oversized percentage to `100%`;
- renders `--/--` and no numeric progressbar when values are unavailable.

**Step 2: Run the component tests to verify RED**

Run: `cd frontend && npm test -- OcrQuotaStatus.test.tsx`

Expected: FAIL because the current component requests the alert endpoint and renders reminder copy instead of a progressbar.

**Step 3: Implement the minimal component**

Replace the alert-list state with the quota status response. Request `/api/v1/ocr-quota/status`, clamp the numeric percentage to 0-100, and render:

```tsx
<div className="quota-progress-row">
  <div className="quota-progress-track" role="progressbar">
    <span className="quota-progress-fill" style={{ width: `${usedPercent}%` }} />
  </div>
  <strong className="quota-progress-value">{quotaLabel}</strong>
</div>
```

Only attach numeric progressbar semantics when total and used values are present. Use warning or critical as the component level; failed, loading, and missing data render the empty fallback without reminder prose.

**Step 4: Run the component tests to verify GREEN**

Run: `cd frontend && npm test -- OcrQuotaStatus.test.tsx`

Expected: all tests pass.

**Step 5: Commit the component**

```bash
git add frontend/src/components/OcrQuotaStatus.tsx frontend/src/__tests__/OcrQuotaStatus.test.tsx
git commit -m "feat: render OCR quota progress"
```

### Task 3: Progress bar visual system and responsive layout

**Files:**
- Modify: `frontend/src/styles.css`

**Step 1: Add a source-level failing visual contract test**

Extend `frontend/src/__tests__/authenticatedVisualSystem.test.tsx` to assert the stylesheet includes the quota track, fill, value, and warning/critical red-fill selectors.

**Step 2: Run the visual contract test to verify RED**

Run: `cd frontend && npm test -- authenticatedVisualSystem.test.tsx`

Expected: FAIL because the new progress selectors are absent.

**Step 3: Implement the styles**

Add a stable two-column progress row with a flexible track and fixed-width value. The track uses a transparent background and black border. The fill uses black normally and the existing critical red token for warning and critical states. Remove obsolete quota reminder and definition-list layout rules. Preserve the sidebar's borderless container and upload header's framed container, and ensure the value cannot wrap or overflow.

**Step 4: Run focused frontend tests to verify GREEN**

Run: `cd frontend && npm test -- OcrQuotaStatus.test.tsx authenticatedVisualSystem.test.tsx UploadPage.test.tsx`

Expected: all tests pass.

**Step 5: Commit the styles**

```bash
git add frontend/src/styles.css frontend/src/__tests__/authenticatedVisualSystem.test.tsx
git commit -m "style: refine OCR quota progress"
```

### Task 4: Full verification

**Files:**
- Verify only.

**Step 1: Run backend regression tests**

Run: `cd backend && uv run pytest -q`

Expected: all backend tests pass.

**Step 2: Run frontend tests**

Run: `cd frontend && npm test`

Expected: all frontend tests pass.

**Step 3: Run frontend production checks**

Run: `cd frontend && npm run build`

Expected: TypeScript checks and Vite production build complete successfully.

**Step 4: Run repository diff checks**

Run: `git diff --check && git status --short`

Expected: no whitespace errors and only intentional files, if any, remain uncommitted.

**Step 5: Verify the interface in the browser**

Start the local application using the repository's documented development command. Inspect the sidebar and upload page at desktop and narrow widths. Confirm the track is hollow, the used portion is black below threshold, warning/critical fill is red, the ratio stays to the right, and no text overlaps.
