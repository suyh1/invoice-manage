import { FormEvent, useEffect, useMemo, useState } from "react";

import { apiGet, apiPatch, apiPost, ApiError } from "../lib/api";

type OcrProviderConfig = {
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

type ProviderPayload = {
  provider: "tencent" | "mock";
  display_name: string;
  enabled: boolean;
  is_default: boolean;
  credential?: { secret_id: string; secret_key: string };
  qps_limit: number;
  quota: {
    source: "manual";
    free_quota_total: number | null;
    free_quota_used: number | null;
    quota_warning_percent: number;
    quota_warning_remaining: number;
  };
};

type ProviderForm = {
  provider: "tencent" | "mock";
  display_name: string;
  secret_id: string;
  secret_key: string;
  qps_limit: number;
  free_quota_total: string;
  free_quota_used: string;
  quota_warning_percent: number;
  quota_warning_remaining: number;
};

const emptyForm: ProviderForm = {
  provider: "tencent",
  display_name: "腾讯云 OCR",
  secret_id: "",
  secret_key: "",
  qps_limit: 8,
  free_quota_total: "",
  free_quota_used: "",
  quota_warning_percent: 80,
  quota_warning_remaining: 100,
};

export function OcrProviderSettings() {
  const [providers, setProviders] = useState<OcrProviderConfig[]>([]);
  const [form, setForm] = useState(emptyForm);
  const [status, setStatus] = useState<"loading" | "ready" | "saving" | "error">("loading");
  const [message, setMessage] = useState("");

  const defaultProvider = useMemo(() => providers.find((provider) => provider.is_default), [providers]);

  useEffect(() => {
    loadProviders();
  }, []);

  function loadProviders() {
    setStatus("loading");
    apiGet<OcrProviderConfig[]>("/api/v1/admin/ocr-providers")
      .then((data) => {
        setProviders(data);
        setStatus("ready");
      })
      .catch((error) => {
        setStatus("error");
        setMessage(error instanceof ApiError && error.status === 401 ? "请先登录管理员账号。" : "无法加载 OCR 运营商配置。");
      });
  }

  async function submitProvider(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setStatus("saving");
    const payload: ProviderPayload = {
      provider: form.provider,
      display_name: form.display_name,
      enabled: true,
      is_default: providers.length === 0,
      qps_limit: form.qps_limit,
      quota: {
        source: "manual",
        free_quota_total: toNumberOrNull(form.free_quota_total),
        free_quota_used: toNumberOrNull(form.free_quota_used),
        quota_warning_percent: form.quota_warning_percent,
        quota_warning_remaining: form.quota_warning_remaining,
      },
    };
    if (form.secret_id && form.secret_key) {
      payload.credential = { secret_id: form.secret_id, secret_key: form.secret_key };
    }
    try {
      await apiPost<OcrProviderConfig>("/api/v1/admin/ocr-providers", payload);
      setForm({ ...emptyForm, provider: form.provider });
      setMessage("OCR 运营商已保存。");
      await apiGet<OcrProviderConfig[]>("/api/v1/admin/ocr-providers").then(setProviders);
      setStatus("ready");
    } catch (error) {
      setStatus("error");
      setMessage(error instanceof ApiError ? error.message : "保存失败。");
    }
  }

  async function setDefault(provider: OcrProviderConfig) {
    setStatus("saving");
    try {
      await apiPost<OcrProviderConfig>(`/api/v1/admin/ocr-providers/${provider.id}/set-default`);
      await apiGet<OcrProviderConfig[]>("/api/v1/admin/ocr-providers").then(setProviders);
      setStatus("ready");
      setMessage(`${provider.display_name} 已设为默认。`);
    } catch (error) {
      setStatus("error");
      setMessage(error instanceof ApiError ? error.message : "设置默认失败。");
    }
  }

  async function testConnection(provider: OcrProviderConfig) {
    setStatus("saving");
    try {
      await apiPost(`/api/v1/admin/ocr-providers/${provider.id}/test`);
      await apiGet<OcrProviderConfig[]>("/api/v1/admin/ocr-providers").then(setProviders);
      setStatus("ready");
      setMessage("连接测试已完成。");
    } catch (error) {
      setStatus("error");
      setMessage(error instanceof ApiError ? error.message : "连接测试失败。");
    }
  }

  async function updateQuota(provider: OcrProviderConfig, field: "quota_warning_percent" | "quota_warning_remaining", value: number) {
    const quota = {
      source: provider.quota.source,
      free_quota_total: provider.quota.free_quota_total,
      free_quota_used: provider.quota.free_quota_used,
      quota_warning_percent: field === "quota_warning_percent" ? value : provider.quota.warning_percent,
      quota_warning_remaining: field === "quota_warning_remaining" ? value : provider.quota.warning_remaining,
    };
    try {
      const updated = await apiPatch<OcrProviderConfig>(`/api/v1/admin/ocr-providers/${provider.id}`, { quota });
      setProviders((current) => current.map((item) => (item.id === updated.id ? updated : item)));
      setMessage(`${provider.display_name} 的额度提醒阈值已更新。`);
    } catch (error) {
      setStatus("error");
      setMessage(error instanceof ApiError ? error.message : "额度提醒阈值更新失败。");
    }
  }

  return (
    <section className="settings-layout">
      <div className="surface-panel provider-list">
        <div className="panel-heading">
          <div>
            <span className="section-label">运营商</span>
            <h2>已配置 OCR</h2>
          </div>
          <button className="button secondary" onClick={loadProviders} type="button" disabled={status === "loading"}>
            刷新
          </button>
        </div>

        {providers.length ? (
          <div className="provider-table" role="table" aria-label="OCR 运营商列表">
            {providers.map((provider) => (
              <article className="provider-row" key={provider.id}>
                <div>
                  <strong>{provider.display_name}</strong>
                  <span>
                    {provider.provider} · {provider.region} · QPS {provider.qps_limit}
                  </span>
                </div>
                <div className="provider-status">
                  <span className={`status-token ${provider.is_default ? "success" : "neutral"}`}>
                    {provider.is_default ? "默认" : provider.enabled ? "启用" : "停用"}
                  </span>
                  <span className="fingerprint">{provider.configured ? provider.credential_fingerprint : "未配置凭据"}</span>
                </div>
                <div className="quota-controls">
                  <label>
                    百分比阈值
                    <input
                      type="number"
                      min="1"
                      max="100"
                      defaultValue={provider.quota.warning_percent}
                      onBlur={(event) => updateQuota(provider, "quota_warning_percent", Number(event.currentTarget.value))}
                    />
                  </label>
                  <label>
                    剩余额度阈值
                    <input
                      type="number"
                      min="0"
                      defaultValue={provider.quota.warning_remaining}
                      onBlur={(event) => updateQuota(provider, "quota_warning_remaining", Number(event.currentTarget.value))}
                    />
                  </label>
                </div>
                <div className="row-actions">
                  <button className="button secondary" type="button" onClick={() => testConnection(provider)}>
                    测试连接
                  </button>
                  <button className="button primary" type="button" onClick={() => setDefault(provider)} disabled={provider.is_default}>
                    设为默认
                  </button>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <div className="empty-state">
            <strong>还没有 OCR 运营商</strong>
            <p>先添加 Mock 或腾讯云 OCR。真实凭据提交后仅加密保存，页面不会回显。</p>
          </div>
        )}
      </div>

      <form className="surface-panel provider-form" onSubmit={submitProvider}>
        <div className="panel-heading">
          <div>
            <span className="section-label">新增配置</span>
            <h2>添加 OCR 运营商</h2>
          </div>
          <span className="status-token neutral">{defaultProvider ? `默认：${defaultProvider.display_name}` : "未设置默认"}</span>
        </div>

        <div className="form-grid">
          <label>
            运营商
            <select value={form.provider} onChange={(event) => setForm({ ...form, provider: event.currentTarget.value as "tencent" | "mock" })}>
              <option value="tencent">腾讯云 OCR</option>
              <option value="mock">Mock OCR</option>
            </select>
          </label>
          <label>
            显示名称
            <input value={form.display_name} onChange={(event) => setForm({ ...form, display_name: event.currentTarget.value })} />
          </label>
          <label>
            SecretId
            <input
              autoComplete="off"
              value={form.secret_id}
              onChange={(event) => setForm({ ...form, secret_id: event.currentTarget.value })}
              placeholder="仅提交时发送"
            />
          </label>
          <label>
            SecretKey
            <input
              autoComplete="off"
              type="password"
              value={form.secret_key}
              onChange={(event) => setForm({ ...form, secret_key: event.currentTarget.value })}
              placeholder="保存后清空"
            />
          </label>
          <label>
            QPS 上限
            <input
              type="number"
              min="1"
              max={form.provider === "mock" ? "100" : "8"}
              value={form.qps_limit}
              onChange={(event) => setForm({ ...form, qps_limit: Number(event.currentTarget.value) })}
            />
          </label>
          <label>
            总额度
            <input value={form.free_quota_total} onChange={(event) => setForm({ ...form, free_quota_total: event.currentTarget.value })} />
          </label>
          <label>
            已用额度
            <input value={form.free_quota_used} onChange={(event) => setForm({ ...form, free_quota_used: event.currentTarget.value })} />
          </label>
          <label>
            百分比提醒
            <input
              type="number"
              min="1"
              max="100"
              value={form.quota_warning_percent}
              onChange={(event) => setForm({ ...form, quota_warning_percent: Number(event.currentTarget.value) })}
            />
          </label>
          <label>
            剩余额度提醒
            <input
              type="number"
              min="0"
              value={form.quota_warning_remaining}
              onChange={(event) => setForm({ ...form, quota_warning_remaining: Number(event.currentTarget.value) })}
            />
          </label>
        </div>
        <div className="form-footer">
          <p>{message || "SecretId 和 SecretKey 不会在页面保存或展示。"}</p>
          <button className="button primary" disabled={status === "saving"} type="submit">
            保存配置
          </button>
        </div>
      </form>
    </section>
  );
}

function toNumberOrNull(value: string) {
  if (!value.trim()) {
    return null;
  }
  return Number(value);
}
