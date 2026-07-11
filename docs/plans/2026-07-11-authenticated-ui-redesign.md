# Authenticated UI Redesign Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rebuild every authenticated surface around the approved monochrome editorial finance desk prototype without changing business behavior, permissions, routes, or API contracts.

**Architecture:** Keep the existing React page and component boundaries. Introduce the new visual language through semantic markup additions in the shared shell and primary workflow pages, then replace the authenticated CSS layer with monochrome ledger, paper, table, and workbench patterns. Preserve the current authentication landing implementation as-is.

**Tech Stack:** React 19, TypeScript, vanilla CSS, Lucide React, Vitest, Testing Library.

---

### Task 1: Shared authenticated application shell

**Files:**
- Modify: `frontend/src/components/AppShell.tsx`
- Modify: `frontend/src/styles.css`
- Create: `frontend/src/__tests__/authenticatedVisualSystem.test.tsx`

**Steps:**
1. Add a failing test asserting the authenticated shell exposes the editorial brand, numbered navigation, command search, local-state indicator, and upload command.
2. Run `npm test -- authenticatedVisualSystem.test.tsx` and confirm the new structural assertions fail.
3. Update `AppShell.tsx` using existing routes, permissions, quota, and user menu behavior.
4. Add scoped authenticated design tokens and shell styles without altering `.motion-auth-page` behavior.
5. Run the focused test and confirm it passes.

### Task 2: Dashboard ledger composition

**Files:**
- Modify: `frontend/src/pages/DashboardPage.tsx`
- Modify: `frontend/src/styles.css`
- Modify: `frontend/src/__tests__/authenticatedVisualSystem.test.tsx`

**Steps:**
1. Add a failing test for the dashboard editorial heading, ledger metrics, priority queue, and activity area.
2. Run the focused test and confirm failure is caused by missing structure.
3. Recompose existing summary data into the approved ledger layout, retaining loading and error states.
4. Add responsive dashboard styles and reduced-motion behavior.
5. Run the focused test and confirm it passes.

### Task 3: Invoice library

**Files:**
- Modify: `frontend/src/pages/InvoiceListPage.tsx`
- Modify: `frontend/src/components/InvoiceTable.tsx`
- Modify: `frontend/src/styles.css`
- Modify: `frontend/src/__tests__/invoiceWorkbench.test.ts`

**Steps:**
1. Add failing source-level assertions for the project index, archive toolbar, status filter counts, and ledger table treatment.
2. Run the focused test and confirm failure.
3. Restructure the page while preserving all project creation, selection, archive, query, and saved-view handlers.
4. Update table status presentation to monochrome symbols and labels.
5. Run the focused test and confirm it passes.

### Task 4: Review queue and invoice review workbench

**Files:**
- Modify: `frontend/src/pages/ReviewQueuePage.tsx`
- Modify: `frontend/src/pages/InvoiceDetailPage.tsx`
- Modify: `frontend/src/components/FieldEditor.tsx`
- Modify: `frontend/src/components/InvoicePreview.tsx`
- Modify: `frontend/src/styles.css`
- Modify: `frontend/src/__tests__/authenticatedVisualSystem.test.tsx`

**Steps:**
1. Add failing assertions for numbered queue tabs, restrained risk markers, document-stage controls, field confidence treatment, and persistent confirmation actions.
2. Run focused tests and confirm failure.
3. Restyle the queue and detail workbench around document-versus-data comparison while preserving confirm, retry, save, project move, and archive behavior.
4. Run focused tests and confirm they pass.

### Task 5: Remaining authenticated surfaces and responsive rules

**Files:**
- Modify: `frontend/src/pages/UploadPage.tsx`
- Modify: `frontend/src/pages/ExportRecordsPage.tsx`
- Modify: `frontend/src/pages/SettingsPage.tsx`
- Modify: `frontend/src/pages/UserManagementPage.tsx`
- Modify: `frontend/src/styles.css`
- Modify: `frontend/src/__tests__/responsiveLayout.test.ts`

**Steps:**
1. Add failing responsive/style assertions for the new shell collapse, data table overflow, and workbench stacking rules.
2. Run the focused test and confirm failure.
3. Apply the shared ledger visual system to upload, export, settings, users, dialogs, empty, loading, and error states.
4. Add desktop, tablet, and mobile layout rules with stable control sizes and no horizontal page overflow.
5. Run focused tests and confirm they pass.

### Task 6: Full verification and implementation commit

**Files:**
- Verify all changed frontend and plan files.

**Steps:**
1. Run `npm test` from `frontend/`.
2. Run `npm run build` from `frontend/`.
3. Run `git diff --check` and inspect `git diff --stat`.
4. Verify the running application visually if browser attachment is available; otherwise report that limitation explicitly.
5. Commit the completed UI redesign on `main` with a separate implementation commit.
