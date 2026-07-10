# Single-Screen Auth Landing Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Remove the authentication landing menu and capability label, then fit the complete normal desktop login landing page inside one viewport while preserving mobile scrolling and authentication behavior.

**Architecture:** Simplify `MotionLandingChrome` into a static brand-and-content shell with no menu state or navigation overlay. Use a desktop-only `100dvh` grid to allocate space across the Hero, capability marquee, compact workflow index, and footer; restore natural document flow below 810px and for the taller bootstrap state.

**Tech Stack:** React 19, TypeScript, Vitest, Testing Library, custom CSS, Docker Compose, in-app Browser.

---

### Task 1: Define The Removed Chrome And Single-Screen Contract

**Files:**
- Modify: `frontend/src/__tests__/AuthLandingPage.test.tsx`
- Modify: `frontend/src/__tests__/responsiveLayout.test.ts`

**Step 1: Replace menu assertions with removal assertions**

Update the primary landing contract test to assert:

```tsx
expect(screen.queryByRole("button", { name: "Menu" })).toBeNull();
expect(screen.queryByRole("dialog", { name: "首页导航" })).toBeNull();
expect(screen.queryByText("围绕企业财务流程构建")).toBeNull();
expect(screen.getByRole("region", { name: "系统能力" })).toBeTruthy();
```

Delete tests that only exercise removed behavior:

- Escape menu closing
- menu focus trapping
- explicit close button
- login link focus transfer
- body scroll locking

Keep all tests for:

- login fields and autocomplete
- glass panel engagement
- first administrator initialization
- busy and error handling
- loading and retry states
- exact pulse-line counts

**Step 2: Add the desktop CSS contract**

Extend `responsiveLayout.test.ts` with a desktop-only assertion:

```ts
const desktopSingleScreenRules = styles.match(
  /@media \(min-width: 811px\) \{([\s\S]*?)@media \(max-width: 810px\)/,
)?.[1];

expect(desktopSingleScreenRules).toMatch(
  /\.motion-auth-page:not\(\.is-bootstrap\)\s*\{[^}]*height:\s*100dvh;[^}]*overflow:\s*hidden;/,
);
expect(desktopSingleScreenRules).toMatch(
  /grid-template-rows:\s*minmax\(0, 1fr\) auto auto auto;/,
);
```

Also assert the menu CSS selectors and removed label are absent:

```ts
expect(styles).not.toContain(".motion-auth-menu-button");
expect(styles).not.toContain(".motion-auth-menu {");
expect(styles).not.toContain(".motion-auth-menu-close");
expect(styles).not.toContain("围绕企业财务流程构建");
```

**Step 3: Run the targeted tests and verify RED**

Run:

```bash
cd frontend
npm test -- AuthLandingPage responsiveLayout
```

Expected: FAIL because the Menu, drawer, label, and scrolling desktop CSS still exist.

**Step 4: Commit the failing contract**

```bash
git add frontend/src/__tests__/AuthLandingPage.test.tsx frontend/src/__tests__/responsiveLayout.test.ts
git commit -m "test: define single-screen auth landing"
```

### Task 2: Remove Menu And Capability Label Code

**Files:**
- Modify: `frontend/src/components/auth/MotionLandingChrome.tsx`
- Modify: `frontend/src/pages/AuthLandingPage.tsx`
- Test: `frontend/src/__tests__/AuthLandingPage.test.tsx`

**Step 1: Simplify React imports and props**

In `MotionLandingChrome.tsx`, remove:

- `useEffect`
- `useRef`
- `useState`
- `RefObject`
- `ChevronUp`
- `X`
- `drawerLinks`
- `onLoginRequest`

Keep only:

```tsx
import type { CSSProperties, ReactNode } from "react";
```

The chrome prop becomes:

```tsx
type MotionLandingChromeProps = {
  bootstrap?: boolean;
  children: ReactNode;
};
```

**Step 2: Replace the navbar with brand-only markup**

Render:

```tsx
function MotionNavbar() {
  return (
    <header className="motion-auth-navbar">
      <a className="motion-auth-brand" href="#top" aria-label="Invoice OCR 发票识别与归档">
        <span>Invoice OCR</span>
        <small>发票识别与归档</small>
      </a>
    </header>
  );
}
```

Delete `FullscreenMenu` completely.

**Step 3: Remove the capability label**

Change `CapabilityBand` to:

```tsx
function CapabilityBand() {
  return (
    <section className="motion-auth-capability-band" aria-label="系统能力">
      <TextMarquee className="motion-auth-capability-marquee" items={workflowCapabilities} />
    </section>
  );
}
```

**Step 4: Remove the unused login-focus callback**

In `AuthLandingPage.tsx`, render:

```tsx
<MotionLandingChrome bootstrap={isBootstrap}>
```

Keep `firstInputRef` because it still backs the bootstrap/login input ref contract.

**Step 5: Run targeted tests**

```bash
cd frontend
npm test -- AuthLandingPage
npm run typecheck
```

Expected: all authentication tests pass.

**Step 6: Commit**

```bash
git add frontend/src/components/auth/MotionLandingChrome.tsx frontend/src/pages/AuthLandingPage.tsx frontend/src/__tests__/AuthLandingPage.test.tsx
git commit -m "refactor: remove landing navigation"
```

### Task 3: Implement Desktop Single-Screen Layout

**Files:**
- Modify: `frontend/src/styles.css`
- Test: `frontend/src/__tests__/responsiveLayout.test.ts`

**Step 1: Delete obsolete menu CSS**

Remove every selector and animation used only by the deleted navigation:

- `.motion-auth-menu-button`
- `.motion-auth-menu`
- `.motion-auth-menu-close`
- `.motion-auth-menu nav`
- `.motion-auth-menu footer`
- `@keyframes motion-menu-enter`
- menu rules inside 1200px and 810px media queries

**Step 2: Make the default desktop shell a four-row viewport grid**

Add before the existing mobile media block:

```css
@media (min-width: 811px) {
  .motion-auth-page:not(.is-bootstrap) {
    display: grid;
    height: 100dvh;
    min-height: 720px;
    grid-template-rows: minmax(0, 1fr) auto auto auto;
    overflow: hidden;
  }

  .motion-auth-page:not(.is-bootstrap) .motion-auth-hero {
    min-height: 0;
    padding: 70px 36px 12px;
  }
}
```

Do not apply the fixed-height shell to `.is-bootstrap`.

**Step 3: Compress the normal desktop Hero**

Within the desktop media query, use explicit fixed sizes rather than viewport-scaled font sizes:

```css
.motion-auth-page:not(.is-bootstrap) .motion-auth-ticker {
  height: 30px;
}

.motion-auth-page:not(.is-bootstrap) .motion-auth-copy {
  margin-top: 14px;
}

.motion-auth-page:not(.is-bootstrap) .motion-auth-copy h1 {
  max-width: 620px;
  font-size: 58px;
}

.motion-auth-page:not(.is-bootstrap) .motion-auth-copy p {
  margin-top: 10px;
  font-size: 14px;
}

.motion-auth-page:not(.is-bootstrap) .motion-auth-panel {
  margin-top: 14px;
  padding: 18px 20px;
}
```

Compress the form without changing labels or behavior:

```css
.motion-auth-page:not(.is-bootstrap) .motion-auth-panel .auth-form {
  gap: 9px;
  margin-top: 12px;
}

.motion-auth-page:not(.is-bootstrap) .motion-auth-panel .auth-form input {
  min-height: 40px;
}

.motion-auth-page:not(.is-bootstrap) .motion-auth-panel .auth-submit {
  min-height: 42px;
}

.motion-auth-page:not(.is-bootstrap) .motion-auth-panel .auth-help {
  margin-top: 10px;
  padding-top: 9px;
}
```

**Step 4: Compress the capability band**

Use a full-width marquee with no empty label column:

```css
.motion-auth-capability-band {
  display: block;
  padding: 7px 0;
}

.motion-auth-capability-marquee {
  height: 26px;
}
```

Delete `.motion-auth-capability-band > p` rules.

**Step 5: Compress workflow and footer on desktop**

Within the desktop media query:

```css
.motion-auth-workflow {
  padding: 12px 0 10px;
}

.motion-auth-workflow > h2 {
  font-size: 24px;
}

.motion-auth-workflow-grid {
  margin-top: 10px;
}

.motion-auth-workflow-grid article {
  grid-template-columns: 34px 22px minmax(0, 1fr);
  gap: 8px;
  align-items: center;
  padding: 10px 12px 8px;
}

.motion-auth-workflow-number {
  font-size: 24px;
}

.motion-auth-workflow-grid h3 {
  font-size: 13px;
}

.motion-auth-workflow-grid p {
  margin-top: 3px;
  font-size: 10px;
  line-height: 1.4;
}

.motion-auth-footer {
  padding: 8px 0 10px;
  font-size: 10px;
}
```

If the three-column article layout is visually too dense, keep the number and icon stacked but constrain the article height to the same viewport budget. Do not hide any of the five steps.

**Step 6: Restore mobile natural flow**

Inside `@media (max-width: 810px)`, explicitly set:

```css
.motion-auth-page,
.motion-auth-page:not(.is-bootstrap) {
  display: block;
  height: auto;
  min-height: 100dvh;
  overflow-x: clip;
  overflow-y: visible;
}
```

Keep the existing mobile Hero, form, background, line, workflow and footer rules.

**Step 7: Run CSS and full frontend verification**

```bash
cd frontend
npm test -- responsiveLayout
npm test
npm run build
```

Expected: all tests pass and the Vite build completes.

**Step 8: Commit**

```bash
git add frontend/src/styles.css frontend/src/__tests__/responsiveLayout.test.ts
git commit -m "feat: fit auth landing into desktop viewport"
```

### Task 4: Docker And Browser Verification

**Files:**
- Modify: no production files unless browser findings require a focused fix

**Step 1: Rebuild the release image without deleting volumes**

```bash
docker buildx build --platform linux/amd64 --load -t invoice-ocr-app:0.2.0 .
docker compose up -d --force-recreate app worker
curl -fsS http://localhost:8080/healthz
curl -fsS http://localhost:8080/readyz
```

Expected: app healthy, database and Redis ready.

**Step 2: Verify logged-out desktop layouts in the in-app Browser**

Use `http://127.0.0.1:8080/` to avoid disturbing the existing localhost session.

At `1440×900` and `2048×982`, verify with a read-only DOM evaluation:

```js
({
  innerHeight,
  scrollHeight: document.documentElement.scrollHeight,
  innerWidth,
  scrollWidth: document.documentElement.scrollWidth,
  menuCount: document.querySelectorAll(".motion-auth-menu-button, .motion-auth-menu").length,
  removedLabelCount: [...document.querySelectorAll("*")].filter(
    (node) => node.textContent?.trim() === "围绕企业财务流程构建",
  ).length,
})
```

Expected:

- `scrollHeight === innerHeight`
- `scrollWidth === innerWidth`
- `menuCount === 0`
- `removedLabelCount === 0`
- title, login panel, capability marquee, five workflow items, and footer all visible

**Step 3: Verify mobile remains scrollable**

At `375×812` and `768×900`, verify:

- `scrollHeight > innerHeight`
- `scrollWidth === innerWidth`
- mobile background and 40 top pulse lines remain active
- fields and buttons remain inside the viewport width

**Step 4: Verify the glass interaction**

Focus the email field and confirm:

- `data-engaged="true"`
- `backdrop-filter: blur(28px) saturate(140%)`
- panel z-index changes from 2 to 4

**Step 5: Restore the browser and review the repository**

Reset the viewport override and leave the visible browser at:

```text
http://localhost:8080/#/invoices
```

Run:

```bash
git status --short --branch
git diff --check HEAD~4..HEAD
```

Expected: clean `main` worktree and no whitespace errors.
