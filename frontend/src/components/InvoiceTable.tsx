import { useState, type PointerEvent as ReactPointerEvent } from "react";

import { invoiceStatusLabel } from "../lib/invoiceStatus";

export type InvoiceSummary = {
  amount_with_tax: string | null;
  buyer_name: string | null;
  currency: string | null;
  document: {
    created_at: string | null;
    file_ext: string;
    original_filename: string;
    status: string;
  } | null;
  expense_scene: string | null;
  id: string;
  invoice_code: string | null;
  invoice_date: string | null;
  invoice_number: string | null;
  is_duplicate_suspected: boolean;
  project: {
    id: string;
    name: string;
    visibility: string;
    status: string;
  } | null;
  seller_name: string | null;
  status: string;
};

type ResizableColumnKey = "amount" | "date" | "number" | "seller";

type ColumnDefinition = {
  defaultWidth: number;
  key: ResizableColumnKey;
  label: string;
  maxWidth: number;
  minWidth: number;
};

const COLUMN_STORAGE_KEY = "invoice-table-column-widths";
const resizableColumns: ColumnDefinition[] = [
  { defaultWidth: 280, key: "number", label: "发票号码", maxWidth: 520, minWidth: 190 },
  { defaultWidth: 300, key: "seller", label: "销售方", maxWidth: 620, minWidth: 180 },
  { defaultWidth: 140, key: "date", label: "日期", maxWidth: 260, minWidth: 120 },
  { defaultWidth: 160, key: "amount", label: "金额", maxWidth: 300, minWidth: 130 },
];
const actionColumnWidth = 96;

export function InvoiceTable({ invoices }: { invoices: InvoiceSummary[] }) {
  const [columnWidths, setColumnWidths] = useState<Record<ResizableColumnKey, number>>(readColumnWidths);

  if (!invoices.length) {
    return (
      <div className="empty-state invoice-empty">
        <strong>没有匹配的发票</strong>
        <p>调整筛选条件，或先从上传识别页添加发票原件。</p>
        <div className="empty-actions">
          <a className="button primary" href="#/upload">上传发票</a>
          <a className="button secondary" href="#/invoices">返回发票库</a>
        </div>
      </div>
    );
  }

  return (
    <div className="invoice-table-wrap">
      <table className="invoice-table invoice-ledger-table">
        <colgroup>
          {resizableColumns.map((column) => <col key={column.key} style={{ width: columnWidths[column.key] }} />)}
          <col style={{ width: actionColumnWidth }} />
        </colgroup>
        <thead>
          <tr>
            {resizableColumns.map((column) => (
              <th data-resizable="true" key={column.key}>
                {column.label}
                <span
                  aria-label={`调整${column.label}列宽`}
                  aria-orientation="vertical"
                  className="column-resize-handle"
                  onPointerDown={(event) => startResize(event, column)}
                  role="separator"
                />
              </th>
            ))}
            <th data-resizable="false">操作</th>
          </tr>
        </thead>
        <tbody>
          {invoices.map((invoice) => (
            <tr key={invoice.id}>
              <td className="invoice-number-cell" title={invoice.invoice_number || "未识别发票号码"}>
                <strong>{invoice.invoice_number || "-"}</strong>
                <span className={`status-token ${invoice.is_duplicate_suspected ? "danger" : invoice.status === "confirmed" ? "success" : "neutral"}`}>
                  {invoice.is_duplicate_suspected ? "疑似重复" : invoiceStatusLabel(invoice.status)}
                </span>
              </td>
              <td className="invoice-seller-cell" title={invoice.seller_name || "未知销售方"}>{invoice.seller_name || "-"}</td>
              <td className="invoice-date-cell">{invoice.invoice_date || "-"}</td>
              <td className="invoice-amount-cell">
                <strong>{formatMoney(invoice.amount_with_tax, invoice.currency)}</strong>
              </td>
              <td className="invoice-action-cell">
                <a className="button secondary" href={`#/invoices/${invoice.id}`}>
                  查看
                </a>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );

  function startResize(event: ReactPointerEvent<HTMLSpanElement>, column: ColumnDefinition) {
    event.preventDefault();
    const startX = event.clientX;
    const startWidth = columnWidths[column.key];
    let nextWidth = startWidth;

    const handlePointerMove = (moveEvent: PointerEvent) => {
      nextWidth = clamp(startWidth + moveEvent.clientX - startX, column.minWidth, column.maxWidth);
      setColumnWidths((current) => ({ ...current, [column.key]: nextWidth }));
    };
    const handlePointerUp = () => {
      window.removeEventListener("pointermove", handlePointerMove);
      window.removeEventListener("pointerup", handlePointerUp);
      const persisted = { ...columnWidths, [column.key]: nextWidth };
      window.localStorage.setItem(COLUMN_STORAGE_KEY, JSON.stringify(persisted));
    };

    window.addEventListener("pointermove", handlePointerMove);
    window.addEventListener("pointerup", handlePointerUp);
  }
}

function readColumnWidths(): Record<ResizableColumnKey, number> {
  const defaults = Object.fromEntries(
    resizableColumns.map((column) => [column.key, column.defaultWidth]),
  ) as Record<ResizableColumnKey, number>;
  try {
    const stored = JSON.parse(window.localStorage.getItem(COLUMN_STORAGE_KEY) || "{}") as Partial<Record<ResizableColumnKey, number>>;
    return Object.fromEntries(
      resizableColumns.map((column) => {
        const storedWidth = stored[column.key];
        return [
          column.key,
          typeof storedWidth === "number"
            ? clamp(storedWidth, column.minWidth, column.maxWidth)
            : defaults[column.key],
        ];
      }),
    ) as Record<ResizableColumnKey, number>;
  } catch {
    return defaults;
  }
}

function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max);
}

function formatMoney(value: string | null, currency: string | null) {
  if (!value) {
    return "-";
  }
  return `${currency || "CNY"} ${value}`;
}
