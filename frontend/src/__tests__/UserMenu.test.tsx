import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { UserMenu } from "../components/UserMenu";
import type { AuthUser } from "../auth/authState";

const admin: AuthUser = {
  id: "admin-id",
  email: "admin@example.com",
  display_name: "系统管理员",
  role: "admin",
};

describe("UserMenu", () => {
  it("renders identity, role, password change, and logout controls", () => {
    const markup = renderToStaticMarkup(
      <UserMenu user={admin} onChangePassword={async () => undefined} onLogout={async () => undefined} />,
    );

    expect(markup).toContain("系统管理员");
    expect(markup).toContain("管理员");
    expect(markup).toContain("admin@example.com");
    expect(markup).toContain("修改密码");
    expect(markup).toContain("退出登录");
    expect(markup).toContain('autoComplete="current-password"');
    expect(markup.match(/autoComplete="new-password"/g)).toHaveLength(2);
  });
});
