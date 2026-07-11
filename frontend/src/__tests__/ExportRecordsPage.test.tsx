// @ts-expect-error Vitest runs in Node; the browser app intentionally omits Node type declarations.
import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

const exportPage = readFileSync(new URL("../pages/ExportRecordsPage.tsx", import.meta.url), "utf8");

describe("project package export controls", () => {
  it("offers ZIP packages and makes the project mandatory", () => {
    expect(exportPage).toContain("项目文件包 ZIP");
    expect(exportPage).toContain("isProjectPackage");
    expect(exportPage).toContain("includeAll={!isProjectPackage}");
    expect(exportPage).toContain("required={isProjectPackage}");
    expect(exportPage).toContain("disabled={busy || (isProjectPackage && !projectId)}");
  });

  it("hides invoice-only controls and labels package records", () => {
    expect(exportPage).toContain("!isProjectPackage");
    expect(exportPage).toContain("项目文件包");
    expect(exportPage).toContain("buildExportPayload");
  });
});
