import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { AuthLandingPage, AuthStatusPage } from "../pages/AuthLandingPage";

const noop = async () => undefined;

describe("AuthLandingPage", () => {
  it("renders a focused login surface without unsupported account actions", () => {
    const markup = renderToStaticMarkup(
      <AuthLandingPage mode="login" busy={false} errorMessage={null} onBootstrap={noop} onLogin={noop} />,
    );

    expect(markup).toContain("Invoice OCR 发票管理系统");
    expect(markup).toContain("登录系统");
    expect(markup).toContain('autoComplete="username"');
    expect(markup).toContain('autoComplete="current-password"');
    expect(markup).toContain("账号由管理员创建");
    expect(markup).toContain("/auth-paper-index.webp");
    expect(markup).not.toContain("记住我");
    expect(markup).not.toContain("忘记密码");
    expect(markup).not.toContain("注册");
  });

  it("renders the first-administrator bootstrap contract", () => {
    const markup = renderToStaticMarkup(
      <AuthLandingPage mode="bootstrap" busy={false} errorMessage={null} onBootstrap={noop} onLogin={noop} />,
    );

    expect(markup).toContain("创建首位管理员");
    expect(markup).toContain("公开注册将自动关闭");
    expect(markup).toContain('autoComplete="name"');
    expect(markup.match(/autoComplete="new-password"/g)).toHaveLength(2);
    expect(markup).toContain("创建管理员并进入系统");
  });

  it("announces authentication errors and locks duplicate submissions", () => {
    const markup = renderToStaticMarkup(
      <AuthLandingPage
        mode="login"
        busy
        errorMessage="邮箱或密码不正确，请重新输入。"
        onBootstrap={noop}
        onLogin={noop}
      />,
    );

    expect(markup).toContain('role="alert"');
    expect(markup).toContain("邮箱或密码不正确，请重新输入。");
    expect(markup).toContain("正在登录...");
    expect(markup).toContain("disabled");
  });
});

describe("AuthStatusPage", () => {
  it("keeps an announced loading skeleton while authentication resolves", () => {
    const markup = renderToStaticMarkup(<AuthStatusPage mode="loading" onRetry={noop} />);

    expect(markup).toContain("正在确认系统状态");
    expect(markup).toContain('aria-live="polite"');
    expect(markup).toContain('aria-busy="true"');
  });

  it("offers a concrete recovery action when the service is unavailable", () => {
    const markup = renderToStaticMarkup(<AuthStatusPage mode="error" onRetry={noop} />);

    expect(markup).toContain("暂时无法连接");
    expect(markup).toContain("重新尝试");
    expect(markup).toContain('type="button"');
  });
});
