import { apiGet } from "./api";
import { notifyOcrQuotaRefresh } from "./ocrQuotaRefresh";

export type OcrJobQuotaSnapshot = {
  attempt_count: number;
  status: string;
};

type WatchOptions = {
  request?: (path: string) => Promise<OcrJobQuotaSnapshot>;
  wait?: (ms: number) => Promise<unknown>;
  maxChecks?: number;
};

const providerResultStatuses = new Set(["completed", "failed_final", "failed", "retry_scheduled"]);
const terminalStatuses = new Set(["completed", "failed_final", "failed", "canceled"]);

export function refreshQuotaForOcrJob(job: OcrJobQuotaSnapshot, lastAttempt: number) {
  if (providerResultStatuses.has(job.status) && job.attempt_count > lastAttempt) {
    notifyOcrQuotaRefresh();
    return job.attempt_count;
  }
  return lastAttempt;
}

export async function watchOcrJobQuota(jobId: string, options: WatchOptions = {}) {
  const request = options.request ?? ((path: string) => apiGet<OcrJobQuotaSnapshot>(path));
  const wait = options.wait ?? delay;
  const maxChecks = options.maxChecks ?? 24;
  let lastRefreshAttempt = 0;

  for (let check = 0; check < maxChecks; check += 1) {
    await wait(check === 0 ? 1000 : 2500);
    let job: OcrJobQuotaSnapshot;
    try {
      job = await request(`/api/v1/ocr-jobs/${jobId}`);
    } catch {
      return;
    }
    lastRefreshAttempt = refreshQuotaForOcrJob(job, lastRefreshAttempt);
    if (terminalStatuses.has(job.status)) {
      return;
    }
  }
}

function delay(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
