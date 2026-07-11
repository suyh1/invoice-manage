# Project File Preview Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add accessible project-file previews while preserving existing download, delete, permissions, and responsive layout behavior.

**Architecture:** Reuse the existing authenticated document preview endpoint. Add a dedicated modal for image and PDF files, while Office files use a new-window preview link because they cannot be rendered reliably by the browser without additional parsing dependencies.

**Tech Stack:** React 19, TypeScript, Vitest, Testing Library, lucide-react, vanilla CSS.

---

### Task 1: Preview behavior and modal

**Files:**
- Create: `frontend/src/components/ProjectFilePreviewDialog.tsx`
- Modify: `frontend/src/components/ProjectFileTable.tsx`
- Modify: `frontend/src/__tests__/ProjectFileTable.test.tsx`

**Step 1: Write failing component tests**

Add tests asserting that image/PDF preview actions open an accessible dialog, render the existing preview URL, expose open/download actions, and close correctly. Add a DOCX case asserting that preview opens the endpoint in a new window instead of opening the modal.

**Step 2: Run tests and verify failure**

Run:

```bash
cd frontend
npm test -- --run src/__tests__/ProjectFileTable.test.tsx
```

Expected: failures because no preview action or dialog exists.

**Step 3: Implement the minimal preview component**

Create `ProjectFilePreviewDialog` using a native `dialog`, `showModal()`, and the existing `/api/v1/documents/{id}/preview` URL. Render an `img` for PNG/JPG/JPEG and an `iframe` for PDF. Add open, download, and close controls.

Update `ProjectFileTable` to hold the selected preview file. Render a preview icon button for PDF/images and a target-blank preview link for DOCX/XLSX.

**Step 4: Run focused tests and typecheck**

Run:

```bash
cd frontend
npm test -- --run src/__tests__/ProjectFileTable.test.tsx
npm run typecheck
```

Expected: all focused tests pass and TypeScript reports no errors.

### Task 2: Responsive styling and full verification

**Files:**
- Modify: `frontend/src/styles.css`
- Modify: `frontend/src/__tests__/invoiceWorkbench.test.ts`

**Step 1: Add a failing static layout test**

Require project-file preview dialog classes and viewport-constrained sizing in the authenticated stylesheet.

**Step 2: Run the test and verify failure**

Run:

```bash
cd frontend
npm test -- --run src/__tests__/invoiceWorkbench.test.ts
```

Expected: failure because preview-specific styles do not exist.

**Step 3: Add scoped modal styles**

Constrain width and height with `min()` and viewport units, keep media contained, allow internal scrolling, and add a mobile breakpoint. Do not change global workspace overflow rules.

**Step 4: Run full frontend verification**

Run:

```bash
cd frontend
npm test -- --run
npm run build
```

Expected: all frontend tests pass and the production bundle builds.

**Step 5: Verify in the browser**

Open `http://localhost:8080/#/invoices`, switch to project files, and verify preview behavior at desktop and mobile widths with no page-level horizontal overflow.
