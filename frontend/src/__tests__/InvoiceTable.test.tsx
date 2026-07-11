// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { InvoiceTable, type InvoiceSummary } from "../components/InvoiceTable";

const invoice: InvoiceSummary = {
  amount_with_tax: "21.00",
  buyer_name: "苏钰溪",
  currency: "CNY",
  document: {
    created_at: "2026-07-08T00:00:00Z",
    file_ext: "pdf",
    original_filename: "invoice.pdf",
    status: "completed",
  },
  expense_scene: "office",
  id: "invoice-1",
  invoice_code: null,
  invoice_date: "2026-07-08",
  invoice_number: "26527000000090440284",
  is_duplicate_suspected: false,
  project: { id: "project-1", name: "jet", visibility: "private", status: "active" },
  seller_name: "云上艾珀（贵州）技术有限公司",
  status: "needs_review",
};

describe("InvoiceTable", () => {
  beforeEach(() => localStorage.clear());
  afterEach(cleanup);

  it("shows only the approved compact columns", () => {
    render(<InvoiceTable invoices={[invoice]} />);

    expect(screen.getAllByRole("columnheader").map((header) => header.textContent)).toEqual([
      "发票号码",
      "销售方",
      "日期",
      "金额",
      "操作",
    ]);
    expect(screen.queryByRole("columnheader", { name: "项目" })).toBeNull();
    expect(screen.queryByRole("columnheader", { name: "购买方" })).toBeNull();
    expect(screen.queryByRole("columnheader", { name: "文件" })).toBeNull();
    expect(screen.getAllByRole("separator")).toHaveLength(4);
  });

  it("persists a resized data column while keeping the action column fixed", () => {
    render(<InvoiceTable invoices={[invoice]} />);

    const handle = screen.getByRole("separator", { name: "调整发票号码列宽" });
    fireEvent.pointerDown(handle, { clientX: 200, pointerId: 1 });
    fireEvent.pointerMove(window, { clientX: 260, pointerId: 1 });
    fireEvent.pointerUp(window, { clientX: 260, pointerId: 1 });

    expect(JSON.parse(localStorage.getItem("invoice-table-column-widths") || "{}")).toMatchObject({
      number: 340,
    });
    expect(screen.getByRole("columnheader", { name: "操作" }).getAttribute("data-resizable")).toBe("false");
  });
});
