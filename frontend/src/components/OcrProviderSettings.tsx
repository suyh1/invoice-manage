import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { Check, Eye, Pencil, Plus, Power, RefreshCw, Save, TestTube, Trash2, X } from "lucide-react";

import { apiDelete, apiGet, apiPatch, apiPost, ApiError } from "../lib/api";

export type OcrProviderConfig = {
  id: string;
  provider: "tencent" | "mock" | "aliyun";
  display_name: string;
  enabled: boolean;
  is_default: boolean;
  configured: boolean;
  credential_fingerprint: string | null;
  endpoint: string;
  region: string;
  action: string;
  api_version: string;
  qps_limit: number;
  last_test_status: string | null;
  quota: {
    source: string;
    free_quota_total: number | null;
    free_quota_used: number | null;
    free_quota_remaining: number | null;
    used_percent: number | null;
    warning_percent: number;
    warning_remaining: number;
    alert_level: string;
  };
};

type DialogAction = { mode: "create" } | { mode: "view" | "edit"; provider: OcrProviderConfig };

export function OcrProviderSettings() {
  const [providers, setProviders] = useState<OcrProviderConfig[]>([]);
  const [loading, setLoading] = useState(true);
  const [pageError, setPageError] = useState<string | null>(null);
  const [dialogAction, setDialogAction] = useState<DialogAction | null>(null);
  const [dialogError, setDialogError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [rowMessages, setRowMessages] = useState<Record<string, string>>({});

  const loadProviders = useCallback(async () => {
    setLoading(true);
    setPageError(null);
    try {
      setProviders(await apiGet<OcrProviderConfig[]>("/api/v1/admin/ocr-providers"));
    } catch (error) {
      setPageError(messageFor(error, "无法加载 OCR 配置。"));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadProviders();
  }, [loadProviders]);

  async function saveProvider(payload: Record<string, unknown>) {
    setDialogError(null);
    setBusyId("dialog");
    try {
      if (dialogAction?.mode === "edit") {
        await apiPatch(`/api/v1/admin/ocr-providers/${dialogAction.provider.id}`, payload);
      } else {
        await apiPost("/api/v1/admin/ocr-providers", payload);
      }
      setDialogAction(null);
      await loadProviders();
    } catch (error) {
      setDialogError(messageFor(error, "配置保存失败。"));
    } finally {
      setBusyId(null);
    }
  }

  async function runRowAction(provider: OcrProviderConfig, action: "test" | "activate" | "delete") {
    setBusyId(provider.id);
    setPageError(null);
    try {
      if (action === "test") {
        const result = await apiPost<{ status: string; message: string }>(`/api/v1/admin/ocr-providers/${provider.id}/test`);
        setRowMessages((current) => ({ ...current, [provider.id]: result.message || "连接测试成功。" }));
      } else if (action === "activate") {
        await apiPost(`/api/v1/admin/ocr-providers/${provider.id}/set-default`);
        setRowMessages((current) => ({ ...current, [provider.id]: "已启用，其他 OCR 配置已停用。" }));
      } else {
        await apiDelete(`/api/v1/admin/ocr-providers/${provider.id}`);
      }
      await loadProviders();
    } catch (error) {
      const message = messageFor(error, action === "test" ? "连接测试失败。" : action === "delete" ? "删除失败。" : "启用失败。");
      setRowMessages((current) => ({ ...current, [provider.id]: message }));
    } finally {
      setBusyId(null);
    }
  }

  return (
    <section className="provider-management">
      <div className="management-toolbar provider-toolbar">
        <div>
          <span className="section-label">服务入口</span>
          <h2>OCR 配置</h2>
          <p>系统只启用一个配置。切换后，尚未开始和待重试作业会自动使用当前服务。</p>
        </div>
        <div className="row-actions">
          <button aria-label="刷新 OCR 配置" className="icon-button" onClick={() => void loadProviders()} title="刷新" type="button">
            <RefreshCw aria-hidden="true" size={18} />
          </button>
          <button className="button primary" onClick={() => setDialogAction({ mode: "create" })} type="button">
            <Plus aria-hidden="true" size={17} /> 新增配置
          </button>
        </div>
      </div>

      {pageError ? <p className="inline-message error" role="alert">{pageError}</p> : null}
      {loading ? <div className="management-loading">正在加载 OCR 配置...</div> : null}
      {!loading && providers.length === 0 ? (
        <div className="empty-state provider-empty"><strong>还没有 OCR 服务配置</strong><p>新增腾讯云、Mock 或后续支持的其他 OCR 服务。</p></div>
      ) : null}

      {!loading && providers.length ? (
        <div className="provider-list" aria-label="OCR 运营商列表">
          {providers.map((provider) => (
            <article className={`provider-card ${provider.enabled ? "active" : ""}`} key={provider.id}>
              <div className="provider-card-main">
                <div className="provider-identity">
                  <span className={`provider-mark ${provider.provider}`}>{provider.provider.slice(0, 1).toUpperCase()}</span>
                  <div><strong>{provider.display_name}</strong><span>{provider.provider} · {provider.region} · QPS {provider.qps_limit}</span></div>
                </div>
                <span className={`status-token ${provider.enabled ? "success" : "neutral"}`}>
                  {provider.enabled ? <><Check aria-hidden="true" size={13} /> 当前启用</> : "未启用"}
                </span>
              </div>
              <dl className="provider-metrics">
                <div><dt>总额度</dt><dd>{value(provider.quota.free_quota_total)}</dd></div>
                <div><dt>已用</dt><dd>{value(provider.quota.free_quota_used)}</dd></div>
                <div><dt>剩余</dt><dd>{value(provider.quota.free_quota_remaining)}</dd></div>
                <div><dt>凭据</dt><dd className="metric-text">{provider.configured ? provider.credential_fingerprint : "未配置"}</dd></div>
              </dl>
              {rowMessages[provider.id] ? <p className="provider-row-message" role="status">{rowMessages[provider.id]}</p> : null}
              <div className="provider-card-actions">
                <button aria-label={`查看${provider.display_name}`} className="icon-button" onClick={() => setDialogAction({ mode: "view", provider })} title="查看" type="button"><Eye aria-hidden="true" size={17} /></button>
                <button aria-label={`编辑${provider.display_name}`} className="icon-button" onClick={() => setDialogAction({ mode: "edit", provider })} title="编辑" type="button"><Pencil aria-hidden="true" size={17} /></button>
                <button aria-label={`测试${provider.display_name}连接`} className="icon-button" disabled={busyId === provider.id} onClick={() => void runRowAction(provider, "test")} title="测试连接" type="button"><TestTube aria-hidden="true" size={17} /></button>
                {!provider.enabled ? <button className="button secondary" disabled={busyId === provider.id} onClick={() => void runRowAction(provider, "activate")} type="button"><Power aria-hidden="true" size={16} />启用</button> : null}
                <button aria-label={`删除${provider.display_name}`} className="icon-button danger" onClick={() => setDialogAction({ mode: "view", provider })} title="删除" type="button"><Trash2 aria-hidden="true" size={17} /></button>
              </div>
            </article>
          ))}
        </div>
      ) : null}

      {dialogAction ? (
        <ProviderDialog
          action={dialogAction}
          busy={busyId === "dialog" || busyId === (dialogAction.mode === "create" ? "" : dialogAction.provider.id)}
          error={dialogError}
          onClose={() => { setDialogAction(null); setDialogError(null); }}
          onDelete={dialogAction.mode === "create" ? undefined : async () => { await runRowAction(dialogAction.provider, "delete"); setDialogAction(null); }}
          onEdit={dialogAction.mode === "create" ? undefined : () => setDialogAction({ mode: "edit", provider: dialogAction.provider })}
          onSave={saveProvider}
        />
      ) : null}
    </section>
  );
}

function ProviderDialog({ action, busy, error, onClose, onDelete, onEdit, onSave }: { action: DialogAction; busy: boolean; error: string | null; onClose: () => void; onDelete?: () => Promise<void>; onEdit?: () => void; onSave: (payload: Record<string, unknown>) => Promise<void> }) {
  const ref = useRef<HTMLDialogElement>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const provider = action.mode === "create" ? null : action.provider;
  const readonly = action.mode === "view";
  useEffect(() => { ref.current?.showModal(); return () => ref.current?.close(); }, []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const total = numberOrNull(data.get("free_quota_total"));
    const used = numberOrNull(data.get("free_quota_used"));
    const payload: Record<string, unknown> = {
      provider: String(data.get("provider")), display_name: String(data.get("display_name")).trim(),
      enabled: action.mode === "create" ? Boolean(data.get("activate")) : provider?.enabled,
      is_default: action.mode === "create" ? Boolean(data.get("activate")) : provider?.is_default,
      qps_limit: Number(data.get("qps_limit")),
      quota: { source: "manual", free_quota_total: total, free_quota_used: used, quota_warning_percent: Number(data.get("warning_percent")), quota_warning_remaining: Number(data.get("warning_remaining")) },
    };
    const secretId = String(data.get("secret_id") ?? ""); const secretKey = String(data.get("secret_key") ?? "");
    if (secretId && secretKey) payload.credential = { secret_id: secretId, secret_key: secretKey };
    await onSave(payload);
  }

  return <dialog aria-label={action.mode === "create" ? "新增 OCR 配置" : `${readonly ? "查看" : "编辑"}${provider?.display_name}`} className="management-dialog provider-dialog" onClose={onClose} ref={ref}>
    <div className="management-dialog-heading"><div><h2>{action.mode === "create" ? "新增 OCR 配置" : `${readonly ? "查看" : "编辑"} ${provider?.display_name}`}</h2><p>凭据只在提交时发送，保存后不会回显。</p></div><button aria-label="关闭配置对话框" className="icon-button" onClick={onClose} type="button"><X aria-hidden="true" size={18} /></button></div>
    {error ? <p className="inline-message error management-dialog-message" role="alert">{error}</p> : null}
    <form className="management-form" onSubmit={submit}>
      <div className="form-grid"><label>运营商<select defaultValue={provider?.provider ?? "tencent"} disabled={readonly || action.mode === "edit"} name="provider"><option value="tencent">腾讯云 OCR</option><option value="mock">Mock OCR</option><option value="aliyun">阿里云 OCR</option></select></label><label>显示名称<input defaultValue={provider?.display_name ?? "腾讯云 OCR"} disabled={readonly} name="display_name" required /></label></div>
      {!readonly ? <div className="form-grid"><label>SecretId<input autoComplete="off" name="secret_id" placeholder={provider?.configured ? "留空则保持原凭据" : "请输入 SecretId"} /></label><label>SecretKey<input autoComplete="new-password" name="secret_key" placeholder={provider?.configured ? "留空则保持原凭据" : "请输入 SecretKey"} type="password" /></label></div> : <p className="provider-detail-line">凭据状态：{provider?.configured ? provider.credential_fingerprint : "未配置"}</p>}
      <div className="form-grid"><label>QPS 上限<input defaultValue={provider?.qps_limit ?? 8} disabled={readonly} min="1" name="qps_limit" type="number" /></label><label>总额度<input defaultValue={provider?.quota.free_quota_total ?? ""} disabled={readonly} min="0" name="free_quota_total" type="number" /></label><label>已用额度<input defaultValue={provider?.quota.free_quota_used ?? ""} disabled={readonly} min="0" name="free_quota_used" type="number" /></label><label>剩余额度<input disabled value={provider?.quota.free_quota_remaining ?? "保存后计算"} /></label><label>百分比提醒<input defaultValue={provider?.quota.warning_percent ?? 80} disabled={readonly} max="100" min="1" name="warning_percent" type="number" /></label><label>剩余额度提醒<input defaultValue={provider?.quota.warning_remaining ?? 100} disabled={readonly} min="0" name="warning_remaining" type="number" /></label></div>
      {action.mode === "create" ? <label className="check-row"><input defaultChecked name="activate" type="checkbox" /><span>保存后立即启用，并停用其他配置</span></label> : null}
      {confirmDelete ? <p className="inline-message error">删除后，该配置的额度统计和告警会一并移除。排队作业会自动使用当前启用配置。</p> : null}
      <div className="management-dialog-actions"><button className="button secondary" onClick={onClose} type="button">关闭</button>{readonly && onDelete ? <button className="button danger" onClick={() => confirmDelete ? void onDelete() : setConfirmDelete(true)} type="button"><Trash2 aria-hidden="true" size={16} />{confirmDelete ? "确认删除" : "删除配置"}</button> : null}{readonly && onEdit ? <button className="button primary" onClick={onEdit} type="button"><Pencil aria-hidden="true" size={16} />编辑</button> : null}{!readonly ? <button className="button primary" disabled={busy} type="submit"><Save aria-hidden="true" size={16} />{busy ? "正在保存..." : "保存配置"}</button> : null}</div>
    </form>
  </dialog>;
}

function numberOrNull(value: FormDataEntryValue | null) { const text = String(value ?? "").trim(); return text === "" ? null : Number(text); }
function value(input: number | null) { return input === null ? "-" : input.toLocaleString("zh-CN"); }
function messageFor(error: unknown, fallback: string) { return error instanceof ApiError ? error.message : fallback; }
