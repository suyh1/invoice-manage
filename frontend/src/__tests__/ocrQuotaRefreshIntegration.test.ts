// @ts-expect-error Vitest runs in Node; the browser app intentionally omits Node type declarations.
import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

const uploadPage = readFileSync(new URL("../pages/UploadPage.tsx", import.meta.url), "utf8");
const reviewQueuePage = readFileSync(new URL("../pages/ReviewQueuePage.tsx", import.meta.url), "utf8");

describe("OCR quota refresh integration", () => {
  it("connects upload polling to the per-attempt quota observer", () => {
    expect(uploadPage).toContain("refreshQuotaForOcrJob");
    expect(uploadPage).toContain("lastQuotaRefreshAttempt = refreshQuotaForOcrJob(job, lastQuotaRefreshAttempt)");
  });

  it("starts a quota watcher after a review retry is accepted", () => {
    expect(reviewQueuePage).toContain("watchOcrJobQuota");
    expect(reviewQueuePage).toContain("void watchOcrJobQuota(item.ocr.id)");
  });
});
