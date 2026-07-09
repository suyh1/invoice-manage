import { useEffect, useMemo, useState } from "react";

import { InvoiceTable, type InvoiceSummary } from "../components/InvoiceTable";
import { ApiError, apiGet } from "../lib/api";

type InvoiceListResponse = {
  items: InvoiceSummary[];
  total: number;
};

type InvoiceFilters = {
  duplicate: string;
  file_type: string;
  q: string;
  scene: string;
  status: string;
};

const emptyFilters: InvoiceFilters = {
  duplicate: "",
  file_type: "",
  q: "",
  scene: "",
  status: "",
};

const savedViews: Array<{ filters: Partial<InvoiceFilters>; label: string }> = [
  { filters: {}, label: "全部" },
  { filters: { status: "draft" }, label: "待校对" },
  { filters: { duplicate: "true" }, label: "疑似重复" },
  { filters: { status: "confirmed" }, label: "已确认" },
  { filters: { file_type: "pdf" }, label: "PDF" },
];

export function InvoiceListPage() {
  const [filters, setFilters] = useState<InvoiceFilters>(emptyFilters);
  const [invoices, setInvoices] = useState<InvoiceSummary[]>([]);
  const [message, setMessage] = useState("");
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");

  const query = useMemo(() => buildQuery(filters), [filters]);

  useEffect(() => {
    let cancelled = false;
    setStatus("loading");
    apiGet<InvoiceListResponse>(`/api/v1/invoices${query}`)
      .then((data) => {
        if (!cancelled) {
          setInvoices(data.items);
          setStatus("ready");
          setMessage("");
        }
      })
      .catch((error) => {
        if (!cancelled) {
          setStatus("error");
          setMessage(error instanceof ApiError ? error.message : "无法加载发票列表。");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [query]);

  function applySavedView(viewFilters: Partial<InvoiceFilters>) {
    setFilters({ ...emptyFilters, ...viewFilters });
  }

  return (
    <div className="page-stack">
      <section className="surface-panel invoice-list-header">
        <div>
          <span className="section-label">发票库</span>
          <h2>搜索、筛选与批量校对入口</h2>
          <p>列表保留 OCR 状态、疑似重复和原件类型，详情页继续完成字段校对与确认归档。</p>
        </div>
        <div className="saved-view-bar" aria-label="常用视图">
          {savedViews.map((view) => (
            <button className="button secondary" key={view.label} onClick={() => applySavedView(view.filters)} type="button">
              {view.label}
            </button>
          ))}
        </div>
      </section>

      <section className="surface-panel invoice-filters" aria-label="发票筛选">
        <label>
          搜索
          <input
            value={filters.q}
            onChange={(event) => setFilters({ ...filters, q: event.currentTarget.value })}
            placeholder="号码、代码、销售方、购买方"
          />
        </label>
        <label>
          状态
          <select value={filters.status} onChange={(event) => setFilters({ ...filters, status: event.currentTarget.value })}>
            <option value="">全部状态</option>
            <option value="draft">待校对</option>
            <option value="duplicate_suspected">疑似重复</option>
            <option value="confirmed">已确认</option>
            <option value="archived">已归档</option>
          </select>
        </label>
        <label>
          疑似重复
          <select value={filters.duplicate} onChange={(event) => setFilters({ ...filters, duplicate: event.currentTarget.value })}>
            <option value="">全部</option>
            <option value="true">仅疑似重复</option>
            <option value="false">排除疑似重复</option>
          </select>
        </label>
        <label>
          文件类型
          <select value={filters.file_type} onChange={(event) => setFilters({ ...filters, file_type: event.currentTarget.value })}>
            <option value="">全部类型</option>
            <option value="png">PNG</option>
            <option value="jpg">JPG</option>
            <option value="jpeg">JPEG</option>
            <option value="pdf">PDF</option>
          </select>
        </label>
        <label>
          场景
          <select value={filters.scene} onChange={(event) => setFilters({ ...filters, scene: event.currentTarget.value })}>
            <option value="">全部场景</option>
            <option value="travel">差旅</option>
            <option value="purchase">采购</option>
            <option value="office">办公</option>
            <option value="meal">餐饮</option>
            <option value="transport">交通</option>
          </select>
        </label>
      </section>

      <section className="surface-panel invoice-list-panel">
        <div className="panel-heading">
          <div>
            <span className="section-label">查询结果</span>
            <h2>{status === "loading" ? "加载中" : `${invoices.length} 张发票`}</h2>
          </div>
          {message ? <span className="status-token danger">{message}</span> : null}
        </div>
        <InvoiceTable invoices={invoices} />
      </section>
    </div>
  );
}

function buildQuery(filters: InvoiceFilters) {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value) {
      params.set(key, value);
    }
  });
  const query = params.toString();
  return query ? `?${query}` : "";
}
