import { useEffect, useState } from "react";

import { apiGet, ApiError } from "../lib/api";

type QuotaAlert = {
  id: string;
  level: "info" | "warning" | "critical";
  status: "active" | "acknowledged" | "resolved";
  message: string;
  quota_total: number | null;
  quota_used: number | null;
  quota_remaining: number | null;
};

export function OcrQuotaStatus({ compact = false }: { compact?: boolean }) {
  const [alerts, setAlerts] = useState<QuotaAlert[]>([]);
  const [state, setState] = useState<"loading" | "ready" | "blocked">("loading");

  useEffect(() => {
    let cancelled = false;
    apiGet<QuotaAlert[]>("/api/v1/admin/ocr-quota-alerts")
      .then((data) => {
        if (!cancelled) {
          setAlerts(data);
          setState("ready");
        }
      })
      .catch((error) => {
        if (!cancelled) {
          setState(error instanceof ApiError && error.status === 401 ? "blocked" : "ready");
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const activeAlert = alerts.find((alert) => alert.status === "active");
  const label = activeAlert ? activeAlert.message : state === "blocked" ? "登录后显示 OCR 额度提醒" : "暂无 OCR 额度提醒";
  const level = activeAlert?.level ?? "none";

  return (
    <section className={`quota-status ${compact ? "compact" : ""} ${level}`} aria-label="OCR 额度状态">
      <span className="section-label">OCR 额度</span>
      <strong>{level === "critical" ? "紧急" : level === "warning" ? "预警" : "正常"}</strong>
      <p>{state === "loading" ? "正在检查额度提醒" : label}</p>
      {activeAlert ? (
        <dl>
          <div>
            <dt>剩余</dt>
            <dd>{activeAlert.quota_remaining ?? "-"}</dd>
          </div>
          <div>
            <dt>已用</dt>
            <dd>{activeAlert.quota_used ?? "-"}</dd>
          </div>
        </dl>
      ) : null}
    </section>
  );
}
