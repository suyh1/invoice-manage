import { useEffect, useRef, useState, type FormEvent } from "react";
import { KeyRound, Save, UserPlus, X } from "lucide-react";

import type { UserRole } from "../auth/authState";

export type ManagedUser = {
  id: string;
  email: string;
  display_name: string;
  department: string | null;
  role: UserRole;
  status: "active" | "disabled";
  created_at: string | null;
  updated_at: string | null;
};

export type UserDialogAction =
  | { mode: "create" }
  | { mode: "edit"; user: ManagedUser }
  | { mode: "reset"; user: ManagedUser };

type UserEditorDialogProps = {
  action: UserDialogAction;
  busy: boolean;
  errorMessage: string | null;
  onClose: () => void;
  onSubmit: (payload: Record<string, string | null>) => Promise<void> | void;
};

export const userRoleLabels: Record<UserRole, string> = {
  admin: "管理员",
  finance: "财务",
  user: "普通用户",
};

export const userStatusLabels: Record<ManagedUser["status"], string> = {
  active: "启用",
  disabled: "停用",
};

export function UserEditorDialog({ action, busy, errorMessage, onClose, onSubmit }: UserEditorDialogProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const [localError, setLocalError] = useState<string | null>(null);
  const user = action.mode === "create" ? null : action.user;

  useEffect(() => {
    dialogRef.current?.showModal();
    return () => dialogRef.current?.close();
  }, []);

  function closeDialog() {
    dialogRef.current?.close();
    onClose();
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLocalError(null);
    const data = new FormData(event.currentTarget);

    if (action.mode === "reset") {
      const password = String(data.get("password") ?? "");
      if (password !== String(data.get("confirm_password") ?? "")) {
        setLocalError("两次输入的新密码不一致。");
        return;
      }
      await onSubmit({ password });
      return;
    }

    const payload: Record<string, string | null> = {
      display_name: String(data.get("display_name") ?? "").trim(),
      department: String(data.get("department") ?? "").trim() || null,
      role: String(data.get("role") ?? "user"),
      status: String(data.get("status") ?? "active"),
    };
    if (action.mode === "create") {
      payload.email = String(data.get("email") ?? "").trim();
      payload.password = String(data.get("password") ?? "");
    }
    await onSubmit(payload);
  }

  const title =
    action.mode === "create" ? "创建用户" : action.mode === "edit" ? `编辑 ${user?.display_name}` : "重置密码";

  return (
    <dialog className="management-dialog" onClose={onClose} ref={dialogRef}>
      <div className="management-dialog-heading">
        <div>
          <h2>{title}</h2>
          <p>
            {action.mode === "create"
              ? "新账号默认为普通用户，可在创建时调整角色。"
              : action.mode === "edit"
                ? user?.email
                : `为 ${user?.email} 设置临时密码。`}
          </p>
        </div>
        <button aria-label="关闭用户对话框" className="icon-button" onClick={closeDialog} title="关闭" type="button">
          <X aria-hidden="true" size={18} />
        </button>
      </div>

      {localError || errorMessage ? (
        <p className="inline-message error management-dialog-message" role="alert">
          {localError ?? errorMessage}
        </p>
      ) : null}

      <form className="management-form" onSubmit={handleSubmit}>
        {action.mode === "reset" ? (
          <>
            <label htmlFor="managed-user-password">
              新密码
              <input
                autoComplete="new-password"
                disabled={busy}
                id="managed-user-password"
                minLength={12}
                name="password"
                placeholder="至少 12 位"
                required
                type="password"
              />
            </label>
            <label htmlFor="managed-user-password-confirm">
              确认新密码
              <input
                autoComplete="new-password"
                disabled={busy}
                id="managed-user-password-confirm"
                minLength={12}
                name="confirm_password"
                required
                type="password"
              />
            </label>
          </>
        ) : (
          <>
            <div className="form-grid">
              <label htmlFor="managed-user-name">
                姓名
                <input
                  autoComplete="name"
                  defaultValue={user?.display_name ?? ""}
                  disabled={busy}
                  id="managed-user-name"
                  name="display_name"
                  required
                />
              </label>
              {action.mode === "create" ? (
                <label htmlFor="managed-user-email">
                  邮箱
                  <input
                    autoComplete="username"
                    disabled={busy}
                    id="managed-user-email"
                    inputMode="email"
                    name="email"
                    required
                    type="email"
                  />
                </label>
              ) : null}
            </div>
            <label htmlFor="managed-user-department">
              部门
              <input
                defaultValue={user?.department ?? ""}
                disabled={busy}
                id="managed-user-department"
                name="department"
                placeholder="可选"
              />
            </label>
            <div className="form-grid">
              <label htmlFor="managed-user-role">
                角色
                <select defaultValue={user?.role ?? "user"} disabled={busy} id="managed-user-role" name="role">
                  <option value="user">普通用户</option>
                  <option value="finance">财务</option>
                  <option value="admin">管理员</option>
                </select>
              </label>
              <label htmlFor="managed-user-status">
                状态
                <select defaultValue={user?.status ?? "active"} disabled={busy} id="managed-user-status" name="status">
                  <option value="active">启用</option>
                  <option value="disabled">停用</option>
                </select>
              </label>
            </div>
            {action.mode === "create" ? (
              <label htmlFor="managed-user-create-password">
                初始密码
                <input
                  autoComplete="new-password"
                  disabled={busy}
                  id="managed-user-create-password"
                  minLength={12}
                  name="password"
                  placeholder="至少 12 位"
                  required
                  type="password"
                />
              </label>
            ) : null}
          </>
        )}

        <div className="management-dialog-actions">
          <button className="button secondary" onClick={closeDialog} type="button">
            返回
          </button>
          <button className="button primary" disabled={busy} type="submit">
            {action.mode === "create" ? (
              <UserPlus aria-hidden="true" size={17} />
            ) : action.mode === "reset" ? (
              <KeyRound aria-hidden="true" size={17} />
            ) : (
              <Save aria-hidden="true" size={17} />
            )}
            {busy ? "正在保存..." : action.mode === "create" ? "创建用户" : action.mode === "reset" ? "重置密码" : "保存用户"}
          </button>
        </div>
      </form>
    </dialog>
  );
}
