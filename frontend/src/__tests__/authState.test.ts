import { describe, expect, it } from "vitest";

import { ApiError } from "../lib/api";
import {
  authErrorMessage,
  loadAuthSnapshot,
  resolveAuthScreen,
  type AuthUser,
} from "../auth/authState";

const admin: AuthUser = {
  id: "admin-id",
  email: "admin@example.com",
  display_name: "系统管理员",
  role: "admin",
};

describe("resolveAuthScreen", () => {
  it("shows loading while bootstrap status is unresolved", () => {
    expect(resolveAuthScreen({ initialized: null, user: null })).toBe("loading");
  });

  it("shows bootstrap before the first user exists", () => {
    expect(resolveAuthScreen({ initialized: false, user: null })).toBe("bootstrap");
  });

  it("shows login after initialization without a session", () => {
    expect(resolveAuthScreen({ initialized: true, user: null })).toBe("login");
  });

  it("shows the workspace for an authenticated user", () => {
    expect(resolveAuthScreen({ initialized: true, user: admin })).toBe("workspace");
  });
});

describe("authErrorMessage", () => {
  it("translates credential and disabled-account errors into actionable Chinese copy", () => {
    expect(authErrorMessage("AUTH_INVALID_CREDENTIALS")).toBe("邮箱或密码不正确，请重新输入。");
    expect(authErrorMessage("AUTH_USER_DISABLED")).toBe("此账号已停用，请联系管理员恢复访问权限。");
    expect(authErrorMessage("AUTH_BOOTSTRAP_COMPLETE")).toBe("系统已完成初始化，请使用已有账号登录。");
  });

  it("uses a recoverable fallback for unknown failures", () => {
    expect(authErrorMessage("API_ERROR")).toBe("暂时无法完成登录，请稍后重试。");
  });
});

describe("loadAuthSnapshot", () => {
  it("does not request the current user before system initialization", async () => {
    const paths: string[] = [];
    const request = async <T>(path: string): Promise<T> => {
      paths.push(path);
      return { initialized: false } as T;
    };

    await expect(loadAuthSnapshot(request)).resolves.toEqual({ initialized: false, user: null });
    expect(paths).toEqual(["/api/v1/auth/bootstrap-status"]);
  });

  it("restores an authenticated user after initialization", async () => {
    const request = async <T>(path: string): Promise<T> => {
      if (path.endsWith("bootstrap-status")) {
        return { initialized: true } as T;
      }
      return admin as T;
    };

    await expect(loadAuthSnapshot(request)).resolves.toEqual({ initialized: true, user: admin });
  });

  it("treats an expired session as signed out and preserves other failures", async () => {
    const signedOutRequest = async <T>(path: string): Promise<T> => {
      if (path.endsWith("bootstrap-status")) {
        return { initialized: true } as T;
      }
      throw new ApiError(401, "AUTH_REQUIRED", "Authentication required");
    };
    await expect(loadAuthSnapshot(signedOutRequest)).resolves.toEqual({ initialized: true, user: null });

    const unavailableRequest = async <T>(path: string): Promise<T> => {
      if (path.endsWith("bootstrap-status")) {
        return { initialized: true } as T;
      }
      throw new ApiError(503, "SERVICE_UNAVAILABLE", "Unavailable");
    };
    await expect(loadAuthSnapshot(unavailableRequest)).rejects.toMatchObject({ status: 503 });
  });
});
