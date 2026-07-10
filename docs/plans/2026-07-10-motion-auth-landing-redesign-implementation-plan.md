# Motion Auth Landing Redesign Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the existing archival authentication page with an image-led MotionSites-inspired landing experience featuring a centered progressive glass login panel, full-density pulse lines, real project capability marquees, and preserved authentication behavior.

**Architecture:** Keep AuthContext and every backend authentication API unchanged. Split the landing presentation into reusable authentication chrome components, keep form submission and validation in AuthLandingPage, and drive menu and glass engagement with local React state plus CSS-only motion. Generate separate desktop and mobile visual references and background assets before implementation, then translate them into custom CSS without Tailwind.

**Tech Stack:** React 19, TypeScript, Vite, Vitest, Testing Library, Lucide React, custom CSS, local Fontsource packages, generated WebP assets, Docker Compose.

---

### Task 1: Generate And Analyze The Visual Source Of Truth

**Files:**
- Create: docs/design/motion-auth-reference-desktop.webp
- Create: docs/design/motion-auth-reference-mobile.webp
- Create: frontend/public/auth-motion-hero-desktop.webp
- Create: frontend/public/auth-motion-hero-mobile.webp
- Create: docs/design/motion-auth-reference-analysis.md

**Step 1: Generate a standalone desktop design reference**

Use the imagegen and image-to-code skills to generate one large 1440x1000 reference image with this direction:

    Premium black-and-white single-page authentication landing for an enterprise invoice OCR system named Invoice OCR. Fixed minimal navbar, editorial serif italic emphasis, full-density white curved pulse lines on both sides, abstract layered invoice paper and OCR scan-light background, centered headline "Every invoice, traceable.", Chinese supporting copy, a semi-transparent login form initially sitting below the line animation, a clear raised glass form state implied, capability ticker, bottom capability marquee, no fake clients, no office, no laptop, no readable invoice amounts, no purple, no dashboard screenshot, clean high-end MotionSites-inspired composition, implementation-ready, 1440x1000.

Save it as docs/design/motion-auth-reference-desktop.webp.

**Step 2: Generate a fresh standalone mobile design reference**

Generate a separate 390x1100 mobile composition. Do not crop or rotate the desktop reference. Preserve the same brand world, with 40 horizontal pulse lines above the title and a centered glass form that fits the viewport.

Save it as docs/design/motion-auth-reference-mobile.webp.

**Step 3: Analyze both references before coding**

Write docs/design/motion-auth-reference-analysis.md with exact observations for:

- navbar height and gutters
- title line count, serif emphasis, and type scale
- inactive and active glass panel appearance
- panel width and vertical center
- background light and dark zones
- line placement and visual stacking
- ticker and capability marquee spacing
- mobile collapse behavior
- colors, borders, shadows, and blur levels

Do not begin component implementation until this analysis is complete.

**Step 4: Generate fresh background-only assets**

Generate two new images without UI or text:

    Desktop: horizontal cool-white layered invoice paper planes, translucent receipt edges, deep graphite structural shadows, soft OCR scan light, low-detail quiet central region for overlaid form and text, premium high-key black-and-white editorial photography, no readable text, no amount, no currency, no person, no hand, no desk, no computer, no UI, 16:10 landscape.

    Mobile: vertical layered invoice paper and translucent receipt planes, graphite shadows and soft OCR scan light, large low-detail central corridor for title and form, same premium black-and-white editorial world, no readable text, no amount, no currency, no person, no device, 9:16 portrait.

Save them as:

- frontend/public/auth-motion-hero-desktop.webp
- frontend/public/auth-motion-hero-mobile.webp

**Step 5: Verify the generated assets**

Run:

    file docs/design/motion-auth-reference-desktop.webp
    file docs/design/motion-auth-reference-mobile.webp
    file frontend/public/auth-motion-hero-desktop.webp
    file frontend/public/auth-motion-hero-mobile.webp
    ls -lh docs/design/motion-auth-reference-*.webp frontend/public/auth-motion-hero-*.webp

Expected: four valid WebP images with non-zero dimensions. Background assets should be compressed to a practical first-screen size.

**Step 6: Commit**

    git add docs/design/motion-auth-reference-desktop.webp docs/design/motion-auth-reference-mobile.webp docs/design/motion-auth-reference-analysis.md frontend/public/auth-motion-hero-desktop.webp frontend/public/auth-motion-hero-mobile.webp
    git commit -m "design: add motion auth visual references"

### Task 2: Add Interactive Landing Test Infrastructure

**Files:**
- Modify: frontend/package.json
- Modify: frontend/package-lock.json
- Modify: frontend/src/__tests__/AuthLandingPage.test.tsx

**Step 1: Install the minimal test and font dependencies**

Run:

    cd frontend
    npm install @fontsource/manrope @fontsource/source-serif-4
    npm install --save-dev @testing-library/react @testing-library/user-event jsdom

Do not add Tailwind or a general animation library.

**Step 2: Replace the static-only authentication tests with the new visual contract**

Keep existing authentication field assertions and add tests equivalent to:

    // @vitest-environment jsdom

    it("renders the motion landing contract without fake social proof", () => {
      render(<AuthLandingPage mode="login" busy={false} errorMessage={null} onBootstrap={noop} onLogin={noop} />);

      expect(screen.getByRole("heading", { name: "Every invoice, traceable." })).toBeTruthy();
      expect(screen.getByRole("button", { name: "Menu" })).toBeTruthy();
      expect(screen.getByText("围绕企业财务流程构建")).toBeTruthy();
      expect(document.querySelectorAll(".motion-line-left")).toHaveLength(20);
      expect(document.querySelectorAll(".motion-line-right")).toHaveLength(20);
      expect(screen.queryByText("Partnered with top-tier companies globally")).toBeNull();
    });

    it("raises and retains the glass panel after the first field focus", async () => {
      const user = userEvent.setup();
      render(<AuthLandingPage mode="login" busy={false} errorMessage={null} onBootstrap={noop} onLogin={noop} />);
      const panel = screen.getByRole("region", { name: "登录系统" });

      expect(panel.getAttribute("data-engaged")).toBe("false");
      await user.click(screen.getByLabelText("邮箱"));
      expect(panel.getAttribute("data-engaged")).toBe("true");
      await user.click(screen.getByLabelText("密码"));
      expect(panel.getAttribute("data-engaged")).toBe("true");
    });

    it("opens and closes the fullscreen menu with Escape", async () => {
      const user = userEvent.setup();
      render(<AuthLandingPage mode="login" busy={false} errorMessage={null} onBootstrap={noop} onLogin={noop} />);

      await user.click(screen.getByRole("button", { name: "Menu" }));
      expect(screen.getByRole("dialog", { name: "首页导航" })).toBeTruthy();
      await user.keyboard("{Escape}");
      expect(screen.queryByRole("dialog", { name: "首页导航" })).toBeNull();
    });

Also keep tests for:

- login autocomplete values
- first-admin bootstrap fields and two new-password inputs
- busy and error states
- loading and retry states
- no remember-me, forgot-password, registration, avatar, or fake company logos

**Step 3: Run the tests and verify RED**

Run:

    cd frontend
    npm test -- AuthLandingPage

Expected: FAIL because the new headline, motion lines, menu, marquee, and engaged panel state do not exist.

**Step 4: Commit the failing contract**

    git add frontend/package.json frontend/package-lock.json frontend/src/__tests__/AuthLandingPage.test.tsx
    git commit -m "test: define motion auth landing contract"

### Task 3: Build The Motion Landing Structure

**Files:**
- Create: frontend/src/components/auth/MotionLandingChrome.tsx
- Create: frontend/src/lib/authLanding.ts
- Modify: frontend/src/pages/AuthLandingPage.tsx
- Modify: frontend/src/main.tsx
- Test: frontend/src/__tests__/AuthLandingPage.test.tsx

**Step 1: Add landing constants and panel-state helper**

Create frontend/src/lib/authLanding.ts:

    export const heroCapabilities = [
      "原件归档",
      "OCR 识别",
      "人工校对",
      "项目分类",
      "权限管理",
      "结构化导出",
    ] as const;

    export const workflowCapabilities = [
      "原件归档",
      "OCR 识别",
      "人工校对",
      "重复检测",
      "项目分类",
      "权限管理",
      "JSON",
      "CSV",
      "XLSX",
    ] as const;

    export function forceEngagedPanel(options: {
      busy: boolean;
      errorMessage: string | null;
      mode: "bootstrap" | "login";
    }): boolean {
      return options.mode === "bootstrap" || options.busy || Boolean(options.errorMessage);
    }

**Step 2: Add reusable landing chrome**

Create MotionLandingChrome.tsx with:

- MotionNavbar
- FullscreenMenu
- PulseLines
- TextMarquee
- CapabilityBand
- WorkflowIndex
- LandingFooter

Generate exactly 20 left lines and 20 right lines with stable keys. Give each line CSS custom properties for a delay of index times 0.25 seconds and a width of 60 plus index times 10 pixels. Generate a separate 40-line top set for mobile CSS to reveal.

**Step 3: Rebuild AuthLandingPage around the approved structure**

Keep handleSubmit, field names, autocomplete, password toggling, and payloads unchanged. Add local engaged state:

    const [engaged, setEngaged] = useState(
      forceEngagedPanel({ busy, errorMessage, mode }),
    );
    const panelEngaged = engaged || forceEngagedPanel({ busy, errorMessage, mode });

Attach onFocusCapture to the panel and render data-engaged on the region. Render the headline as one accessible heading:

    <h1 id="auth-product-title">
      Every invoice, <em>traceable.</em>
    </h1>

**Step 4: Import local Fontsource CSS**

In frontend/src/main.tsx, before styles.css, import only:

    @fontsource/manrope/400.css
    @fontsource/manrope/500.css
    @fontsource/manrope/600.css
    @fontsource/manrope/700.css
    @fontsource/source-serif-4/600.css
    @fontsource/source-serif-4/600-italic.css

**Step 5: Run the targeted tests and verify GREEN**

    cd frontend
    npm test -- AuthLandingPage

Expected: structural, form, line-count, engaged-state, and menu tests pass.

**Step 6: Commit**

    git add frontend/src/components/auth/MotionLandingChrome.tsx frontend/src/lib/authLanding.ts frontend/src/pages/AuthLandingPage.tsx frontend/src/main.tsx frontend/src/__tests__/AuthLandingPage.test.tsx
    git commit -m "feat: build motion authentication landing"

### Task 4: Implement Menu Focus And Scroll Behavior

**Files:**
- Modify: frontend/src/components/auth/MotionLandingChrome.tsx
- Modify: frontend/src/pages/AuthLandingPage.tsx
- Test: frontend/src/__tests__/AuthLandingPage.test.tsx

**Step 1: Add failing focus-management tests**

Add tests proving:

- Menu opens with aria-expanded true
- first menu link receives focus
- Tab and Shift+Tab stay inside the drawer
- Escape closes the drawer
- focus returns to Menu
- “登录系统” closes the menu and focuses the first authentication field
- document scrolling is restored on unmount

Run npm test -- AuthLandingPage and verify it fails on focus management.

**Step 2: Implement focus management**

Use refs and a scoped effect only while the drawer is open. Save and restore document.body.style.overflow. Add one keydown listener for Escape and Tab wrapping, and remove it in the effect cleanup. Keep focusable-element queries scoped to the drawer. Do not add a global focus-trap dependency.

**Step 3: Verify targeted tests**

    cd frontend
    npm test -- AuthLandingPage

Expected: PASS.

**Step 4: Commit**

    git add frontend/src/components/auth/MotionLandingChrome.tsx frontend/src/pages/AuthLandingPage.tsx frontend/src/__tests__/AuthLandingPage.test.tsx
    git commit -m "feat: make landing navigation accessible"

### Task 5: Translate The Visual References Into Custom CSS

**Files:**
- Modify: frontend/src/styles.css
- Modify: frontend/src/__tests__/responsiveLayout.test.ts

**Step 1: Add failing CSS contract tests**

Extend responsiveLayout.test.ts to assert the auth CSS contains:

    .motion-auth-page
    backdrop-filter: blur(28px) saturate(140%);
    @keyframes line-pulse
    @keyframes marquee-left
    auth-motion-hero-mobile.webp
    @media (prefers-reduced-motion: reduce)

Run npm test -- responsiveLayout and verify RED.

**Step 2: Replace the old authentication CSS block**

Implement custom CSS for:

- fixed navbar and brand lockup
- black Menu pill
- fullscreen white drawer
- full-bleed background image using desktop and mobile assets
- 20 left, 20 right, and 40 mobile top pulse lines
- ticker mask and duplicated track
- centered title and description
- inactive glass panel below pulse lines
- active glass panel above pulse lines using data-engaged true
- progressive bottom blur
- capability band
- workflow index
- footer

Use this layer order:

    --auth-z-background: 0;
    --auth-z-panel-resting: 2;
    --auth-z-lines: 3;
    --auth-z-panel-engaged: 4;
    --auth-z-navbar: 20;
    --auth-z-menu: 100;

The inactive panel must remain readable. Do not use negative letter spacing. Do not change authenticated workspace tokens.

**Step 3: Add the approved animations**

    @keyframes marquee-left {
      from { transform: translateX(0); }
      to { transform: translateX(-50%); }
    }

    @keyframes line-pulse {
      0% { opacity: 0; transform: scale(1); }
      15% { opacity: 0.9; }
      70% { opacity: 0.4; }
      100% { opacity: 0; transform: scale(0.85); }
    }

Gate loops behind prefers-reduced-motion no-preference. Under reduced motion, show a stable representative line state and stop both marquees.

**Step 4: Implement discrete responsive breakpoints**

- below 1200px: reduce gutters and title size
- below 810px: switch to the mobile background, hide side lines, reveal 40 top lines, use a one-column workflow index, and size the panel to the viewport minus 32px
- at 375px: keep every field, label, and button inside the viewport
- bootstrap mode: use a taller hero modifier without compressing form controls

**Step 5: Run CSS and full frontend verification**

    cd frontend
    npm test -- responsiveLayout
    npm test
    npm run build

Expected: all tests pass and Vite production build completes.

**Step 6: Commit**

    git add frontend/src/styles.css frontend/src/__tests__/responsiveLayout.test.ts
    git commit -m "feat: style immersive motion login"

### Task 6: Preserve Loading And Error States In The New Shell

**Files:**
- Modify: frontend/src/pages/AuthLandingPage.tsx
- Test: frontend/src/__tests__/AuthLandingPage.test.tsx

**Step 1: Add failing state tests**

Test that loading and error screens render:

- the same navbar, hero title, backgrounds, pulse lines, and footer
- a glass panel with data-engaged true
- aria-live polite for loading
- retry button for errors
- no login fields while loading or unavailable

Run npm test -- AuthLandingPage and verify RED if status pages still use the old structure.

**Step 2: Reuse the shared motion shell**

Refactor AuthStatusPage to render through the same chrome components. Do not duplicate navbar, background, pulse-line, capability, or footer markup.

**Step 3: Verify tests**

    cd frontend
    npm test -- AuthLandingPage

Expected: PASS.

**Step 4: Commit**

    git add frontend/src/pages/AuthLandingPage.tsx frontend/src/__tests__/AuthLandingPage.test.tsx
    git commit -m "feat: unify authentication status screens"

### Task 7: Full Verification, Docker Upgrade, And Browser QA

**Files:**
- Modify: docs/plans/2026-07-10-motion-auth-landing-redesign-design.md only if implementation findings require an explicit correction

**Step 1: Run frontend verification**

    cd frontend
    npm test
    npm run build

Expected: all tests and production build pass.

**Step 2: Run backend regression verification**

    cd backend
    uv run --frozen --extra test pytest -v

Expected: all backend tests pass, with only documented optional PostgreSQL skips.

**Step 3: Run Docker E2E**

    tests/e2e/run.sh

Expected: bootstrap, login, users, projects, OCR, review, export, and persistence checks pass unchanged.

**Step 4: Rebuild the release image and retain existing volumes**

    docker buildx build --platform linux/amd64 --load -t invoice-ocr-app:0.2.0 .
    docker inspect invoice-ocr-app:0.2.0 --format '{{.Config.User}} {{.Architecture}}'
    docker compose up -d --force-recreate app worker
    curl -fsS http://localhost:8080/healthz
    curl -fsS http://localhost:8080/readyz

Expected: invoice amd64, healthy app, ready database and Redis. Do not delete volumes.

**Step 5: Browser QA at the required widths**

Use the in-app browser and verify logged-out login state, first-admin state in the isolated E2E environment or component fixture, loading state, and error state.

At 375, 768, 1024, and 1440px verify:

- background image is nonblank and correctly framed
- desktop or mobile image selection is correct
- 20 left and 20 right lines on desktop
- 40 top lines on mobile
- inactive panel is below the line layer and remains readable
- focusing an input raises the panel above the line layer and keeps it engaged
- drawer opens, traps focus, closes with Escape, and returns focus
- title, panel, buttons, and footer do not overlap
- scrollWidth equals innerWidth
- reduced-motion mode stops loops
- console has no warnings or errors

Reset the viewport override, log in again, and leave the browser visible at http://localhost:8080/#/invoices.

**Step 6: Final repository review**

    git status --short --branch
    git log --oneline -10
    git diff --check HEAD~6..HEAD

Confirm no external image URLs, plaintext local credentials, session values, OCR secrets, or generated font licensing files outside installed packages were committed.
