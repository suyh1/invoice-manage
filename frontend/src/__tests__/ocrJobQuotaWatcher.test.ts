import { beforeEach, describe, expect, it, vi } from "vitest";

import { notifyOcrQuotaRefresh } from "../lib/ocrQuotaRefresh";
import {
  refreshQuotaForOcrJob,
  watchOcrJobQuota,
  type OcrJobQuotaSnapshot,
} from "../lib/ocrJobQuotaWatcher";

vi.mock("../lib/ocrQuotaRefresh", () => ({ notifyOcrQuotaRefresh: vi.fn() }));

beforeEach(() => {
  vi.mocked(notifyOcrQuotaRefresh).mockReset();
});

describe("OCR job quota watcher", () => {
  it.each(["completed", "failed_final", "failed"])("refreshes for %s results", (status) => {
    const lastAttempt = refreshQuotaForOcrJob({ attempt_count: 1, status }, 0);

    expect(lastAttempt).toBe(1);
    expect(notifyOcrQuotaRefresh).toHaveBeenCalledTimes(1);
  });

  it("refreshes once per returned retry attempt", () => {
    let lastAttempt = 0;

    lastAttempt = refreshQuotaForOcrJob({ attempt_count: 1, status: "retry_scheduled" }, lastAttempt);
    lastAttempt = refreshQuotaForOcrJob({ attempt_count: 1, status: "retry_scheduled" }, lastAttempt);
    lastAttempt = refreshQuotaForOcrJob({ attempt_count: 2, status: "retry_scheduled" }, lastAttempt);

    expect(lastAttempt).toBe(2);
    expect(notifyOcrQuotaRefresh).toHaveBeenCalledTimes(2);
  });

  it.each(["queued", "running", "canceled"])("does not refresh for %s", (status) => {
    const lastAttempt = refreshQuotaForOcrJob({ attempt_count: 1, status }, 0);

    expect(lastAttempt).toBe(0);
    expect(notifyOcrQuotaRefresh).not.toHaveBeenCalled();
  });

  it("polls through retries and stops after a terminal result", async () => {
    const snapshots: OcrJobQuotaSnapshot[] = [
      { attempt_count: 1, status: "retry_scheduled" },
      { attempt_count: 1, status: "retry_scheduled" },
      { attempt_count: 2, status: "running" },
      { attempt_count: 2, status: "completed" },
    ];
    const request = vi.fn(async () => snapshots.shift() ?? { attempt_count: 2, status: "completed" });
    const wait = vi.fn(async () => undefined);

    await watchOcrJobQuota("job-1", { request, wait });

    expect(request).toHaveBeenCalledTimes(4);
    expect(wait).toHaveBeenCalledTimes(4);
    expect(notifyOcrQuotaRefresh).toHaveBeenCalledTimes(2);
  });

  it("stops quietly when polling fails", async () => {
    const request = vi.fn(async () => {
      throw new Error("network unavailable");
    });

    await expect(watchOcrJobQuota("job-1", { request, wait: async () => undefined })).resolves.toBeUndefined();
    expect(request).toHaveBeenCalledTimes(1);
    expect(notifyOcrQuotaRefresh).not.toHaveBeenCalled();
  });
});
