import { useEffect, useState } from "react";

import { apiGet } from "../lib/api";

type QuotaStatus = {
  level: "none" | "warning" | "critical";
  quota_total: number | null;
  quota_used: number | null;
  used_percent: number | null;
};

export function OcrQuotaStatus({ compact = false }: { compact?: boolean }) {
  const [quota, setQuota] = useState<QuotaStatus | null>(null);

  useEffect(() => {
    let cancelled = false;
    apiGet<QuotaStatus>("/api/v1/ocr-quota/status")
      .then((data) => {
        if (!cancelled) {
          setQuota(data);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setQuota(null);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const total = quota?.quota_total;
  const used = quota?.quota_used;
  const hasQuota = typeof total === "number" && typeof used === "number";
  const usedPercent = hasQuota
    ? Math.min(100, Math.max(0, quota?.used_percent ?? (total > 0 ? used * 100 / total : 100)))
    : 0;
  const level = quota?.level ?? "none";
  const quotaLabel = hasQuota ? `${used}/${total}` : "--/--";

  return (
    <section className={`quota-status ${compact ? "compact" : ""} ${level}`} aria-label="OCR 额度状态">
      <span className="section-label">OCR 额度</span>
      <div className="quota-progress-row">
        <div
          aria-label={hasQuota ? "OCR 额度使用情况" : undefined}
          aria-valuemax={hasQuota ? total : undefined}
          aria-valuemin={hasQuota ? 0 : undefined}
          aria-valuenow={hasQuota ? Math.min(Math.max(used, 0), Math.max(total, 0)) : undefined}
          className="quota-progress-track"
          role={hasQuota ? "progressbar" : undefined}
        >
          <span className="quota-progress-fill" style={{ width: `${usedPercent}%` }} />
        </div>
        <strong className="quota-progress-value">{quotaLabel}</strong>
      </div>
    </section>
  );
}
