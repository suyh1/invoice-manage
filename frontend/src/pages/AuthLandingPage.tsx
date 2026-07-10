import { useRef, useState, type FormEvent } from "react";
import { Eye, EyeOff, LogIn, RotateCcw, UserRoundPlus } from "lucide-react";

import { MotionLandingChrome } from "../components/auth/MotionLandingChrome";
import { forceEngagedPanel } from "../lib/authLanding";

export type LoginPayload = {
  email: string;
  password: string;
};

export type BootstrapPayload = LoginPayload & {
  display_name: string;
};

type AuthLandingPageProps = {
  mode: "bootstrap" | "login";
  busy: boolean;
  errorMessage: string | null;
  onBootstrap: (payload: BootstrapPayload) => Promise<void> | void;
  onLogin: (payload: LoginPayload) => Promise<void> | void;
};

export function AuthLandingPage({
  mode,
  busy,
  errorMessage,
  onBootstrap,
  onLogin,
}: AuthLandingPageProps) {
  const [showPassword, setShowPassword] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);
  const [engaged, setEngaged] = useState(() => forceEngagedPanel({ busy, errorMessage, mode }));
  const confirmPasswordRef = useRef<HTMLInputElement>(null);
  const isBootstrap = mode === "bootstrap";
  const visibleError = localError ?? errorMessage;
  const panelEngaged = engaged || forceEngagedPanel({ busy, errorMessage: visibleError, mode });

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLocalError(null);

    const formData = new FormData(event.currentTarget);
    const email = String(formData.get("email") ?? "").trim();
    const password = String(formData.get("password") ?? "");
    if (!isBootstrap) {
      await onLogin({ email, password });
      return;
    }

    const confirmPassword = String(formData.get("confirm_password") ?? "");
    if (password !== confirmPassword) {
      setLocalError("两次输入的密码不一致。");
      confirmPasswordRef.current?.focus();
      return;
    }
    await onBootstrap({
      display_name: String(formData.get("display_name") ?? "").trim(),
      email,
      password,
    });
  }

  const passwordInputType = showPassword ? "text" : "password";
  const passwordToggleLabel = showPassword ? "隐藏密码" : "显示密码";

  return (
    <MotionLandingChrome bootstrap={isBootstrap}>
      <section
        aria-busy={busy}
        aria-labelledby="auth-panel-title"
        className="auth-panel motion-auth-panel"
        data-engaged={panelEngaged}
        id="auth-panel"
        onClickCapture={(event) => {
          if (event.target instanceof HTMLInputElement) {
            setEngaged(true);
          }
        }}
        onFocusCapture={() => setEngaged(true)}
      >
        <div className="auth-panel-heading">
          <h2 id="auth-panel-title">{isBootstrap ? "创建首位管理员" : "登录系统"}</h2>
          <p>{isBootstrap ? "初始化完成后，公开注册将自动关闭。" : "使用管理员分配的账号继续。"}</p>
        </div>

        {visibleError ? (
          <div className="auth-alert" role="alert" tabIndex={-1}>
            {visibleError}
          </div>
        ) : null}

        <form className="auth-form" onSubmit={handleSubmit}>
          {isBootstrap ? (
            <label htmlFor="auth-display-name">
              姓名
              <input
                autoComplete="name"
                disabled={busy}
                id="auth-display-name"
                name="display_name"
                placeholder="请输入姓名"
                required
              />
            </label>
          ) : null}

          <label htmlFor="auth-email">
            邮箱
            <input
              autoCapitalize="none"
              autoComplete="username"
              disabled={busy}
              id="auth-email"
              inputMode="email"
              name="email"
              placeholder="name@company.com"
              required
              spellCheck={false}
              type="email"
            />
          </label>

          <label htmlFor="auth-password">
            密码
            <span className="auth-password-field">
              <input
                autoComplete={isBootstrap ? "new-password" : "current-password"}
                disabled={busy}
                id="auth-password"
                minLength={isBootstrap ? 12 : undefined}
                name="password"
                placeholder={isBootstrap ? "设置至少 12 位密码" : "请输入密码"}
                required
                type={passwordInputType}
              />
              <button
                aria-label={passwordToggleLabel}
                className="auth-password-toggle"
                disabled={busy}
                onClick={() => setShowPassword((visible) => !visible)}
                title={passwordToggleLabel}
                type="button"
              >
                {showPassword ? <EyeOff aria-hidden="true" size={18} /> : <Eye aria-hidden="true" size={18} />}
              </button>
            </span>
            {isBootstrap ? <small>至少 12 位，建议同时包含字母、数字和符号。</small> : null}
          </label>

          {isBootstrap ? (
            <label htmlFor="auth-confirm-password">
              确认密码
              <input
                autoComplete="new-password"
                disabled={busy}
                id="auth-confirm-password"
                minLength={12}
                name="confirm_password"
                placeholder="再次输入密码"
                ref={confirmPasswordRef}
                required
                type={passwordInputType}
              />
            </label>
          ) : null}

          {isBootstrap ? (
            <p className="auth-permission-note">首位用户将获得管理员权限，可在系统内创建后续账号。</p>
          ) : null}

          <button className="button primary auth-submit" disabled={busy} type="submit">
            {isBootstrap ? <UserRoundPlus aria-hidden="true" size={18} /> : <LogIn aria-hidden="true" size={18} />}
            <span>
              {busy
                ? isBootstrap
                  ? "正在创建..."
                  : "正在登录..."
                : isBootstrap
                  ? "创建管理员并进入系统"
                  : "登录"}
            </span>
          </button>
        </form>

        {!isBootstrap ? <p className="auth-help">账号由管理员创建。如需重置密码，请联系系统管理员。</p> : null}
      </section>
    </MotionLandingChrome>
  );
}

export function AuthStatusPage({
  mode,
  onRetry,
}: {
  mode: "error" | "loading";
  onRetry: () => Promise<void> | void;
}) {
  const loading = mode === "loading";

  return (
    <MotionLandingChrome>
      <section
        aria-busy={loading}
        aria-live="polite"
        aria-labelledby="auth-panel-title"
        className="auth-panel auth-status-panel motion-auth-panel"
        data-engaged="true"
        id="auth-panel"
      >
        <div className="auth-panel-heading">
          <h2 id="auth-panel-title">{loading ? "正在确认系统状态" : "暂时无法连接"}</h2>
          <p>
            {loading ? "正在检查初始化和登录状态，请稍候。" : "无法确认系统状态。请检查服务是否已启动，然后重试。"}
          </p>
        </div>

        {loading ? (
          <div className="auth-skeleton" aria-hidden="true">
            <span />
            <span />
            <span className="auth-skeleton-action" />
          </div>
        ) : (
          <button className="button primary auth-submit" onClick={() => void onRetry()} type="button">
            <RotateCcw aria-hidden="true" size={18} />
            <span>重新尝试</span>
          </button>
        )}
      </section>
    </MotionLandingChrome>
  );
}
