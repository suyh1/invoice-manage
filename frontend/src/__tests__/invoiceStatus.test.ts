import { describe, expect, it } from "vitest";

import {
  canBulkConfirm,
  invoiceStatusLabel,
  reviewFilterForTab,
  type ReviewInvoiceItem,
} from "../lib/invoiceStatus";
import { groupAssignableProjectOptions, type ProjectSummary } from "../lib/projects";

describe("invoice status helpers", () => {
  it("uses the backend review statuses and Chinese labels", () => {
    expect(invoiceStatusLabel("needs_review")).toBe("待人工确认");
    expect(invoiceStatusLabel("duplicate_suspected")).toBe("疑似重复");
    expect(invoiceStatusLabel("confirmed")).toBe("已确认");
    expect(invoiceStatusLabel("archived")).toBe("已归档");
  });

  it("maps review tabs to their backend filters", () => {
    expect(reviewFilterForTab("needs_review")).toEqual({ status: "needs_review" });
    expect(reviewFilterForTab("duplicates")).toEqual({ status: "duplicate_suspected" });
    expect(reviewFilterForTab("failed")).toEqual({ document_status: "ocr_failed" });
  });

  it("allows bulk confirmation only for clean invoices awaiting review", () => {
    const clean: ReviewInvoiceItem = {
      kind: "invoice",
      invoice_id: "invoice-id",
      status: "needs_review",
      is_duplicate_suspected: false,
    };
    expect(canBulkConfirm(clean)).toBe(true);
    expect(canBulkConfirm({ ...clean, is_duplicate_suspected: true })).toBe(false);
    expect(canBulkConfirm({ ...clean, status: "duplicate_suspected" })).toBe(false);
    expect(canBulkConfirm({ kind: "document", invoice_id: null, status: "ocr_failed" })).toBe(false);
  });
});

describe("groupAssignableProjectOptions", () => {
  it("groups active projects and excludes archived destinations", () => {
    const base: Omit<ProjectSummary, "id" | "name" | "visibility" | "status"> = {
      description: null,
      system_key: null,
      created_by: null,
      created_at: null,
      updated_at: null,
      archived_at: null,
      can_manage: false,
    };
    const groups = groupAssignableProjectOptions([
      { ...base, id: "system", name: "未分类", visibility: "system", status: "active" },
      { ...base, id: "shared", name: "共享差旅", visibility: "shared", status: "active" },
      { ...base, id: "private", name: "我的采购", visibility: "private", status: "active" },
      { ...base, id: "archived", name: "历史项目", visibility: "shared", status: "archived" },
    ]);

    expect(groups.system.map((project) => project.id)).toEqual(["system"]);
    expect(groups.shared.map((project) => project.id)).toEqual(["shared"]);
    expect(groups.private.map((project) => project.id)).toEqual(["private"]);
    expect(Object.values(groups).flat().some((project) => project.id === "archived")).toBe(false);
  });
});
