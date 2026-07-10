import assert from "node:assert/strict";

const baseUrl = process.env.APP_BASE_URL ?? "http://app:8080";
const adminEmail = process.env.ADMIN_EMAIL ?? "admin@example.com";
const adminPassword = process.env.ADMIN_PASSWORD ?? "e2e-admin-password-123";
const memberEmail = process.env.MEMBER_EMAIL ?? "member@example.com";
const memberPassword = process.env.MEMBER_PASSWORD ?? "e2e-member-password-123";
const adminCookieJar = new Map<string, string>();
const memberCookieJar = new Map<string, string>();

if (process.env.E2E_PHASE === "persistence") {
  await runPersistenceCheck();
} else {
  await runInvoiceFlow();
}

async function runInvoiceFlow() {
  await waitForHealth();

  const bootstrapBefore = await api<{ initialized: boolean }>("/api/v1/auth/bootstrap-status");
  assert.equal(bootstrapBefore.initialized, false, "fresh installation must allow first-user bootstrap");

  const admin = await api<any>("/api/v1/auth/bootstrap", {
    body: JSON.stringify({
      email: adminEmail,
      password: adminPassword,
      display_name: "E2E Admin",
    }),
    headers: { "content-type": "application/json" },
    method: "POST",
  });
  assert.equal(admin.email, adminEmail);
  assert.equal(admin.role, "admin");

  const bootstrapAfter = await api<{ initialized: boolean }>("/api/v1/auth/bootstrap-status");
  assert.equal(bootstrapAfter.initialized, true);

  const member = await api<any>("/api/v1/admin/users", {
    body: JSON.stringify({
      email: memberEmail,
      password: memberPassword,
      display_name: "E2E Member",
      department: "Operations",
    }),
    headers: { "content-type": "application/json" },
    method: "POST",
  });
  assert.equal(member.role, "user", "admin-created accounts must default to ordinary users");
  assert.equal(member.status, "active");

  const sharedProject = await createProject("共享差旅", "shared", adminCookieJar);
  const adminPrivateProject = await createProject("管理员私有", "private", adminCookieJar);
  const adminProjects = await api<any[]>("/api/v1/projects");
  assert.ok(adminProjects.some((project) => project.id === sharedProject.id));
  assert.ok(adminProjects.some((project) => project.id === adminPrivateProject.id));

  await login(memberEmail, memberPassword, memberCookieJar);
  const memberPrivateProject = await createProject("成员私有", "private", memberCookieJar);
  const memberProjects = await api<any[]>("/api/v1/projects", {}, memberCookieJar);
  const memberProjectNames = new Set(memberProjects.map((project) => project.name));
  assert.ok(memberProjectNames.has("未分类"));
  assert.ok(memberProjectNames.has(sharedProject.name));
  assert.ok(memberProjectNames.has(memberPrivateProject.name));
  assert.ok(!memberProjectNames.has(adminPrivateProject.name), "ordinary users must not see another user's private project");

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

  const uploaded = await uploadInvoice({
    autoOcr: true,
    filename: "project-invoice.png",
    height: 80,
    projectId: sharedProject.id,
    width: 120,
  });

  assert.ok(uploaded.document_id);
  assert.ok(uploaded.ocr_job_id);
  assert.equal(uploaded.status, "ocr_queued");
  assert.equal(uploaded.project.id, sharedProject.id);

  const uncategorizedUpload = await uploadInvoice({
    autoOcr: false,
    filename: "uncategorized-invoice.png",
    height: 80,
    width: 121,
  });
  assert.equal(uncategorizedUpload.status, "uploaded");
  assert.equal(uncategorizedUpload.project.name, "未分类");

  const job = await waitForOcrJob(uploaded.ocr_job_id, memberCookieJar);
  assert.equal(job.status, "completed");
  assert.equal(job.request_id, "req-success-001");
  assert.ok(job.invoice_id);

  const recognized = await api<any>(`/api/v1/invoices/${job.invoice_id}`, {}, memberCookieJar);
  assertRecognizedInvoice(recognized, sharedProject.id);

  const corrected = await api<any>(`/api/v1/invoices/${job.invoice_id}/items`, {
    body: JSON.stringify({
      items: [
        {
          name: "住宿服务（已校对）",
          specification: "标准间",
          unit: "晚",
          quantity: "1",
          unit_price: "688.00",
          amount: "688.00",
          tax_rate: "0.0600",
          tax_amount: "41.28",
        },
      ],
    }),
    headers: { "content-type": "application/json" },
    method: "PUT",
  }, memberCookieJar);
  assertCorrectedInvoice(corrected, sharedProject.id, "needs_review");
  assert.ok(corrected.corrections.some((correction: any) => correction.field_path === "items"));

  const confirmed = await api<any>(`/api/v1/invoices/${job.invoice_id}/confirm`, {
    method: "POST",
  }, memberCookieJar);
  assertCorrectedInvoice(confirmed, sharedProject.id, "confirmed");
  assert.equal(confirmed.confirmed_by, member.id);
  assert.ok(confirmed.confirmed_at);

  const exportTask = await api<any>("/api/v1/exports", {
    body: JSON.stringify({
      filters: {
        project_id: sharedProject.id,
        status: ["confirmed"],
      },
      format: "json",
      include_items: true,
      include_ocr_meta: true,
      scope: "filtered_invoices",
    }),
    headers: { "content-type": "application/json" },
    method: "POST",
  }, memberCookieJar);
  const completedExport = await waitForExport(exportTask.id, memberCookieJar);
  assert.equal(completedExport.status, "completed");
  assert.equal(completedExport.filters.project_id, sharedProject.id);

  const exported = await downloadJson(`/api/v1/exports/${completedExport.id}/download`, memberCookieJar);
  assertExportPayload(exported, sharedProject.id);

  console.log("bootstrap, user, project, review, and export E2E flow passed");
}

async function runPersistenceCheck() {
  await waitForHealth();
  await loginAsAdmin();

  const users = await api<any[]>("/api/v1/admin/users");
  const member = users.find((user) => user.email === memberEmail);
  assert.ok(member, "persisted ordinary user was not found");
  assert.equal(member.role, "user");

  const projects = await api<any[]>("/api/v1/projects");
  const sharedProject = projects.find((project) => project.name === "共享差旅");
  assert.ok(sharedProject, "persisted shared project was not found");
  assert.ok(projects.some((project) => project.name === "管理员私有"));
  assert.ok(projects.some((project) => project.name === "成员私有"));

  const list = await api<any>(`/api/v1/invoices?invoice_number=12876543&project_id=${sharedProject.id}`);
  assert.ok(list.total >= 1, "persisted invoice was not found");
  const invoice = list.items.find((item: any) => item.invoice_number === "12876543");
  assert.ok(invoice, "persisted invoice summary was not found");
  assert.equal(invoice.status, "confirmed");
  assert.equal(invoice.project.id, sharedProject.id);

  const detail = await api<any>(`/api/v1/invoices/${invoice.id}`);
  assertCorrectedInvoice(detail, sharedProject.id, "confirmed");
  assert.ok(detail.corrections.some((correction: any) => correction.field_path === "items"));

  await login(memberEmail, memberPassword, memberCookieJar);
  const memberProjects = await api<any[]>("/api/v1/projects", {}, memberCookieJar);
  assert.ok(memberProjects.some((project) => project.name === "共享差旅"));
  assert.ok(memberProjects.some((project) => project.name === "成员私有"));
  assert.ok(!memberProjects.some((project) => project.name === "管理员私有"));

  const exports = await api<any[]>("/api/v1/exports", {}, memberCookieJar);
  const completedExport = exports.find(
    (task) => task.status === "completed" && task.format === "json" && task.filters.project_id === sharedProject.id,
  );
  assert.ok(completedExport, "persisted completed JSON export was not found");

  const exported = await downloadJson(`/api/v1/exports/${completedExport.id}/download`, memberCookieJar);
  assertExportPayload(exported, sharedProject.id);

  console.log("user, project, review, and export persistence check passed");
}

async function loginAsAdmin() {
  return login(adminEmail, adminPassword, adminCookieJar);
}

async function login(email: string, password: string, cookieJar: Map<string, string>) {
  cookieJar.clear();
  await api("/api/v1/auth/login", {
    body: JSON.stringify({ email, password }),
    headers: { "content-type": "application/json" },
    method: "POST",
  }, cookieJar);
}

async function createProject(name: string, visibility: "private" | "shared", cookieJar: Map<string, string>) {
  return api<any>("/api/v1/projects", {
    body: JSON.stringify({ name, visibility }),
    headers: { "content-type": "application/json" },
    method: "POST",
  }, cookieJar);
}

async function uploadInvoice(options: {
  autoOcr: boolean;
  filename: string;
  height: number;
  projectId?: string;
  width: number;
}) {
  const body = new FormData();
  body.append("file", new Blob([makePngBytes(options.width, options.height)], { type: "image/png" }), options.filename);
  body.append("scene", "travel");
  body.append("auto_ocr", String(options.autoOcr));
  if (options.projectId) {
    body.append("project_id", options.projectId);
  }
  return api<{
    document_id: string;
    ocr_job_id: string | null;
    project: { id: string; name: string };
    status: string;
  }>("/api/v1/documents", { body, method: "POST" }, memberCookieJar);
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

async function waitForOcrJob(jobId: string, cookieJar: Map<string, string>) {
  return waitFor(async () => {
    const job = await api<any>(`/api/v1/ocr-jobs/${jobId}`, {}, cookieJar);
    assert.notEqual(job.status, "failed_final", job.error_message ?? "OCR job failed");
    return job.status === "completed" ? job : null;
  }, "OCR job did not complete");
}

async function waitForExport(exportId: string, cookieJar: Map<string, string>) {
  return waitFor(async () => {
    const task = await api<any>(`/api/v1/exports/${exportId}`, {}, cookieJar);
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

async function api<T = unknown>(
  path: string,
  init: RequestInit = {},
  cookieJar: Map<string, string> = adminCookieJar,
) {
  const response = await fetch(`${baseUrl}${path}`, withCookies(init, cookieJar));
  storeCookies(response, cookieJar);
  const payload = await response.json().catch(() => ({}));
  assert.ok(response.ok, `${init.method ?? "GET"} ${path} failed: ${JSON.stringify(payload)}`);
  assert.ok(payload && typeof payload === "object" && "data" in payload, `missing data envelope for ${path}`);
  return payload.data as T;
}

async function downloadJson(path: string, cookieJar: Map<string, string>) {
  const response = await fetch(`${baseUrl}${path}`, withCookies({}, cookieJar));
  assert.ok(response.ok, `download ${path} failed: ${response.status}`);
  return response.json();
}

function assertRecognizedInvoice(detail: any, projectId: string) {
  assert.equal(detail.invoice_code, "144032216011");
  assert.equal(detail.invoice_number, "12876543");
  assert.equal(detail.invoice_date, "2026-07-09");
  assert.equal(detail.project.id, projectId);
  assert.equal(detail.status, "needs_review");
  assert.equal(detail.ocr.request_id, "req-success-001");
  assert.equal(detail.items.length, 1);
  assert.equal(detail.items[0].name, "住宿服务");
  assert.equal(detail.items[0].amount, "688.00");
}

function assertCorrectedInvoice(detail: any, projectId: string, status: string) {
  assert.equal(detail.invoice_code, "144032216011");
  assert.equal(detail.invoice_number, "12876543");
  assert.equal(detail.project.id, projectId);
  assert.equal(detail.status, status);
  assert.equal(detail.items.length, 1);
  assert.equal(detail.items[0].name, "住宿服务（已校对）");
  assert.equal(detail.items[0].specification, "标准间");
  assert.equal(Number(detail.items[0].quantity), 1);
  assert.equal(detail.items[0].amount, "688.00");
}

function assertExportPayload(exported: any, projectId: string) {
  assert.equal(exported.export_metadata.invoice_count, 1);
  assert.equal(exported.export_metadata.filters.project_id, projectId);
  assert.equal(exported.invoices[0].invoice_number, "12876543");
  assert.equal(exported.invoices[0].project_id, projectId);
  assert.equal(exported.invoices[0].status, "confirmed");
  assert.equal(exported.items[0].name, "住宿服务（已校对）");
  assert.equal(exported.ocr_jobs[0].request_id, "req-success-001");
}

function withCookies(init: RequestInit, cookieJar: Map<string, string>): RequestInit {
  const headers = new Headers(init.headers);
  if (cookieJar.size) {
    headers.set("cookie", Array.from(cookieJar, ([key, value]) => `${key}=${value}`).join("; "));
  }
  return { ...init, headers };
}

function storeCookies(response: Response, cookieJar: Map<string, string>) {
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
