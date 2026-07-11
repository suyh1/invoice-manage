import { useCallback, useEffect, useMemo, useState } from "react";
import { CheckCheck, ExternalLink, RotateCcw } from "lucide-react";

import { ApiError, apiGet, apiPost } from "../lib/api";
import { canBulkConfirm, invoiceStatusLabel, type ReviewTab } from "../lib/invoiceStatus";

type ReviewSummary = Record<ReviewTab, number>;

type ReviewOcr = {
  id: string;
  status: string;
  provider: string;
  error_code: string | null;
  provider_error_code: string | null;
  request_id: string | null;
};

type ReviewItem = {
  kind: "invoice" | "document";
  invoice_id: string | null;
  document_id?: string;
  invoice_number?: string | null;
  invoice_code?: string | null;
  seller_name?: string | null;
  amount_with_tax?: string | null;
  is_duplicate_suspected?: boolean;
  status: string;
  project: { id: string; name: string; visibility: string; status: string } | null;
  document: { id?: string; original_filename: string; file_ext: string; status: string; created_at: string | null } | null;
  ocr: ReviewOcr | null;
};

type ReviewItemsResponse = { items: ReviewItem[]; total: number };

const tabs: Array<{ id: ReviewTab; label: string }> = [
  { id: "needs_review", label: "待人工确认" },
  { id: "duplicates", label: "疑似重复" },
  { id: "failed", label: "识别失败" },
];

export function ReviewQueuePage() {
  const [tab, setTab] = useState<ReviewTab>("needs_review");
  const [summary, setSummary] = useState<ReviewSummary>({ needs_review: 0, duplicates: 0, failed: 0 });
  const [items, setItems] = useState<ReviewItem[]>([]);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const loadQueue = useCallback(async () => {
    setLoading(true);
    setMessage(null);
    try {
      const [nextSummary, nextItems] = await Promise.all([
        apiGet<ReviewSummary>("/api/v1/review/summary"),
        apiGet<ReviewItemsResponse>(`/api/v1/review/items?queue=${tab}`),
      ]);
      setSummary(nextSummary);
      setItems(nextItems.items);
      setSelectedIds(new Set());
    } catch (error) {
      setMessage(reviewError(error));
    } finally {
      setLoading(false);
    }
  }, [tab]);

  useEffect(() => {
    void loadQueue();
  }, [loadQueue]);

  const selectableItems = useMemo(
    () => items.filter((item) => canBulkConfirm(item)),
    [items],
  );

  function selectTab(nextTab: ReviewTab) {
    setTab(nextTab);
    setSelectedIds(new Set());
  }

  function toggleSelected(invoiceId: string, checked: boolean) {
    setSelectedIds((current) => {
      const next = new Set(current);
      if (checked) next.add(invoiceId);
      else next.delete(invoiceId);
      return next;
    });
  }

  async function bulkConfirm() {
    if (!selectedIds.size) return;
    setBusy(true);
    setMessage(null);
    try {
      await apiPost<{ confirmed_ids: string[] }>("/api/v1/invoices/bulk-confirm", {
        invoice_ids: [...selectedIds],
      });
      await loadQueue();
    } catch (error) {
      setMessage(reviewError(error));
    } finally {
      setBusy(false);
    }
  }

  async function confirmOne(invoiceId: string) {
    setBusy(true);
    setMessage(null);
    try {
      await apiPost(`/api/v1/invoices/${invoiceId}/confirm`);
      await loadQueue();
    } catch (error) {
      setMessage(reviewError(error));
    } finally {
      setBusy(false);
    }
  }

  async function retry(item: ReviewItem) {
    if (!item.ocr?.id) {
      setMessage("当前条目没有可重试的 OCR 作业。");
      return;
    }
    setBusy(true);
    setMessage(null);
    try {
      await apiPost(`/api/v1/ocr-jobs/${item.ocr.id}/retry`);
      setMessage("已提交重新识别。");
      await loadQueue();
    } catch (error) {
      setMessage(reviewError(error));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="page-stack review-page">
      <section className="surface-panel review-header review-ledger-header">
        <div>
          <span className="section-label">HUMAN REVIEW / 处理队列</span>
          <h2>待校对</h2>
          <p>处理待确认字段、疑似重复和识别失败的发票。</p>
        </div>
        <div className="review-tabs numbered-review-tabs" aria-label="校对队列" role="tablist">
          {tabs.map((candidate, index) => (
            <button
              aria-selected={tab === candidate.id}
              className={tab === candidate.id ? "active" : ""}
              key={candidate.id}
              onClick={() => selectTab(candidate.id)}
              role="tab"
              type="button"
            >
              <i aria-hidden="true">{String(index + 1).padStart(2, "0")}</i>
              <span>{candidate.label}</span>
              <strong>{summary[candidate.id]}</strong>
            </button>
          ))}
        </div>
      </section>

      <section className="surface-panel review-list-panel" aria-label={tabs.find((candidate) => candidate.id === tab)?.label}>
        <div className="panel-heading">
          <div>
            <span className="section-label">{tabs.find((candidate) => candidate.id === tab)?.label}</span>
            <h2>{loading ? "正在加载" : `${items.length} 条记录`}</h2>
          </div>
          {tab === "needs_review" ? (
            <button className="button primary" disabled={busy || selectedIds.size === 0} onClick={bulkConfirm} type="button">
              <CheckCheck aria-hidden="true" size={17} />
              确认选中项{selectedIds.size ? ` (${selectedIds.size})` : ""}
            </button>
          ) : null}
        </div>

        {message ? (
          <p className={`inline-message ${message === "已提交重新识别。" ? "success" : "error"}`} role="alert">
            {message}
          </p>
        ) : null}

        {loading ? (
          <div className="empty-state"><strong>正在加载队列...</strong></div>
        ) : items.length === 0 ? (
          <div className="empty-state"><strong>当前队列为空</strong><p>这里会显示需要人工处理的发票和识别失败文件。</p></div>
        ) : (
          <div className="review-table-wrap">
            <table className="review-table review-ledger-table">
              <thead>
                <tr>
                  <th>
                    {tab === "needs_review" ? (
                      <input
                        aria-label="选择全部可确认发票"
                        checked={selectableItems.length > 0 && selectedIds.size === selectableItems.length}
                        onChange={(event) =>
                          setSelectedIds(event.currentTarget.checked ? new Set(selectableItems.flatMap((item) => item.invoice_id ? [item.invoice_id] : [])) : new Set())
                        }
                        type="checkbox"
                      />
                    ) : null}
                  </th>
                  <th>发票或文件</th>
                  <th>项目</th>
                  <th>状态</th>
                  <th>风险或错误</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => {
                  const selectable = canBulkConfirm(item);
                  return (
                    <tr key={item.invoice_id ?? item.document_id}>
                      <td>
                        {selectable && item.invoice_id ? (
                          <input
                            aria-label={`选择 ${item.invoice_number || item.document?.original_filename || "发票"}`}
                            checked={selectedIds.has(item.invoice_id)}
                            onChange={(event) => toggleSelected(item.invoice_id!, event.currentTarget.checked)}
                            type="checkbox"
                          />
                        ) : null}
                      </td>
                      <td>
                        <strong>{item.invoice_number || item.document?.original_filename || "未识别文件"}</strong>
                        <span>{item.seller_name || item.invoice_code || item.document?.file_ext?.toUpperCase() || "-"}</span>
                      </td>
                      <td>{item.project?.name || "未分类"}</td>
                      <td>
                        <span className={`status-token ${item.is_duplicate_suspected ? "danger" : "neutral"}`}>
                          {item.is_duplicate_suspected ? "疑似重复" : invoiceStatusLabel(item.status)}
                        </span>
                      </td>
                      <td>
                        {item.ocr?.provider_error_code || item.ocr?.error_code || (item.is_duplicate_suspected ? "请核验是否重复" : "待人工确认")}
                      </td>
                      <td>
                        <div className="row-actions">
                          {item.invoice_id ? (
                            <a className="button secondary" href={`#/invoices/${item.invoice_id}`}>
                              <ExternalLink aria-hidden="true" size={16} />
                              详情
                            </a>
                          ) : null}
                          {selectable && item.invoice_id ? (
                            <button className="button secondary" disabled={busy} onClick={() => void confirmOne(item.invoice_id!)} type="button">
                              <CheckCheck aria-hidden="true" size={16} />
                              确认
                            </button>
                          ) : null}
                          {tab === "failed" ? (
                            <button className="button secondary" disabled={busy || !item.ocr?.id} onClick={() => void retry(item)} type="button">
                              <RotateCcw aria-hidden="true" size={16} />
                              重新识别
                            </button>
                          ) : null}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}

function reviewError(error: unknown): string {
  if (!(error instanceof ApiError)) return "暂时无法连接系统，请稍后重试。";
  if (error.code === "REVIEW_BULK_CONFIRM_BLOCKED") return "选中项包含重复风险或非待确认状态，无法批量确认。";
  return "暂时无法完成校对操作，请稍后重试。";
}
