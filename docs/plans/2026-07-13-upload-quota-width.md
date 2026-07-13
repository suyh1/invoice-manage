# Upload OCR Quota Width Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make the upload-page OCR quota panel fill its heading grid column so its desktop width matches the settings-page panel.

**Architecture:** Preserve the shared quota component and existing heading grid. Add one upload-page-scoped CSS override that replaces the percentage-within-grid width with `100%`, while retaining current responsive behavior.

**Tech Stack:** React, CSS, Vitest, Vite, in-app browser verification.

---

### Task 1: Align upload quota panel width

**Files:**
- Modify: `frontend/src/__tests__/authenticatedVisualSystem.test.tsx`
- Modify: `frontend/src/styles.css`

**Step 1: Write the failing visual contract test**

Extend the OCR quota visual-system test to require this scoped rule:

```css
.upload-editorial .editorial-page-heading .quota-status.compact {
  width: 100%;
}
```

The test should continue to require the existing shared progress and threshold selectors.

**Step 2: Run the test to verify RED**

Run: `cd frontend && npm test -- authenticatedVisualSystem.test.tsx`

Expected: FAIL because the upload-specific full-column width rule is absent.

**Step 3: Implement the minimal CSS fix**

Immediately after the shared editorial quota-panel rule, add:

```css
.upload-editorial .editorial-page-heading .quota-status.compact {
  width: 100%;
}
```

Do not change component markup, settings-page sizing, sidebar sizing, or responsive breakpoints.

**Step 4: Run focused tests to verify GREEN**

Run: `cd frontend && npm test -- authenticatedVisualSystem.test.tsx OcrQuotaStatus.test.tsx UploadPage.test.tsx`

Expected: all focused tests pass.

**Step 5: Run production verification**

Run: `cd frontend && npm test && npm run build`

Expected: all frontend tests and the production build pass.

**Step 6: Verify desktop and narrow layouts**

Run the current local app and inspect the upload and settings pages in the in-app browser. At a wide desktop viewport, confirm both quota panels measure 360px. At 390px, confirm the upload quota panel remains full width without horizontal overflow.

**Step 7: Commit**

```bash
git add frontend/src/styles.css frontend/src/__tests__/authenticatedVisualSystem.test.tsx
git commit -m "fix: align upload quota panel width"
```
