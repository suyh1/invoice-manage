import { describe, expect, it } from "vitest";

import { canDownloadExport, exportStatusLabel, shouldPollExport, toReexportPayload } from "../lib/exportTasks";

describe("export task helpers", () => {
  it("labels task states and polls only unfinished work", () => {
    expect(exportStatusLabel("queued")).toBe("等待导出");
    expect(exportStatusLabel("running")).toBe("正在导出");
    expect(exportStatusLabel("completed")).toBe("已完成");
    expect(exportStatusLabel("failed")).toBe("导出失败");
    expect(shouldPollExport("queued")).toBe(true);
    expect(shouldPollExport("running")).toBe(true);
    expect(shouldPollExport("completed")).toBe(false);
  });

  it("allows downloads only for completed, unexpired exports", () => {
    expect(canDownloadExport({ status: "completed", expires_at: "2026-07-11T00:00:00Z" }, new Date("2026-07-10T00:00:00Z"))).toBe(true);
    expect(canDownloadExport({ status: "completed", expires_at: "2026-07-09T00:00:00Z" }, new Date("2026-07-10T00:00:00Z"))).toBe(false);
    expect(canDownloadExport({ status: "running", expires_at: null }, new Date())).toBe(false);
  });

  it("reuses a previous task's filters without carrying execution fields", () => {
    expect(toReexportPayload({ format: "xlsx", filters: { project_id: "project-1", status: ["confirmed"], include_items: false, include_ocr_meta: true } })).toEqual({
      format: "xlsx",
      scope: "filtered_invoices",
      filters: { project_id: "project-1", status: ["confirmed"] },
      include_items: false,
      include_ocr_meta: true,
    });
  });
});
