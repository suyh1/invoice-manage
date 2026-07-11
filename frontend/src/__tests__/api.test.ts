import { afterEach, describe, expect, it, vi } from "vitest";

import { apiPostForm } from "../lib/api";

describe("apiPostForm", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("lets the browser set the multipart content type and boundary", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ data: { ok: true } }), {
        headers: { "content-type": "application/json" },
        status: 200,
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const body = new FormData();
    body.append("file", new File(["invoice"], "invoice.pdf", { type: "application/pdf" }));

    await apiPostForm<{ ok: boolean }>("/api/v1/documents", body);

    const request = fetchMock.mock.calls[0]?.[1] as RequestInit;
    expect(request.body).toBe(body);
    expect(new Headers(request.headers).has("content-type")).toBe(false);
  });
});
