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

export function InvoiceTable({ invoices }: { invoices: InvoiceSummary[] }) {
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
        <thead>
          <tr>
            <th>发票号码</th>
            <th>项目</th>
            <th>销售方</th>
            <th>购买方</th>
            <th>日期</th>
            <th>金额</th>
            <th>状态</th>
            <th>文件</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          {invoices.map((invoice) => (
            <tr key={invoice.id}>
              <td>
                <strong>{invoice.invoice_number || "-"}</strong>
                <span>{invoice.invoice_code || "无代码"}</span>
              </td>
              <td>{invoice.project?.name || "未分类"}</td>
              <td>{invoice.seller_name || "-"}</td>
              <td>{invoice.buyer_name || "-"}</td>
              <td>{invoice.invoice_date || "-"}</td>
              <td>
                <strong>{formatMoney(invoice.amount_with_tax, invoice.currency)}</strong>
              </td>
              <td>
                <span className={`status-token ${invoice.is_duplicate_suspected ? "danger" : invoice.status === "confirmed" ? "success" : "neutral"}`}>
                  {invoice.is_duplicate_suspected ? "疑似重复" : invoiceStatusLabel(invoice.status)}
                </span>
              </td>
              <td>
                <span>{invoice.document?.file_ext?.toUpperCase() || "-"}</span>
                <small>{invoice.document?.original_filename || ""}</small>
              </td>
              <td>
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
}

function formatMoney(value: string | null, currency: string | null) {
  if (!value) {
    return "-";
  }
  return `${currency || "CNY"} ${value}`;
}
