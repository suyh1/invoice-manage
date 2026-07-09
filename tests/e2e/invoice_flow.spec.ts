import assert from "node:assert/strict";

const baseUrl = process.env.APP_BASE_URL ?? "http://app:8080";
const adminEmail = process.env.ADMIN_EMAIL ?? "admin@example.com";
const adminPassword = process.env.ADMIN_PASSWORD ?? "change-me";
const cookieJar = new Map<string, string>();

if (process.env.E2E_PHASE === "persistence") {
  await runPersistenceCheck();
} else {
  await runInvoiceFlow();
}

async function runInvoiceFlow() {
  await waitForHealth();
  await loginAsAdmin();

  await api("/api/v1/admin/ocr-providers", {
    body: JSON.stringify({
      display_name: "Mock OCR",
      enabled: true,
      is_default: true,
      provider: "mock",
      qps_limit: 100,
      quota: {
        free_quota_total: 1000,
        free_quota_used: 0,
        quota_warning_percent: 80,
        quota_warning_remaining: 100,
        source: "manual",
      },
    }),
    headers: { "content-type": "application/json" },
    method: "POST",
  });

  const uploadBody = new FormData();
  uploadBody.append("file", new Blob([makePngBytes(120, 80)], { type: "image/png" }), "invoice.png");
  uploadBody.append("scene", "travel");
  uploadBody.append("auto_ocr", "true");
  const uploaded = await api<{
    document_id: string;
    ocr_job_id: string | null;
    status: string;
  }>("/api/v1/documents", { body: uploadBody, method: "POST" });

  assert.ok(uploaded.document_id);
  assert.ok(uploaded.ocr_job_id);
  assert.equal(uploaded.status, "ocr_queued");

  const job = await waitForOcrJob(uploaded.ocr_job_id);
  assert.equal(job.status, "completed");
  assert.equal(job.request_id, "req-success-001");
  assert.ok(job.invoice_id);

  const detail = await api<any>(`/api/v1/invoices/${job.invoice_id}`);
  assertInvoiceDetail(detail);

  const exportTask = await api<any>("/api/v1/exports", {
    body: JSON.stringify({
      filters: { status: ["needs_review"] },
      format: "json",
      include_items: true,
      include_ocr_meta: true,
      scope: "filtered_invoices",
    }),
    headers: { "content-type": "application/json" },
    method: "POST",
  });
  const completedExport = await waitForExport(exportTask.id);
  assert.equal(completedExport.status, "completed");

  const exported = await downloadJson(`/api/v1/exports/${completedExport.id}/download`);
  assertExportPayload(exported);

  console.log("invoice OCR E2E flow passed");
}

async function runPersistenceCheck() {
  await waitForHealth();
  await loginAsAdmin();

  const list = await api<any>("/api/v1/invoices?invoice_number=12876543");
  assert.ok(list.total >= 1, "persisted invoice was not found");
  const invoice = list.items.find((item: any) => item.invoice_number === "12876543");
  assert.ok(invoice, "persisted invoice summary was not found");

  const detail = await api<any>(`/api/v1/invoices/${invoice.id}`);
  assertInvoiceDetail(detail);

  const exports = await api<any[]>("/api/v1/exports");
  const completedExport = exports.find((task) => task.status === "completed" && task.format === "json");
  assert.ok(completedExport, "persisted completed JSON export was not found");

  const exported = await downloadJson(`/api/v1/exports/${completedExport.id}/download`);
  assertExportPayload(exported);

  console.log("invoice OCR persistence check passed");
}

async function loginAsAdmin() {
  await api("/api/v1/auth/login", {
    body: JSON.stringify({ email: adminEmail, password: adminPassword }),
    headers: { "content-type": "application/json" },
    method: "POST",
  });
}

async function waitForHealth() {
  for (let attempt = 0; attempt < 40; attempt += 1) {
    try {
      const response = await fetch(`${baseUrl}/healthz`);
      if (response.ok) {
        return;
      }
    } catch {
      // Keep waiting.
    }
    await delay(1000);
  }
  throw new Error("app did not become healthy");
}

async function waitForOcrJob(jobId: string) {
  return waitFor(async () => {
    const job = await api<any>(`/api/v1/ocr-jobs/${jobId}`);
    assert.notEqual(job.status, "failed_final", job.error_message ?? "OCR job failed");
    return job.status === "completed" ? job : null;
  }, "OCR job did not complete");
}

async function waitForExport(exportId: string) {
  return waitFor(async () => {
    const task = await api<any>(`/api/v1/exports/${exportId}`);
    assert.notEqual(task.status, "failed", "export task failed");
    return task.status === "completed" ? task : null;
  }, "export task did not complete");
}

async function waitFor<T>(probe: () => Promise<T | null>, failureMessage: string) {
  for (let attempt = 0; attempt < 40; attempt += 1) {
    const value = await probe();
    if (value) {
      return value;
    }
    await delay(1000);
  }
  throw new Error(failureMessage);
}

async function api<T = unknown>(path: string, init: RequestInit = {}) {
  const response = await fetch(`${baseUrl}${path}`, withCookies(init));
  storeCookies(response);
  const payload = await response.json().catch(() => ({}));
  assert.ok(response.ok, `${init.method ?? "GET"} ${path} failed: ${JSON.stringify(payload)}`);
  assert.ok(payload && typeof payload === "object" && "data" in payload, `missing data envelope for ${path}`);
  return payload.data as T;
}

async function downloadJson(path: string) {
  const response = await fetch(`${baseUrl}${path}`, withCookies({}));
  assert.ok(response.ok, `download ${path} failed: ${response.status}`);
  return response.json();
}

function assertInvoiceDetail(detail: any) {
  assert.equal(detail.invoice_code, "144032216011");
  assert.equal(detail.invoice_number, "12876543");
  assert.equal(detail.invoice_date, "2026-07-09");
  assert.equal(detail.ocr.request_id, "req-success-001");
  assert.equal(detail.items.length, 1);
  assert.equal(detail.items[0].name, "住宿服务");
  assert.equal(detail.items[0].amount, "688.00");
}

function assertExportPayload(exported: any) {
  assert.equal(exported.export_metadata.invoice_count, 1);
  assert.equal(exported.invoices[0].invoice_number, "12876543");
  assert.equal(exported.items[0].name, "住宿服务");
  assert.equal(exported.ocr_jobs[0].request_id, "req-success-001");
}

function withCookies(init: RequestInit): RequestInit {
  const headers = new Headers(init.headers);
  if (cookieJar.size) {
    headers.set("cookie", Array.from(cookieJar, ([key, value]) => `${key}=${value}`).join("; "));
  }
  return { ...init, headers };
}

function storeCookies(response: Response) {
  const headerApi = response.headers as Headers & { getSetCookie?: () => string[] };
  const setCookies = headerApi.getSetCookie ? headerApi.getSetCookie() : [response.headers.get("set-cookie")].filter(Boolean) as string[];
  for (const setCookie of setCookies) {
    const [cookie] = setCookie.split(";");
    const separator = cookie.indexOf("=");
    if (separator === -1) {
      continue;
    }
    const key = cookie.slice(0, separator);
    const value = cookie.slice(separator + 1);
    cookieJar.set(key, value);
  }
}

function makePngBytes(width: number, height: number) {
  const bytes = new Uint8Array(33);
  bytes.set([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a], 0);
  bytes.set([0x00, 0x00, 0x00, 0x0d], 8);
  bytes.set([0x49, 0x48, 0x44, 0x52], 12);
  bytes[16] = (width >>> 24) & 0xff;
  bytes[17] = (width >>> 16) & 0xff;
  bytes[18] = (width >>> 8) & 0xff;
  bytes[19] = width & 0xff;
  bytes[20] = (height >>> 24) & 0xff;
  bytes[21] = (height >>> 16) & 0xff;
  bytes[22] = (height >>> 8) & 0xff;
  bytes[23] = height & 0xff;
  return bytes;
}

function delay(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
