// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { InvoiceDetailPage } from "../pages/InvoiceDetailPage";
import { apiGet, apiPatch } from "../lib/api";

vi.mock("../lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../lib/api")>();
  return { ...actual, apiGet: vi.fn(), apiPatch: vi.fn(), apiPost: vi.fn(), apiPut: vi.fn() };
});

const project = { id: "project-1", name: "jet", visibility: "private", status: "active" };
const baseDetail = {
  amount_with_tax: "21.00",
  amount_without_tax: "19.81",
  archived_at: null,
  buyer_name: "苏钰溪",
  buyer_tax_id: null,
  check_code: null,
  confirmed_at: null,
  corrections: [],
  document: null,
  expense_scene: "office",
  id: "invoice-1",
  invoice_code: null,
  invoice_date: "2026-07-08",
  invoice_number: "26527000000090440284",
  invoice_type: "电子发票（普通发票）",
  is_duplicate_suspected: false,
  items: [],
  normalized_payload: {
    field_sources: {
      invoice_number: { name: "发票号码", value: "26527000000090440284" },
    },
    invoice_fields: { invoice_number: "26527000000090440284" },
    supplemental_fields: [],
  },
  ocr: null,
  project,
  seller_name: "云上艾珀（贵州）技术有限公司",
  seller_tax_id: "91520900MA6GN48P46",
  status: "needs_review",
  tax_amount: "1.19",
};

describe("InvoiceDetailPage", () => {
  beforeEach(() => {
    vi.mocked(apiGet).mockImplementation((path) => Promise.resolve(path === "/api/v1/projects" ? [project] : baseDetail));
    vi.mocked(apiPatch).mockReset();
  });

  afterEach(cleanup);

  it("keeps business scene beside project and saves it independently from OCR fields", async () => {
    vi.mocked(apiPatch).mockResolvedValue({ ...baseDetail, expense_scene: "travel" });
    render(<InvoiceDetailPage invoiceId="invoice-1" />);

    const sceneSelect = await screen.findByRole("combobox", { name: "业务场景" });
    expect(screen.getByRole("combobox", { name: "归属项目" })).toBeTruthy();
    expect(screen.queryByRole("textbox", { name: /业务场景/ })).toBeNull();

    fireEvent.change(sceneSelect, { target: { value: "travel" } });

    await waitFor(() => expect(apiPatch).toHaveBeenCalledWith("/api/v1/invoices/invoice-1", { expense_scene: "travel" }));
  });

  it("hides an empty invoice code but shows a code returned for a traditional invoice", async () => {
    const first = render(<InvoiceDetailPage invoiceId="invoice-1" />);
    await screen.findByRole("textbox", { name: /发票号码/ });
    expect(screen.queryByRole("textbox", { name: /发票代码/ })).toBeNull();
    first.unmount();

    vi.mocked(apiGet).mockImplementation((path) => Promise.resolve(
      path === "/api/v1/projects" ? [project] : { ...baseDetail, invoice_code: "144032216011" },
    ));
    render(<InvoiceDetailPage invoiceId="invoice-2" />);

    expect((await screen.findByRole("textbox", { name: /发票代码/ }) as HTMLInputElement).value).toBe("144032216011");
  });
});
