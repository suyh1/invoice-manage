// @vitest-environment jsdom

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { OcrProviderSettings } from "../components/OcrProviderSettings";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("OcrProviderSettings", () => {
  it("presents provider management as row actions with an add dialog command", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            data: [
              {
                id: "provider-1",
                provider: "tencent",
                display_name: "腾讯云 OCR",
                enabled: true,
                is_default: true,
                configured: true,
                credential_fingerprint: "sha256:123456789abc",
                endpoint: "ocr.tencentcloudapi.com",
                region: "ap-guangzhou",
                action: "VatInvoiceOCR",
                api_version: "2018-11-19",
                qps_limit: 8,
                last_test_status: null,
                quota: {
                  source: "manual",
                  free_quota_total: 1000,
                  free_quota_used: 4,
                  free_quota_remaining: 996,
                  used_percent: 0,
                  warning_percent: 80,
                  warning_remaining: 100,
                  alert_level: "none",
                },
              },
            ],
          }),
          { status: 200 },
        ),
      ),
    );

    render(<OcrProviderSettings />);

    await waitFor(() => expect(screen.getByText("腾讯云 OCR")).toBeTruthy());
    expect(screen.getByRole("button", { name: /新增配置/ })).toBeTruthy();
    expect(screen.getByRole("button", { name: /查看腾讯云 OCR/ })).toBeTruthy();
    expect(screen.getByRole("button", { name: /编辑腾讯云 OCR/ })).toBeTruthy();
    expect(screen.getByRole("button", { name: /删除腾讯云 OCR/ })).toBeTruthy();
    expect(screen.getByText("996")).toBeTruthy();
  });
});
