// @vitest-environment jsdom

import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";

import { AuthLandingPage, AuthStatusPage } from "../pages/AuthLandingPage";

const noop = async () => undefined;

afterEach(() => {
  cleanup();
  document.body.style.overflow = "";
});

describe("AuthLandingPage", () => {
  it("renders the motion landing contract without fake social proof", () => {
    const { container } = render(
      <AuthLandingPage mode="login" busy={false} errorMessage={null} onBootstrap={noop} onLogin={noop} />,
    );

    expect(screen.getByRole("heading", { name: "Every invoice, traceable." })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Menu" })).toBeTruthy();
    expect(screen.getByText("围绕企业财务流程构建")).toBeTruthy();
    expect(container.querySelectorAll(".motion-line-left")).toHaveLength(20);
    expect(container.querySelectorAll(".motion-line-right")).toHaveLength(20);
    expect(container.querySelectorAll(".motion-line-top")).toHaveLength(40);
    expect(screen.queryByText("Partnered with top-tier companies globally")).toBeNull();
    expect(screen.queryByText("Airbnb")).toBeNull();
  });

  it("raises and retains the glass panel after the first field focus", async () => {
    const user = userEvent.setup();
    render(<AuthLandingPage mode="login" busy={false} errorMessage={null} onBootstrap={noop} onLogin={noop} />);
    const panel = screen.getByRole("region", { name: "登录系统" });

    expect(panel.getAttribute("data-engaged")).toBe("false");
    await user.click(screen.getByLabelText("邮箱"));
    expect(panel.getAttribute("data-engaged")).toBe("true");
    await user.click(screen.getByLabelText("密码"));
    expect(panel.getAttribute("data-engaged")).toBe("true");
  });

  it("opens and closes the fullscreen menu with Escape", async () => {
    const user = userEvent.setup();
    render(<AuthLandingPage mode="login" busy={false} errorMessage={null} onBootstrap={noop} onLogin={noop} />);

    await user.click(screen.getByRole("button", { name: "Menu" }));
    expect(screen.getByRole("dialog", { name: "首页导航" })).toBeTruthy();
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog", { name: "首页导航" })).toBeNull();
  });

  it("keeps the existing login field and unsupported-action contract", () => {
    render(<AuthLandingPage mode="login" busy={false} errorMessage={null} onBootstrap={noop} onLogin={noop} />);

    expect(screen.getByRole("heading", { name: "登录系统" })).toBeTruthy();
    expect(screen.getByLabelText("邮箱").getAttribute("autocomplete")).toBe("username");
    expect(screen.getByLabelText("密码").getAttribute("autocomplete")).toBe("current-password");
    expect(screen.getByText(/账号由管理员创建/)).toBeTruthy();
    expect(screen.queryByText("记住我")).toBeNull();
    expect(screen.queryByText("忘记密码")).toBeNull();
    expect(screen.queryByText("注册")).toBeNull();
  });

  it("renders the first-administrator bootstrap contract as engaged glass", () => {
    render(<AuthLandingPage mode="bootstrap" busy={false} errorMessage={null} onBootstrap={noop} onLogin={noop} />);
    const panel = screen.getByRole("region", { name: "创建首位管理员" });

    expect(panel.getAttribute("data-engaged")).toBe("true");
    expect(screen.getByText(/公开注册将自动关闭/)).toBeTruthy();
    expect(screen.getByLabelText("姓名").getAttribute("autocomplete")).toBe("name");
    expect(document.querySelectorAll('input[autocomplete="new-password"]')).toHaveLength(2);
    expect(screen.getByRole("button", { name: /创建管理员并进入系统/ })).toBeTruthy();
  });

  it("announces authentication errors, engages the panel, and locks duplicate submissions", () => {
    render(
      <AuthLandingPage
        mode="login"
        busy
        errorMessage="邮箱或密码不正确，请重新输入。"
        onBootstrap={noop}
        onLogin={noop}
      />,
    );

    expect(screen.getByRole("alert").textContent).toContain("邮箱或密码不正确，请重新输入。");
    expect(screen.getByRole("region", { name: "登录系统" }).getAttribute("data-engaged")).toBe("true");
    expect(screen.getByRole("button", { name: /正在登录/ }).hasAttribute("disabled")).toBe(true);
  });
});

describe("AuthStatusPage", () => {
  it("keeps an announced loading state inside the shared motion shell", () => {
    const { container } = render(<AuthStatusPage mode="loading" onRetry={noop} />);
    const panel = screen.getByRole("region", { name: "正在确认系统状态" });

    expect(panel.getAttribute("aria-live")).toBe("polite");
    expect(panel.getAttribute("aria-busy")).toBe("true");
    expect(panel.getAttribute("data-engaged")).toBe("true");
    expect(container.querySelectorAll(".motion-line-left")).toHaveLength(20);
    expect(screen.getByRole("heading", { name: "Every invoice, traceable." })).toBeTruthy();
  });

  it("offers a concrete recovery action inside the shared motion shell", () => {
    render(<AuthStatusPage mode="error" onRetry={noop} />);

    expect(screen.getByRole("region", { name: "暂时无法连接" }).getAttribute("data-engaged")).toBe("true");
    expect(screen.getByRole("button", { name: "重新尝试" }).getAttribute("type")).toBe("button");
  });
});
