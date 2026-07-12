// @vitest-environment jsdom

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { OcrQuotaStatus } from "../components/OcrQuotaStatus";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("OcrQuotaStatus", () => {
  it("renders used quota against total quota as an accessible progress bar", async () => {
    mockQuotaStatus({ level: "none", quota_total: 1000, quota_used: 250, used_percent: 25 });

    const { container } = render(<OcrQuotaStatus compact />);

    await screen.findByText("250/1000");
    const progress = screen.getByRole("progressbar", { name: "OCR 额度使用情况" });
    expect(progress.getAttribute("aria-valuenow")).toBe("250");
    expect(progress.getAttribute("aria-valuemax")).toBe("1000");
    expect((container.querySelector(".quota-progress-fill") as HTMLElement).style.width).toBe("25%");
  });

  it("uses the threshold state and clamps the fill percentage", async () => {
    mockQuotaStatus({ level: "warning", quota_total: 1000, quota_used: 800, used_percent: 125 });

    const { container } = render(<OcrQuotaStatus />);

    await screen.findByText("800/1000");
    expect(container.querySelector(".quota-status")?.classList.contains("warning")).toBe(true);
    expect((container.querySelector(".quota-progress-fill") as HTMLElement).style.width).toBe("100%");
  });

  it("keeps an empty hollow track when quota is not configured", async () => {
    const fetchMock = mockQuotaStatus({ level: "none", quota_total: null, quota_used: null, used_percent: null });

    const { container } = render(<OcrQuotaStatus />);

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    expect(screen.getByText("--/--")).toBeTruthy();
    expect(screen.queryByRole("progressbar")).toBeNull();
    expect((container.querySelector(".quota-progress-fill") as HTMLElement).style.width).toBe("0%");
  });
});

function mockQuotaStatus(data: {
  level: "none" | "warning" | "critical";
  quota_total: number | null;
  quota_used: number | null;
  used_percent: number | null;
}) {
  const fetchMock = vi.fn().mockResolvedValue(
    new Response(JSON.stringify({ data }), { status: 200 }),
  );
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}
