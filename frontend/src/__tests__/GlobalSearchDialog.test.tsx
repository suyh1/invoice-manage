// @vitest-environment jsdom

import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { appRoutes } from "../app/router";
import { AppShell } from "../components/AppShell";
import { apiGet } from "../lib/api";


vi.mock("../auth/AuthContext", () => ({
  useAuth: () => ({
    user: { id: "user-1", email: "user@example.com", display_name: "测试用户", role: "user" },
    changePassword: vi.fn(),
    logout: vi.fn(),
  }),
}));

vi.mock("../lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../lib/api")>();
  return { ...actual, apiGet: vi.fn() };
});

const searchResults = {
  invoices: [
    {
      id: "invoice-1",
      invoice_number: "12876543",
      invoice_code: "144032216011",
      seller_name: "上海云栖酒店",
      buyer_name: "星河科技有限公司",
      amount_with_tax: "729.28",
    },
  ],
  projects: [{ id: "project-1", name: "云栖差旅", description: "上海酒店发票" }],
  suppliers: [{ name: "上海云栖酒店", invoice_count: 2 }],
};

describe("global search command", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.mocked(apiGet).mockReset();
    window.location.hash = "#/";
  });

  afterEach(() => {
    cleanup();
    vi.useRealTimers();
  });

  it("opens from the top bar, searches grouped results, and supports keyboard navigation", async () => {
    vi.mocked(apiGet).mockImplementation((path) => Promise.resolve(path.startsWith("/api/v1/search") ? searchResults : []));
    render(<AppShell activeRoute={appRoutes[0]}><div>页面内容</div></AppShell>);

    fireEvent.click(screen.getByRole("button", { name: /搜索发票、项目或供应商/ }));
    const input = screen.getByRole("searchbox", { name: "全局搜索" });
    fireEvent.change(input, { target: { value: "云栖" } });
    await act(async () => vi.advanceTimersByTimeAsync(220));

    expect(apiGet).toHaveBeenCalledWith("/api/v1/search?q=%E4%BA%91%E6%A0%96&limit=6");
    expect(screen.getByText("发票")).toBeTruthy();
    expect(screen.getByText("项目")).toBeTruthy();
    expect(screen.getByText("供应商")).toBeTruthy();

    fireEvent.keyDown(input, { key: "Enter" });
    expect(window.location.hash).toBe("#/invoices/invoice-1");
  });

  it("opens with the platform shortcut and closes with Escape", () => {
    vi.mocked(apiGet).mockResolvedValue([]);
    render(<AppShell activeRoute={appRoutes[0]}><div>页面内容</div></AppShell>);

    fireEvent.keyDown(window, { key: "k", metaKey: true });
    expect(screen.getByRole("dialog", { name: "全局搜索" })).toBeTruthy();

    fireEvent.keyDown(window, { key: "Escape" });
    expect(screen.queryByRole("dialog", { name: "全局搜索" })).toBeNull();
  });

  it("shows empty and request-error states", async () => {
    let searchAttempt = 0;
    vi.mocked(apiGet).mockImplementation((path) => {
      if (!path.startsWith("/api/v1/search")) return Promise.resolve([]);
      searchAttempt += 1;
      return searchAttempt === 1
        ? Promise.resolve({ invoices: [], projects: [], suppliers: [] })
        : Promise.reject(new Error("offline"));
    });
    render(<AppShell activeRoute={appRoutes[0]}><div>页面内容</div></AppShell>);

    fireEvent.click(screen.getByRole("button", { name: /搜索发票、项目或供应商/ }));
    const input = screen.getByRole("searchbox", { name: "全局搜索" });
    fireEvent.change(input, { target: { value: "没有" } });
    await act(async () => vi.advanceTimersByTimeAsync(220));
    expect(screen.getByText("没有找到匹配结果")).toBeTruthy();

    fireEvent.change(input, { target: { value: "断网" } });
    await act(async () => vi.advanceTimersByTimeAsync(220));
    expect(screen.getByRole("alert").textContent).toContain("暂时无法完成搜索");
  });
});
