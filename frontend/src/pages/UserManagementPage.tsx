import { useCallback, useEffect, useState } from "react";
import { KeyRound, Pencil, UserPlus } from "lucide-react";

import {
  UserEditorDialog,
  userRoleLabels,
  userStatusLabels,
  type ManagedUser,
  type UserDialogAction,
} from "../components/UserEditorDialog";
import { ApiError, apiGet, apiPatch, apiPost } from "../lib/api";

export function UserManagementPage() {
  const [users, setUsers] = useState<ManagedUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [pageError, setPageError] = useState<string | null>(null);
  const [dialogError, setDialogError] = useState<string | null>(null);
  const [dialogAction, setDialogAction] = useState<UserDialogAction | null>(null);
  const [busy, setBusy] = useState(false);

  const loadUsers = useCallback(async () => {
    setLoading(true);
    setPageError(null);
    try {
      setUsers(await apiGet<ManagedUser[]>("/api/v1/admin/users"));
    } catch (error) {
      setPageError(userManagementError(error));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadUsers();
  }, [loadUsers]);

  function openDialog(action: UserDialogAction) {
    setDialogError(null);
    setDialogAction(action);
  }

  async function handleSubmit(payload: Record<string, string | null>) {
    if (!dialogAction) return;
    setBusy(true);
    setDialogError(null);
    try {
      if (dialogAction.mode === "create") {
        await apiPost<ManagedUser>("/api/v1/admin/users", payload);
      } else if (dialogAction.mode === "edit") {
        await apiPatch<ManagedUser>(`/api/v1/admin/users/${dialogAction.user.id}`, payload);
      } else {
        await apiPost<{ ok: boolean }>(`/api/v1/admin/users/${dialogAction.user.id}/reset-password`, payload);
      }
      setDialogAction(null);
      await loadUsers();
    } catch (error) {
      setDialogError(userManagementError(error));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="management-page">
      <div className="management-toolbar">
        <div>
          <span className="section-label">账号与权限</span>
          <h2>用户管理</h2>
          <p>创建内部账号，分配固定角色，并控制账号启用状态。</p>
        </div>
        <button className="button primary" onClick={() => openDialog({ mode: "create" })} type="button">
          <UserPlus aria-hidden="true" size={17} />
          创建用户
        </button>
      </div>

      {pageError ? (
        <div className="inline-message error management-page-message" role="alert">
          {pageError}
          <button className="button secondary" onClick={() => void loadUsers()} type="button">
            重新加载
          </button>
        </div>
      ) : null}

      <div className="management-table-wrap">
        <table className="management-table">
          <thead>
            <tr>
              <th>用户</th>
              <th>部门</th>
              <th>角色</th>
              <th>状态</th>
              <th>创建时间</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={6}>正在加载用户...</td>
              </tr>
            ) : users.length === 0 ? (
              <tr>
                <td colSpan={6}>暂无用户。</td>
              </tr>
            ) : (
              users.map((user) => (
                <tr key={user.id}>
                  <td>
                    <strong>{user.display_name}</strong>
                    <span>{user.email}</span>
                  </td>
                  <td>{user.department || "未设置"}</td>
                  <td>{userRoleLabels[user.role]}</td>
                  <td>
                    <span className={`status-token ${user.status === "active" ? "success" : "danger"}`}>
                      {userStatusLabels[user.status]}
                    </span>
                  </td>
                  <td>{formatDateTime(user.created_at)}</td>
                  <td>
                    <div className="row-actions">
                      <button className="button secondary" onClick={() => openDialog({ mode: "edit", user })} type="button">
                        <Pencil aria-hidden="true" size={16} />
                        编辑
                      </button>
                      <button className="button secondary" onClick={() => openDialog({ mode: "reset", user })} type="button">
                        <KeyRound aria-hidden="true" size={16} />
                        重置密码
                      </button>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {dialogAction ? (
        <UserEditorDialog
          action={dialogAction}
          busy={busy}
          errorMessage={dialogError}
          onClose={() => setDialogAction(null)}
          onSubmit={handleSubmit}
        />
      ) : null}
    </section>
  );
}

function userManagementError(error: unknown): string {
  if (!(error instanceof ApiError)) {
    return "暂时无法连接系统，请稍后重试。";
  }
  const messages: Record<string, string> = {
    AUTH_LAST_ADMIN_REQUIRED: "系统必须保留至少一名启用中的管理员。",
    USER_EMAIL_EXISTS: "该邮箱已存在，请使用其他邮箱。",
    USER_NOT_FOUND: "用户不存在或已被移除。",
  };
  return messages[error.code] ?? "暂时无法完成用户操作，请稍后重试。";
}

function formatDateTime(value: string | null): string {
  if (!value) return "未知";
  return new Intl.DateTimeFormat("zh-CN", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}
