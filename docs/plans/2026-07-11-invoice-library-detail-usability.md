# Invoice Library and Detail Usability Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Repair the invoice library selection and table layout, bound the detail workbench to the app workspace, and correctly separate OCR fields from archive metadata.

**Architecture:** Keep the current React and CSS structure. Add a small reusable column-width hook inside `InvoiceTable`, reuse the existing PATCH endpoint for project and scene changes, and correct layout through scoped CSS rather than changing the application shell.

**Tech Stack:** React 18, TypeScript, Vitest, Testing Library, FastAPI, pytest, vanilla CSS.

---

### Task 1: Project index active state

**Files:**
- Modify: `frontend/src/styles.css`
- Test: `frontend/src/__tests__/invoiceWorkbench.test.ts`

**Steps:**

1. Add a failing source-level regression test asserting that an active archive project row gives its select button and action buttons transparent backgrounds and inherited color.
2. Run `npm test -- --run src/__tests__/invoiceWorkbench.test.ts` from `frontend` and confirm the new assertion fails.
3. Add scoped `.invoice-archive .project-rail-row.active` descendant rules, including hover and focus states, without changing row dimensions.
4. Re-run the focused test and confirm it passes.

### Task 2: Compact resizable invoice table

**Files:**
- Modify: `frontend/src/components/InvoiceTable.tsx`
- Modify: `frontend/src/styles.css`
- Create: `frontend/src/__tests__/InvoiceTable.test.tsx`

**Steps:**

1. Add failing component tests asserting the five approved headers, absence of project/buyer/file headers, four resize handles, and a fixed action column.
2. Add a failing interaction test that drags a header handle and verifies the changed width is written to `localStorage`.
3. Run `npm test -- --run src/__tests__/InvoiceTable.test.tsx` and confirm the tests fail for missing compact and resize behavior.
4. Replace the nine-column rendering with invoice number/status, seller, date, amount, and action.
5. Implement bounded pointer-based column resizing for the first four columns and restore valid persisted widths on mount.
6. Add scoped table CSS for single-line ellipsis, stable row height, visible resize handles, and a fixed action column.
7. Re-run the focused tests and confirm they pass.

### Task 3: Detail assignment controls and OCR labels

**Files:**
- Modify: `frontend/src/pages/InvoiceDetailPage.tsx`
- Modify: `frontend/src/components/FieldEditor.tsx`
- Modify: `frontend/src/styles.css`
- Test: `frontend/src/__tests__/ocrFieldPresentation.test.ts`
- Create: `frontend/src/__tests__/InvoiceDetailPage.test.tsx`

**Steps:**

1. Add failing tests for provider-independent `原始字段` and `OCR值` text.
2. Add failing tests asserting business scene is absent from editable OCR fields, appears beside project as a select, and sends `{ expense_scene: value }` through PATCH.
3. Add a failing test asserting invoice code is hidden when empty and shown when present.
4. Run the two focused test files and confirm each new behavior fails.
5. Remove `expense_scene` from `invoiceFields`, add a shared scene option list matching upload, and implement a scene-only save handler.
6. Render project and scene controls as a stable two-column assignment group.
7. Change the field helper text and conditionally include `invoice_code` in editable fields.
8. Re-run the focused tests and confirm they pass.

### Task 4: Bound the detail workbench

**Files:**
- Modify: `frontend/src/styles.css`
- Test: `frontend/src/__tests__/responsiveLayout.test.ts`

**Steps:**

1. Add a failing regression test that inspects the final detail override and requires zero outer margin, `max-width: 100%`, and no horizontal overflow.
2. Add breakpoint assertions for a bounded two-column desktop grid and one-column narrow layout.
3. Run `npm test -- --run src/__tests__/responsiveLayout.test.ts` and confirm the new assertions fail.
4. Add a final scoped layout override that removes the detail negative margin, keeps the sticky header relative to the workspace, and uses shrinkable grid tracks.
5. Re-run the focused test and confirm it passes.

### Task 5: Full verification

**Files:**
- Verify only

**Steps:**

1. Run `npm test -- --run` from `frontend`.
2. Run `npm run build` from `frontend`.
3. Run `uv run pytest` from `backend` to verify invoice-code and expense-scene compatibility.
4. Open `http://localhost:8080`, reproduce project selection and invoice detail navigation, and capture desktop and narrow screenshots.
5. Confirm there is no overlap with the sidebar/top bar, no page-level horizontal overflow, and all interactive controls remain readable.
