export const OCR_QUOTA_REFRESH_EVENT = "invoice-ocr:quota-refresh";

export function notifyOcrQuotaRefresh() {
  window.dispatchEvent(new Event(OCR_QUOTA_REFRESH_EVENT));
}
