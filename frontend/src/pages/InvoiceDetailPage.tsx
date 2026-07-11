import { useEffect, useMemo, useState } from "react";

import { FieldEditor, type EditableField } from "../components/FieldEditor";
import { InvoicePreview, type InvoiceDocumentMeta } from "../components/InvoicePreview";
import { LineItemsEditor, type InvoiceLineItem } from "../components/LineItemsEditor";
import { ProjectFilter } from "../components/ProjectFilter";
import { ApiError, apiGet, apiPatch, apiPost, apiPut } from "../lib/api";
import type { ProjectSummary } from "../lib/projects";

type InvoiceDetail = {
  amount_with_tax: string | null;
  amount_without_tax: string | null;
  archived_at: string | null;
  buyer_name: string | null;
  buyer_tax_id: string | null;
  check_code: string | null;
  confirmed_at: string | null;
  corrections: Array<{
    changed_at: string | null;
    field_path: string;
    id: string;
    new_value: string | null;
    ocr_value: string | null;
    old_value: string | null;
  }>;
  document: InvoiceDocumentMeta | null;
  expense_scene: string | null;
  id: string;
  invoice_code: string | null;
  invoice_date: string | null;
  invoice_number: string | null;
  invoice_type: string | null;
  is_duplicate_suspected: boolean;
  project: {
    id: string;
    name: string;
    visibility: string;
    status: string;
  } | null;
  items: InvoiceLineItem[];
  normalized_payload: {
    field_sources?: Record<string, { name: string; value: string | null }>;
    invoice_fields?: Record<string, string | null>;
    supplemental_fields?: Array<{ group: string; name: string; value: string }>;
  } | null;
  ocr: {
    error_code: string | null;
    id: string;
    provider: string;
    provider_error_code: string | null;
    request_id: string | null;
    status: string;
  } | null;
  seller_name: string | null;
  seller_tax_id: string | null;
  status: string;
  tax_amount: string | null;
};

type DraftFields = Record<InvoiceFieldName, string>;

type InvoiceFieldName = (typeof invoiceFields)[number]["name"];

const invoiceFields = [
  { group: "发票基础信息", label: "发票类型", name: "invoice_type" },
  { group: "发票基础信息", label: "发票代码", name: "invoice_code" },
  { group: "发票基础信息", label: "发票号码", name: "invoice_number" },
  { group: "发票基础信息", label: "开票日期", name: "invoice_date", type: "date" },
  { group: "销售方信息", label: "销售方", name: "seller_name" },
  { group: "销售方信息", label: "销售方税号", name: "seller_tax_id" },
  { group: "购买方信息", label: "购买方", name: "buyer_name" },
  { group: "购买方信息", label: "购买方税号", name: "buyer_tax_id" },
  { group: "金额信息", label: "不含税金额", name: "amount_without_tax", type: "number" },
  { group: "金额信息", label: "税额", name: "tax_amount", type: "number" },
  { group: "金额信息", label: "价税合计", name: "amount_with_tax", type: "number" },
  { group: "金额信息", label: "校验码", name: "check_code" },
  { group: "归档信息", label: "业务场景", name: "expense_scene" },
] as const;

export function InvoiceDetailPage({ invoiceId }: { invoiceId: string }) {
  const [detail, setDetail] = useState<InvoiceDetail | null>(null);
  const [draft, setDraft] = useState<DraftFields | null>(null);
  const [lineItems, setLineItems] = useState<InvoiceLineItem[]>([]);
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [message, setMessage] = useState("");
  const [status, setStatus] = useState<"loading" | "ready" | "saving" | "error">("loading");

  useEffect(() => {
    loadInvoice();
  }, [invoiceId]);

  useEffect(() => {
    let cancelled = false;
    apiGet<ProjectSummary[]>("/api/v1/projects")
      .then((data) => {
        if (!cancelled) setProjects(data);
      })
      .catch(() => {
        if (!cancelled) setProjects([]);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const editableFields = useMemo(() => {
    if (!detail || !draft) {
      return [];
    }
    const ocrFields = detail.normalized_payload?.invoice_fields ?? {};
    const fieldSources = detail.normalized_payload?.field_sources ?? {};
    return invoiceFields.map((field): EditableField => ({
      group: field.group,
      label: field.label,
      name: field.name,
      ocrSource: fieldSources[field.name]?.name ?? null,
      ocrValue: fieldSources[field.name]?.value ?? ocrFields[field.name] ?? null,
      type: "type" in field ? field.type : "text",
      value: draft[field.name],
    }));
  }, [detail, draft]);

  async function loadInvoice() {
    setStatus("loading");
    try {
      const data = await apiGet<InvoiceDetail>(`/api/v1/invoices/${invoiceId}`);
      setDetail(data);
      setDraft(toDraft(data));
      setLineItems(data.items);
      setMessage("");
      setStatus("ready");
    } catch (error) {
      setStatus("error");
      setMessage(apiErrorMessage(error, "无法加载发票详情。"));
    }
  }

  async function saveFields() {
    if (!detail || !draft) {
      return;
    }
    setStatus("saving");
    try {
      const updated = await apiPatch<InvoiceDetail>(`/api/v1/invoices/${detail.id}`, buildPatch(draft));
      setDetail(updated);
      setDraft(toDraft(updated));
      setMessage("字段已保存。");
      setStatus("ready");
    } catch (error) {
      setStatus("error");
      setMessage(apiErrorMessage(error, "字段保存失败。"));
    }
  }

  async function saveLineItems() {
    if (!detail) {
      return;
    }
    setStatus("saving");
    try {
      const updated = await apiPut<InvoiceDetail>(`/api/v1/invoices/${detail.id}/items`, { items: lineItems });
      setDetail(updated);
      setDraft(toDraft(updated));
      setLineItems(updated.items);
      setMessage("明细已提交保存。");
      setStatus("ready");
    } catch (error) {
      setStatus("error");
      setMessage(apiErrorMessage(error, "明细保存失败。"));
    }
  }

  async function moveProject(projectId: string) {
    if (!detail || !projectId || projectId === detail.project?.id) {
      return;
    }
    setStatus("saving");
    try {
      const updated = await apiPatch<InvoiceDetail>(`/api/v1/invoices/${detail.id}`, { project_id: projectId });
      setDetail(updated);
      setDraft(toDraft(updated));
      setLineItems(updated.items);
      setMessage("已更新归属项目。");
      setStatus("ready");
    } catch (error) {
      setStatus("error");
      setMessage(apiErrorMessage(error, "项目移动失败。"));
    }
  }

  async function runAction(action: "archive" | "confirm") {
    if (!detail) {
      return;
    }
    setStatus("saving");
    try {
      const updated = await apiPost<InvoiceDetail>(`/api/v1/invoices/${detail.id}/${action}`);
      setDetail(updated);
      setDraft(toDraft(updated));
      setMessage(action === "confirm" ? "发票已确认。" : "发票已归档。");
      setStatus("ready");
    } catch (error) {
      setStatus("error");
      setMessage(apiErrorMessage(error, "操作失败。"));
    }
  }

  async function retryOcr() {
    if (!detail?.ocr?.id) {
      setMessage("当前发票没有可重试的 OCR 作业。");
      return;
    }
    setStatus("saving");
    try {
      await apiPost(`/api/v1/ocr-jobs/${detail.ocr.id}/retry`);
      setMessage("已提交重新识别。");
      setStatus("ready");
    } catch (error) {
      setStatus("error");
      setMessage(apiErrorMessage(error, "重新识别失败。"));
    }
  }

  if (status === "loading" && !detail) {
    return (
      <section className="surface-panel empty-panel">
        <div>
          <span className="section-label">发票详情</span>
          <h1>加载中</h1>
        </div>
      </section>
    );
  }

  if (!detail || !draft) {
    return (
      <section className="surface-panel empty-panel">
        <div>
          <span className="section-label">发票详情</span>
          <h1>无法加载发票</h1>
          <p>{message}</p>
        </div>
      </section>
    );
  }

  return (
    <div className="page-stack invoice-review-workbench">
      <section className="surface-panel detail-header">
        <div>
          <a className="section-label" href="#/invoices">
            返回发票库
          </a>
          <h2>{detail.invoice_number || "未识别发票号码"}</h2>
          <p>
            {detail.seller_name || "未知销售方"} · {detail.invoice_date || "未知日期"} · {detail.amount_with_tax || "金额待校对"}
          </p>
        </div>
        <div className="detail-actions persistent-review-actions">
          <button className="button primary" disabled={status === "saving"} onClick={() => runAction("confirm")} type="button">
            确认无误
          </button>
          <button className="button secondary" disabled={status === "saving"} onClick={() => runAction("archive")} type="button">
            归档
          </button>
          <button className="button secondary" disabled={status === "saving"} onClick={retryOcr} type="button">
            重新识别
          </button>
        </div>
      </section>

      {message ? <p className={`inline-message ${status === "error" ? "error" : ""}`}>{message}</p> : null}

      <section className="invoice-detail-layout">
        <InvoicePreview document={detail.document} />
        <div className="detail-editor-stack field-inspector">
          <section className="surface-panel project-assignment-panel">
            <div>
              <span className="section-label">项目归档</span>
              <h2>{detail.project?.name || "未分类"}</h2>
              <p>调整后会保留项目移动的修正记录。</p>
            </div>
            <ProjectFilter
              disabled={status === "saving" || projects.length === 0}
              includeAll={false}
              label="归属项目"
              onChange={moveProject}
              projects={projects}
              value={detail.project?.id ?? ""}
            />
          </section>
          <section className="surface-panel">
            <div className="panel-heading">
              <div>
                <span className="section-label">字段校对</span>
                <h2>OCR 原值与当前值</h2>
              </div>
              <button className="button primary" disabled={status === "saving"} onClick={saveFields} type="button">
                保存字段
              </button>
            </div>
            <FieldEditor
              fields={editableFields}
              onChange={(name, value) => setDraft((current) => (current ? { ...current, [name]: value } : current))}
            />
            <SupplementalOcrFields fields={detail.normalized_payload?.supplemental_fields ?? []} />
          </section>

          <section className="surface-panel">
            <div className="panel-heading">
              <div>
                <span className="section-label">明细项目</span>
                <h2>{lineItems.length} 行</h2>
              </div>
              <button className="button secondary" disabled={status === "saving"} onClick={saveLineItems} type="button">
                保存明细
              </button>
            </div>
            <LineItemsEditor items={lineItems} onChange={setLineItems} />
          </section>

          <section className="surface-panel ocr-meta">
            <span className="section-label">OCR 元信息</span>
            <dl>
              <div>
                <dt>状态</dt>
                <dd>{detail.ocr?.status || "-"}</dd>
              </div>
              <div>
                <dt>运营商</dt>
                <dd>{detail.ocr?.provider || "-"}</dd>
              </div>
              <div>
                <dt>RequestId</dt>
                <dd>{detail.ocr?.request_id || "-"}</dd>
              </div>
              <div>
                <dt>错误码</dt>
                <dd>{detail.ocr?.provider_error_code || detail.ocr?.error_code || "-"}</dd>
              </div>
            </dl>
          </section>

          <section className="surface-panel correction-log">
            <span className="section-label">修正记录</span>
            {detail.corrections.length ? (
              <ul>
                {detail.corrections.map((correction) => (
                  <li key={correction.id}>
                    <strong>{correction.field_path}</strong>
                    <span>
                      {correction.old_value || "-"} → {correction.new_value || "-"}
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <p>暂无人工修正记录。</p>
            )}
          </section>
        </div>
      </section>
    </div>
  );
}

function toDraft(detail: InvoiceDetail): DraftFields {
  return Object.fromEntries(invoiceFields.map((field) => [field.name, scalar(detail[field.name])])) as DraftFields;
}

function buildPatch(draft: DraftFields) {
  return Object.fromEntries(
    invoiceFields.map((field) => {
      const value = draft[field.name].trim();
      return [field.name, value === "" ? null : value];
    }),
  );
}

function scalar(value: string | null) {
  return value ?? "";
}

function apiErrorMessage(error: unknown, fallback: string) {
  return error instanceof ApiError ? error.message : fallback;
}

function SupplementalOcrFields({ fields }: { fields: Array<{ group: string; name: string; value: string }> }) {
  if (!fields.length) return null;

  const groups = fields.reduce<Array<{ name: string; fields: typeof fields }>>((result, field) => {
    let group = result.find((candidate) => candidate.name === field.group);
    if (!group) {
      group = { name: field.group, fields: [] };
      result.push(group);
    }
    group.fields.push(field);
    return result;
  }, []);

  return (
    <section className="ocr-supplemental">
      <div className="field-group-heading">
        <span className="section-label">补充识别信息</span>
      </div>
      {groups.map((group) => (
        <div className="ocr-supplemental-group" key={group.name}>
          <h3>{group.name}</h3>
          <dl className="ocr-supplemental-grid">
            {group.fields.map((field, index) => (
              <div key={`${field.name}-${index}`}>
                <dt>{field.name}</dt>
                <dd>{field.value}</dd>
              </div>
            ))}
          </dl>
        </div>
      ))}
    </section>
  );
}
