export type ReviewTab = "needs_review" | "duplicates" | "failed";

export type ReviewInvoiceItem = {
  kind: "invoice" | "document";
  invoice_id: string | null;
  status: string;
  is_duplicate_suspected?: boolean;
};

const statusLabels: Record<string, string> = {
  archived: "已归档",
  confirmed: "已确认",
  deleted: "已删除",
  duplicate_suspected: "疑似重复",
  needs_review: "待人工确认",
  ocr_done: "待人工确认",
  ocr_failed: "识别失败",
  ocr_queued: "排队识别",
  recognizing: "识别中",
  uploaded: "已上传",
};

export function invoiceStatusLabel(status: string): string {
  return statusLabels[status] ?? "待处理";
}

export function reviewFilterForTab(tab: ReviewTab): Record<string, string> {
  if (tab === "duplicates") {
    return { status: "duplicate_suspected" };
  }
  if (tab === "failed") {
    return { document_status: "ocr_failed" };
  }
  return { status: "needs_review" };
}

export function canBulkConfirm(item: ReviewInvoiceItem): boolean {
  return item.kind === "invoice" && item.status === "needs_review" && item.is_duplicate_suspected !== true;
}
