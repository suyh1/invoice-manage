// @ts-expect-error Vitest runs in Node; the browser app intentionally omits Node type declarations.
import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

const invoicePage = readFileSync(new URL("../pages/InvoiceListPage.tsx", import.meta.url), "utf8");
const router = readFileSync(new URL("../app/router.tsx", import.meta.url), "utf8");

describe("invoice workbench", () => {
  it("integrates project navigation and project dialogs into the invoice library", () => {
    expect(invoicePage).toContain("ProjectEditorDialog");
    expect(invoicePage).toContain('className="project-rail"');
    expect(invoicePage).toContain("创建项目");
    expect(invoicePage).toContain("changeArchiveState");
  });

  it("removes the standalone project route without legacy compatibility code", () => {
    expect(router).not.toContain('{ id: "projects", label: "项目"');
    expect(router).not.toContain('"#/projects"');
    expect(router).not.toContain("ProjectManagementPage");
  });
});
