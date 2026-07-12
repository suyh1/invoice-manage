# Invoice OCR Brand Icon Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the browser's default icon with a project-specific invoice scanning mark and reuse that mark throughout the application's brand surfaces.

**Architecture:** Define one deterministic SVG master in `frontend/public`, expose the same vector geometry as a small React component for in-app use, and generate fixed-size PNG derivatives for platform metadata. Keep browser metadata in `frontend/index.html` and verify both markup and component rendering with Vitest.

**Tech Stack:** React 19, TypeScript, Vite, Vitest, SVG, PNG

---

### Task 1: Add failing branding tests

**Files:**
- Create: `frontend/src/__tests__/BrandMark.test.tsx`
- Create: `frontend/src/__tests__/brandMetadata.test.ts`

**Step 1: Write the failing component test**

Render `BrandMark` and assert that it produces the shared brand SVG marker with an accessible-hidden decorative contract.

**Step 2: Write the failing metadata test**

Read `frontend/index.html` and assert that it declares the SVG favicon, PNG favicon, Apple Touch Icon, manifest, and theme color.

**Step 3: Run tests to verify they fail**

Run: `npm test -- --run src/__tests__/BrandMark.test.tsx src/__tests__/brandMetadata.test.ts`

Expected: FAIL because `BrandMark` and the icon metadata do not exist yet.

### Task 2: Create the icon asset set

**Files:**
- Create: `frontend/public/favicon.svg`
- Create: `frontend/public/favicon-32x32.png`
- Create: `frontend/public/apple-touch-icon.png`
- Create: `frontend/public/icon-192.png`
- Create: `frontend/public/icon-512.png`
- Create: `frontend/public/site.webmanifest`

**Step 1: Build the SVG master**

Use a `64 64` viewBox, `#177c78` background, white folded invoice, and four high-contrast scan corners. Keep strokes optically strong enough for 16px output.

**Step 2: Export PNG derivatives**

Rasterize the SVG at 32px, 180px, 192px, and 512px without changing geometry.

**Step 3: Validate dimensions and alpha/color mode**

Inspect each PNG and confirm its exact pixel dimensions and valid PNG format.

### Task 3: Add the reusable page mark and metadata

**Files:**
- Create: `frontend/src/components/BrandMark.tsx`
- Modify: `frontend/src/components/AppShell.tsx`
- Modify: `frontend/src/components/auth/MotionLandingChrome.tsx`
- Modify: `frontend/src/styles.css`
- Modify: `frontend/index.html`

**Step 1: Implement `BrandMark`**

Create a small inline SVG component using the same geometry as `favicon.svg`, accepting an optional class name and remaining decorative with `aria-hidden="true"`.

**Step 2: Integrate the mark**

Place it before the existing brand copy in the authenticated shell and landing navbar. Adjust responsive CSS so the icon remains visible when sidebar text collapses.

**Step 3: Add browser metadata**

Reference all icon assets, the manifest, and `#177c78` theme color from `frontend/index.html`.

**Step 4: Run focused tests to verify they pass**

Run: `npm test -- --run src/__tests__/BrandMark.test.tsx src/__tests__/brandMetadata.test.ts`

Expected: PASS.

### Task 4: Verify the complete frontend

**Files:**
- Verify all modified frontend files.

**Step 1: Run the full test suite**

Run: `npm test`

Expected: all tests pass.

**Step 2: Run the production build**

Run: `npm run build`

Expected: TypeScript and Vite build exit successfully and include the icon assets.

**Step 3: Inspect in the browser**

Start the local frontend, capture desktop and narrow viewport screenshots, and verify that the icon is visible, aligned, uncropped, and consistent with the existing theme.

**Step 4: Review the final diff**

Run: `git diff --check` and inspect `git status --short`.

Expected: no whitespace errors and only the intended branding files are changed.
