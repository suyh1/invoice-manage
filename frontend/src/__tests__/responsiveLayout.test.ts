// @ts-expect-error Vitest runs in Node; the browser app intentionally omits Node type declarations.
import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

const styles = readFileSync(new URL("../styles.css", import.meta.url), "utf8");

describe("responsive workspace layout", () => {
  it("keeps the workspace grid track shrinkable at intermediate widths", () => {
    const workspaceRule = styles.match(/\.workspace\s*\{([^}]*)\}/)?.[1];

    expect(workspaceRule).toContain("grid-template-columns: minmax(0, 1fr);");
  });

  it("keeps page content and invoice filters within tablet widths", () => {
    const pageStackRule = styles.match(/\.page-stack\s*\{([^}]*)\}/)?.[1];
    const tabletRules = styles.match(/@media \(max-width: 980px\) \{([\s\S]*?)@media \(max-width: 680px\)/)?.[1];

    expect(pageStackRule).toContain("grid-template-columns: minmax(0, 1fr);");
    expect(tabletRules).toMatch(
      /\.invoice-filters\s*\{[^}]*grid-template-columns:\s*repeat\(2, minmax\(0, 1fr\)\);/,
    );
  });

  it("keeps invoice detail panels shrinkable and stacks before the editor overflows", () => {
    const detailRule = styles.match(/\.invoice-detail-layout\s*\{([^}]*)\}/)?.[1] ?? "";
    const previewRule = styles.match(/\.invoice-preview\s*\{([^}]*)\}/)?.[1] ?? "";
    const detailBreakpoint = styles.match(
      /@media \(max-width: 1360px\) \{([\s\S]*?)(?=@media|$)/,
    )?.[1] ?? "";

    expect(detailRule).toContain("min-width: 0;");
    expect(previewRule).toContain("min-width: 0;");
    expect(detailBreakpoint).toMatch(/\.invoice-detail-layout\s*\{[^}]*grid-template-columns:\s*1fr;/);
  });

  it("defines the unified project and invoice workspace", () => {
    expect(styles).toContain(".invoice-workbench");
    expect(styles).toContain(".project-rail");
    expect(styles).toContain(".invoice-workbench-main");
  });

  it("keeps the invoice archive inside the workspace and readable", () => {
    expect(styles).toMatch(/\.invoice-archive\s*\{[^}]*min-width:\s*0;/);
    expect(styles).toMatch(/\.invoice-archive \.archive-heading\s*\{[^}]*min-width:\s*0;/);
    expect(styles).toMatch(/\.invoice-archive \.saved-view-bar\s*\{[^}]*max-width:/);
    expect(styles).toMatch(/\.invoice-ledger-table[^}]*font-size:\s*10px/);
    expect(styles).toContain(".invoice-archive .project-rail-heading h2");
  });

  it("defines the approved motion authentication visual contract", () => {
    const desktopSingleScreenRules = styles.match(
      /@media \(min-width: 811px\) \{([\s\S]*?)@media \(max-width: 810px\)/,
    )?.[1] ?? "";
    const desktopAuthPageRule = desktopSingleScreenRules.match(
      /\.motion-auth-page:not\(\.is-bootstrap\)\s*\{([^}]*)\}/,
    )?.[1] ?? "";
    const mobileAuthRules = styles.match(
      /@media \(max-width: 810px\) \{([\s\S]*?)@media \(max-width: 440px\)/,
    )?.[1];

    expect(styles).toContain(".motion-auth-page");
    expect(styles).toContain("--auth-panel-rest-y: 18px;");
    expect(styles).toContain("--auth-panel-engaged-y: -10px;");
    expect(styles).toContain("backdrop-filter: blur(28px) saturate(140%);");
    expect(styles).toContain("@keyframes line-pulse");
    expect(styles).toContain("@keyframes marquee-left");
    expect(styles).toContain("auth-motion-hero-desktop.webp");
    expect(styles).toContain("auth-motion-hero-mobile.webp");
    expect(styles).toContain("@media (max-width: 810px)");
    expect(styles).toContain("@media (prefers-reduced-motion: reduce)");
    expect(desktopAuthPageRule).toContain("height: 100dvh;");
    expect(desktopAuthPageRule).toContain("overflow: hidden;");
    expect(desktopAuthPageRule).toContain("grid-template-columns: minmax(0, 1fr);");
    expect(desktopAuthPageRule).toContain("grid-template-rows: minmax(0, 1fr) auto auto auto;");
    expect(mobileAuthRules).toMatch(/\.motion-auth-hero\s*\{[^}]*min-height:\s*780px;/);
    expect(styles).not.toContain(".motion-auth-menu");
    expect(styles).not.toContain("围绕企业财务流程构建");
  });

  it("keeps short desktop authentication viewports within one screen", () => {
    const shortDesktopRules = styles.match(
      /@media \(min-width: 811px\) and \(max-height: 899px\),\s*\(min-width: 811px\) and \(max-width: 1200px\) and \(max-height: 959px\) \{([\s\S]*?)(?=@media \(min-width: 811px\) and \(max-height: 559px\)|@media \(max-width: 810px\))/,
    )?.[1] ?? "";
    const shortDesktopAuthPageRule = shortDesktopRules.match(
      /\.motion-auth-page:not\(\.is-bootstrap\)\s*\{([^}]*)\}/,
    )?.[1] ?? "";
    const shortStatusPanelRule = shortDesktopRules.match(
      /\.motion-auth-page:not\(\.is-bootstrap\) \.motion-auth-panel\.auth-status-panel\s*\{([^}]*)\}/,
    )?.[1] ?? "";
    const shortStatusPanelMinHeight = Number(
      shortStatusPanelRule.match(/min-height:\s*(\d+)px;/)?.[1] ?? Number.POSITIVE_INFINITY,
    );

    expect(shortDesktopAuthPageRule).toContain("height: 100dvh;");
    expect(shortDesktopAuthPageRule).toContain("min-height: 0;");
    expect(shortDesktopAuthPageRule).toContain("overflow: hidden;");
    expect(shortDesktopRules).toMatch(
      /\.motion-auth-page:not\(\.is-bootstrap\) \.motion-auth-hero\s*\{[^}]*padding:/,
    );
    expect(shortDesktopRules).toMatch(
      /\.motion-auth-page:not\(\.is-bootstrap\) \.motion-auth-copy h1\s*\{[^}]*font-size:/,
    );
    expect(shortDesktopRules).toMatch(
      /\.motion-auth-page:not\(\.is-bootstrap\) \.motion-auth-panel\s*\{[^}]*padding:/,
    );
    expect(shortDesktopRules).toMatch(
      /\.motion-auth-page:not\(\.is-bootstrap\) \.motion-auth-panel \.auth-form input\s*\{[^}]*min-height:/,
    );
    expect(shortStatusPanelMinHeight).toBeLessThan(270);
    expect(shortDesktopRules).toMatch(
      /\.motion-auth-page:not\(\.is-bootstrap\) \.motion-auth-panel \.auth-alert\s*\{[^}]*margin-top:[^}]*padding:[^}]*font-size:[^}]*line-height:/,
    );
    expect(shortDesktopRules).toMatch(
      /\.motion-auth-page:not\(\.is-bootstrap\) \.motion-auth-workflow\s*\{[^}]*padding:/,
    );
    expect(shortDesktopRules).toMatch(
      /\.motion-auth-page:not\(\.is-bootstrap\) \.motion-auth-footer\s*\{[^}]*padding:/,
    );
  });

  it("keeps the compact desktop login panel near the hero visual center", () => {
    const shortDesktopRules = styles.match(
      /@media \(min-width: 811px\) and \(max-height: 899px\),\s*\(min-width: 811px\) and \(max-width: 1200px\) and \(max-height: 959px\) \{([\s\S]*?)(?=@media \(min-width: 811px\) and \(max-height: 559px\)|@media \(max-width: 810px\))/,
    )?.[1] ?? "";
    const compactDesktopPanelRule = shortDesktopRules.match(
      /\.motion-auth-page:not\(\.is-bootstrap\) \.motion-auth-panel\s*\{([^}]*)\}/,
    )?.[1] ?? "";

    expect(compactDesktopPanelRule).toContain("margin-top: 148px;");
  });

  it("keeps authentication accessible in ultra-short desktop viewports", () => {
    const ultraShortDesktopRules = styles.match(
      /@media \(min-width: 811px\) and \(max-height: 559px\) \{([\s\S]*?)@media \(max-width: 810px\)/,
    )?.[1] ?? "";
    const ultraShortAuthPageRule = ultraShortDesktopRules.match(
      /\.motion-auth-page:not\(\.is-bootstrap\)\s*\{([^}]*)\}/,
    )?.[1] ?? "";

    expect(ultraShortAuthPageRule).toContain("display: block;");
    expect(ultraShortAuthPageRule).toContain("height: auto;");
    expect(ultraShortAuthPageRule).toContain("min-height: 100dvh;");
    expect(ultraShortAuthPageRule).toContain("overflow-x: clip;");
    expect(ultraShortAuthPageRule).toContain("overflow-y: visible;");
  });
});
