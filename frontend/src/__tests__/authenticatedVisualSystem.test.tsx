// @ts-expect-error Vitest runs in Node; the browser app intentionally omits Node type declarations.
import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

const shell = readFileSync(new URL("../components/AppShell.tsx", import.meta.url), "utf8");
const dashboard = readFileSync(new URL("../pages/DashboardPage.tsx", import.meta.url), "utf8");
const reviewQueue = readFileSync(new URL("../pages/ReviewQueuePage.tsx", import.meta.url), "utf8");
const invoiceDetail = readFileSync(new URL("../pages/InvoiceDetailPage.tsx", import.meta.url), "utf8");
const invoicePreview = readFileSync(new URL("../components/InvoicePreview.tsx", import.meta.url), "utf8");
const uploadPage = readFileSync(new URL("../pages/UploadPage.tsx", import.meta.url), "utf8");
const exportPage = readFileSync(new URL("../pages/ExportRecordsPage.tsx", import.meta.url), "utf8");
const settingsPage = readFileSync(new URL("../pages/SettingsPage.tsx", import.meta.url), "utf8");
const usersPage = readFileSync(new URL("../pages/UserManagementPage.tsx", import.meta.url), "utf8");
const invoiceTable = readFileSync(new URL("../components/InvoiceTable.tsx", import.meta.url), "utf8");
const styles = readFileSync(new URL("../styles.css", import.meta.url), "utf8");

describe("authenticated editorial visual system", () => {
  it("uses the approved editorial shell and command bar", () => {
    expect(shell).toContain("shell-nav-index");
    expect(shell).toContain("shell-command-search");
    expect(shell).toContain("本地运行");
    expect(shell).toContain("上传发票");
    expect(shell).toContain("Invoice OCR");
  });

  it("composes the dashboard as a ledger instead of a card grid", () => {
    expect(dashboard).toContain("dashboard-editorial-heading");
    expect(dashboard).toContain("dashboard-ledger");
    expect(dashboard).toContain("priority-queue");
    expect(dashboard).toContain("activity-ledger");
  });

  it("defines a monochrome authenticated design system", () => {
    expect(styles).toContain("/* Authenticated editorial finance desk */");
    expect(styles).toContain("--desk-ink: #0a0a0a;");
    expect(styles).toContain(".shell-command-search");
    expect(styles).toContain(".dashboard-ledger");
    expect(styles).toContain("Authenticated readability baseline");
  });

  it("uses ledger review queues and a document comparison workbench", () => {
    expect(reviewQueue).toContain("numbered-review-tabs");
    expect(reviewQueue).toContain("review-ledger-table");
    expect(invoiceDetail).toContain("invoice-review-workbench");
    expect(invoicePreview).toContain("document-stage");
    expect(invoiceDetail).toContain("field-inspector");
    expect(invoiceDetail).toContain("persistent-review-actions");
  });

  it("applies the same editorial system to every authenticated surface", () => {
    expect(uploadPage).toContain("upload-editorial");
    expect(exportPage).toContain("export-ledger");
    expect(settingsPage).toContain("settings-editorial");
    expect(usersPage).toContain("user-ledger");
    expect(invoiceTable).toContain("empty-actions");
  });

  it("renders OCR quota as a hollow monochrome progress track with red threshold states", () => {
    expect(styles).toContain(".quota-progress-row");
    expect(styles).toContain(".quota-progress-track");
    expect(styles).toContain(".quota-progress-fill");
    expect(styles).toContain(".quota-progress-value");
    expect(styles).toContain(".quota-status.warning .quota-progress-fill");
    expect(styles).toContain(".quota-status.critical .quota-progress-fill");
    expect(styles).toContain("--quota-alert: oklch(0.52 0.15 28);");
    expect(styles).toContain("background: var(--quota-alert);");
    expect(styles).toMatch(
      /\.upload-editorial \.editorial-page-heading \.quota-status\.compact\s*\{\s*width:\s*100%;\s*\}/,
    );
  });
});
