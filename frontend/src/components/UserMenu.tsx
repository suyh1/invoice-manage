import { useRef, useState, type FormEvent } from "react";
import { ChevronDown, KeyRound, LogOut, Save, UserRound, X } from "lucide-react";

import type { AuthUser } from "../auth/authState";
import { authErrorMessage } from "../auth/authState";
import { ApiError } from "../lib/api";

type PasswordChangePayload = {
  current_password: string;
  new_password: string;
};

type UserMenuProps = {
  user: AuthUser;
  onChangePassword: (payload: PasswordChangePayload) => Promise<void>;
  onLogout: () => Promise<void>;
};

const roleLabels: Record<AuthUser["role"], string> = {
  admin: "管理员",
  finance: "财务",
  user: "普通用户",
};

export function UserMenu({ user, onChangePassword, onLogout }: UserMenuProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const currentPasswordRef = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ kind: "error" | "success"; text: string } | null>(null);

  function openPasswordDialog() {
    setMessage(null);
    dialogRef.current?.showModal();
    window.requestAnimationFrame(() => currentPasswordRef.current?.focus());
  }

  async function handlePasswordSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMessage(null);
    const form = event.currentTarget;
    const formData = new FormData(form);
    const currentPassword = String(formData.get("current_password") ?? "");
    const newPassword = String(formData.get("new_password") ?? "");
    const confirmPassword = String(formData.get("confirm_password") ?? "");
    if (newPassword !== confirmPassword) {
      setMessage({ kind: "error", text: "两次输入的新密码不一致。" });
      return;
    }

    setBusy(true);
    try {
      await onChangePassword({ current_password: currentPassword, new_password: newPassword });
      form.reset();
      setMessage({ kind: "success", text: "密码已更新，其他已登录会话将失效。" });
    } catch (error) {
      setMessage({
        kind: "error",
        text: error instanceof ApiError ? authErrorMessage(error.code) : "暂时无法修改密码，请稍后重试。",
      });
    } finally {
      setBusy(false);
    }
  }

  async function handleLogout() {
    setBusy(true);
    try {
      await onLogout();
    } catch {
      setMessage({ kind: "error", text: "暂时无法退出，请稍后重试。" });
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <details className="user-menu">
        <summary aria-label="打开账号菜单">
          <span className="user-menu-avatar" aria-hidden="true">
            <UserRound size={18} />
          </span>
          <span className="user-menu-identity">
            <strong>{user.display_name}</strong>
            <small>{roleLabels[user.role]}</small>
          </span>
          <ChevronDown aria-hidden="true" className="user-menu-chevron" size={16} />
        </summary>

        <div className="user-menu-popover">
          <div className="user-menu-account">
            <strong>{user.display_name}</strong>
            <span>{user.email}</span>
          </div>
          <button onClick={openPasswordDialog} type="button">
            <KeyRound aria-hidden="true" size={17} />
            修改密码
          </button>
          <button disabled={busy} onClick={() => void handleLogout()} type="button">
            <LogOut aria-hidden="true" size={17} />
            退出登录
          </button>
        </div>
      </details>

      <dialog className="account-dialog" ref={dialogRef}>
        <div className="account-dialog-heading">
          <div>
            <h2>修改密码</h2>
            <p>更新后，其他设备上的已登录会话将立即失效。</p>
          </div>
          <button
            aria-label="关闭修改密码对话框"
            className="icon-button"
            onClick={() => dialogRef.current?.close()}
            title="关闭"
            type="button"
          >
            <X aria-hidden="true" size={18} />
          </button>
        </div>

        {message ? (
          <p className={`inline-message ${message.kind}`} role={message.kind === "error" ? "alert" : "status"}>
            {message.text}
          </p>
        ) : null}

        <form className="account-password-form" onSubmit={handlePasswordSubmit}>
          <label htmlFor="current-password">
            当前密码
            <input
              autoComplete="current-password"
              disabled={busy}
              id="current-password"
              name="current_password"
              ref={currentPasswordRef}
              required
              type="password"
            />
          </label>
          <label htmlFor="new-password">
            新密码
            <input
              autoComplete="new-password"
              disabled={busy}
              id="new-password"
              minLength={12}
              name="new_password"
              placeholder="至少 12 位"
              required
              type="password"
            />
          </label>
          <label htmlFor="confirm-new-password">
            确认新密码
            <input
              autoComplete="new-password"
              disabled={busy}
              id="confirm-new-password"
              minLength={12}
              name="confirm_password"
              required
              type="password"
            />
          </label>
          <div className="account-dialog-actions">
            <button className="button secondary" onClick={() => dialogRef.current?.close()} type="button">
              返回
            </button>
            <button className="button primary" disabled={busy} type="submit">
              <Save aria-hidden="true" size={17} />
              {busy ? "正在保存..." : "保存新密码"}
            </button>
          </div>
        </form>
      </dialog>
    </>
  );
}
