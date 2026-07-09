export class ApiError extends Error {
  status: number;
  code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

type ErrorEnvelope = { error?: { code?: string; message?: string } };

export async function apiGet<T>(path: string): Promise<T> {
  return apiRequest<T>(path);
}

export async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  return apiRequest<T>(path, { method: "POST", body: body ? JSON.stringify(body) : undefined });
}

export async function apiPatch<T>(path: string, body: unknown): Promise<T> {
  return apiRequest<T>(path, { method: "PATCH", body: JSON.stringify(body) });
}

async function apiRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !headers.has("content-type")) {
    headers.set("content-type", "application/json");
  }

  const response = await fetch(path, {
    credentials: "include",
    ...init,
    headers,
  });
  const payload = (await response.json().catch(() => ({}))) as unknown;
  if (!response.ok) {
    const errorPayload = payload as ErrorEnvelope;
    throw new ApiError(
      response.status,
      errorPayload.error?.code ?? "API_ERROR",
      errorPayload.error?.message ?? "请求失败",
    );
  }
  if (!isApiEnvelope<T>(payload)) {
    throw new ApiError(response.status, "API_INVALID_RESPONSE", "后端响应格式异常。");
  }
  return payload.data;
}

function isApiEnvelope<T>(payload: unknown): payload is { data: T } {
  return typeof payload === "object" && payload !== null && Object.prototype.hasOwnProperty.call(payload, "data");
}
