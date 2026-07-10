export type UserRole = "user" | "finance" | "admin";

export type AuthUser = {
  id: string;
  email: string;
  display_name: string;
  role: UserRole;
};

export type AuthScreen = "loading" | "bootstrap" | "login" | "workspace";

export type AuthSnapshot = {
  initialized: boolean;
  user: AuthUser | null;
};

type AuthRequest = <T>(path: string) => Promise<T>;

export function resolveAuthScreen({
  initialized,
  user,
}: {
  initialized: boolean | null;
  user: AuthUser | null;
}): AuthScreen {
  if (initialized === null) {
    return "loading";
  }
  if (!initialized) {
    return "bootstrap";
  }
  return user ? "workspace" : "login";
}

const authErrorMessages: Record<string, string> = {
  AUTH_BOOTSTRAP_COMPLETE: "系统已完成初始化，请使用已有账号登录。",
  AUTH_INVALID_CREDENTIALS: "邮箱或密码不正确，请重新输入。",
  AUTH_PASSWORD_INCORRECT: "当前密码不正确，请重新输入。",
  AUTH_USER_DISABLED: "此账号已停用，请联系管理员恢复访问权限。",
};

export function authErrorMessage(code: string): string {
  return authErrorMessages[code] ?? "暂时无法完成登录，请稍后重试。";
}

export async function loadAuthSnapshot(request: AuthRequest): Promise<AuthSnapshot> {
  const status = await request<{ initialized: boolean }>("/api/v1/auth/bootstrap-status");
  if (!status.initialized) {
    return { initialized: false, user: null };
  }

  try {
    const user = await request<AuthUser>("/api/v1/auth/me");
    return { initialized: true, user };
  } catch (error) {
    if (hasStatus(error, 401)) {
      return { initialized: true, user: null };
    }
    throw error;
  }
}

function hasStatus(error: unknown, status: number): boolean {
  return typeof error === "object" && error !== null && "status" in error && error.status === status;
}
