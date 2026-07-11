// @ts-expect-error Vitest runs in Node; the browser app intentionally omits Node type declarations.
import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

const invoicePage = readFileSync(new URL("../pages/InvoiceListPage.tsx", import.meta.url), "utf8");
const router = readFileSync(new URL("../app/router.tsx", import.meta.url), "utf8");
const styles = readFileSync(new URL("../styles.css", import.meta.url), "utf8");

describe("invoice workbench", () => {
  it("integrates project navigation and project dialogs into the invoice library", () => {
    expect(invoicePage).toContain("ProjectEditorDialog");
    expect(invoicePage).toContain("project-rail");
    expect(invoicePage).toContain("创建项目");
    expect(invoicePage).toContain("changeArchiveState");
  });

  it("uses the approved archive and ledger composition", () => {
    expect(invoicePage).toContain("project-index");
    expect(invoicePage).toContain("archive-toolbar");
    expect(invoicePage).toContain("invoice-archive-ledger");
    expect(invoicePage).toContain("archive-viewbar-row");
    expect(invoicePage).toContain("INVOICE ARCHIVE");
  });

  it("removes the standalone project route without legacy compatibility code", () => {
    expect(router).not.toContain('{ id: "projects", label: "项目"');
    expect(router).not.toContain('"#/projects"');
    expect(router).not.toContain("ProjectManagementPage");
  });

  it("initializes invoice filters from global search route parameters", () => {
    expect(invoicePage).toContain("initialInvoiceFilters");
    expect(invoicePage).toContain("seller_name");
    expect(invoicePage).toContain("routeParams");
  });

  it("keeps active project controls on one continuous selected surface", () => {
    expect(styles).toMatch(
      /\.invoice-archive \.project-rail-row\.active \.project-rail-select\s*\{[^}]*background:\s*transparent;[^}]*color:\s*inherit;/,
    );
    expect(styles).toMatch(
      /\.invoice-archive \.project-rail-row\.active \.project-rail-actions button\s*\{[^}]*background:\s*transparent;[^}]*color:\s*inherit;/,
    );
    expect(styles).toMatch(
      /\.invoice-archive \.project-rail-row\.active \.project-rail-select:focus-visible\s*\{[^}]*box-shadow:\s*inset 0 -2px 0 #fff;/,
    );
  });

  it("provides a project-aware ordinary file view", () => {
    expect(invoicePage).toContain('"发票"');
    expect(invoicePage).toContain('"项目文件"');
    expect(invoicePage).toContain("ProjectFileTable");
    expect(invoicePage).toContain("document_kind=project_file");
    expect(invoicePage).toContain("apiDelete");
  });

  it("constrains project file previews to the viewport", () => {
    expect(styles).toMatch(
      /\.project-file-preview-dialog\s*\{[^}]*width:\s*min\([^;]+;[^}]*max-height:\s*min\([^;]+;/,
    );
    expect(styles).toContain(".project-file-preview-canvas");
  });
});
