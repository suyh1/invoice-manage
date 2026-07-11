// @ts-expect-error Vitest runs in Node; the browser app intentionally omits Node type declarations.
import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

const detailPage = readFileSync(new URL("../pages/InvoiceDetailPage.tsx", import.meta.url), "utf8");
const fieldEditor = readFileSync(new URL("../components/FieldEditor.tsx", import.meta.url), "utf8");
const styles = readFileSync(new URL("../styles.css", import.meta.url), "utf8");

describe("OCR field presentation", () => {
  it("shows source field names and useful supplemental invoice fields", () => {
    expect(fieldEditor).toContain("ocrSource");
    expect(fieldEditor).toContain("原始字段：");
    expect(fieldEditor).toContain("OCR值：");
    expect(fieldEditor).not.toContain("腾讯字段");
    expect(fieldEditor).not.toContain("腾讯未返回对应字段");
    expect(detailPage).toContain("supplemental_fields");
    expect(detailPage).toContain("补充识别信息");
    expect(styles).toContain(".ocr-supplemental-grid");
  });

  it("does not dump technical raw OCR response JSON in the review workflow", () => {
    expect(detailPage).not.toContain("查看腾讯 OCR 原始响应");
    expect(detailPage).not.toContain("formatJson(");
  });
});
