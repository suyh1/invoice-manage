# Invoice OCR Monochrome Brand Icon Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Align every Invoice OCR brand icon asset with the application's current black-and-white visual system.

**Architecture:** Keep the existing invoice scanning geometry unchanged and replace only its color tokens in the SVG master and React component. Regenerate all PNG derivatives from the updated SVG, then synchronize browser metadata and tests with the new `#0a0a0a` theme color.

**Tech Stack:** React 19, TypeScript, Vite, Vitest, SVG, PNG

---

### Task 1: Update the metadata expectation first

**Files:**
- Modify: `frontend/src/__tests__/brandMetadata.test.ts`

**Step 1: Change the expected theme color**

Replace the expected `#177c78` theme color with `#0a0a0a`.

**Step 2: Run the focused test to verify it fails**

Run: `npm test -- --run src/__tests__/brandMetadata.test.ts`

Expected: FAIL because `frontend/index.html` still declares `#177c78`.

### Task 2: Recolor the vector sources and metadata

**Files:**
- Modify: `frontend/public/favicon.svg`
- Modify: `frontend/public/site.webmanifest`
- Modify: `frontend/src/components/BrandMark.tsx`
- Modify: `frontend/index.html`

**Step 1: Replace the icon palette**

Use `#0a0a0a` for the background and invoice lines, `#ffffff` for the invoice, `#dededb` for scan corners, and `#ececea` for the fold.

**Step 2: Synchronize metadata**

Set HTML and manifest theme colors to `#0a0a0a`.

**Step 3: Run the focused test**

Run: `npm test -- --run src/__tests__/BrandMark.test.tsx src/__tests__/brandMetadata.test.ts`

Expected: PASS.

### Task 3: Regenerate and validate raster assets

**Files:**
- Modify: `frontend/public/favicon-32x32.png`
- Modify: `frontend/public/apple-touch-icon.png`
- Modify: `frontend/public/icon-192.png`
- Modify: `frontend/public/icon-512.png`

**Step 1: Rasterize the updated SVG**

Use `sips` to export the four existing PNG dimensions from `frontend/public/favicon.svg`.

**Step 2: Validate formats and dimensions**

Run `file` and `sips -g pixelWidth -g pixelHeight` against all four PNG files.

Expected: valid RGBA PNG files at 32x32, 180x180, 192x192, and 512x512.

### Task 4: Verify the complete change

**Files:**
- Verify all modified branding files.

**Step 1: Check for stale color references in branding files**

Run a scoped `rg` search over the icon component, icon assets, HTML, manifest, and branding test.

Expected: no `#177c78` matches.

**Step 2: Run the full frontend test suite**

Run: `npm test`

Expected: all tests pass.

**Step 3: Run the production build**

Run: `npm run build`

Expected: TypeScript and Vite complete successfully.

**Step 4: Inspect responsive rendering**

Verify desktop and mobile brand marks in the local browser and confirm no sizing or alignment regressions.

**Step 5: Commit**

Commit the scoped color update on `main`.
