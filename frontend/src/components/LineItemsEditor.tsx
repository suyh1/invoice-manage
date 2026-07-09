export type InvoiceLineItem = {
  amount: string | null;
  id: string;
  name: string | null;
  quantity: string | null;
  specification: string | null;
  tax_amount: string | null;
  tax_rate: string | null;
  unit: string | null;
  unit_price: string | null;
};

export function LineItemsEditor({
  items,
  onChange,
}: {
  items: InvoiceLineItem[];
  onChange: (items: InvoiceLineItem[]) => void;
}) {
  function updateItem(id: string, field: keyof InvoiceLineItem, value: string) {
    onChange(items.map((item) => (item.id === id ? { ...item, [field]: value } : item)));
  }

  if (!items.length) {
    return (
      <div className="empty-state line-items-empty">
        <strong>暂无明细项目</strong>
        <p>OCR 结果没有返回明细，或该发票类型不包含商品服务行。</p>
      </div>
    );
  }

  return (
    <div className="line-items-wrap">
      <table className="line-items-table">
        <thead>
          <tr>
            <th>名称</th>
            <th>规格</th>
            <th>单位</th>
            <th>数量</th>
            <th>单价</th>
            <th>金额</th>
            <th>税率</th>
            <th>税额</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.id}>
              <td>
                <input value={item.name ?? ""} onChange={(event) => updateItem(item.id, "name", event.currentTarget.value)} />
              </td>
              <td>
                <input value={item.specification ?? ""} onChange={(event) => updateItem(item.id, "specification", event.currentTarget.value)} />
              </td>
              <td>
                <input value={item.unit ?? ""} onChange={(event) => updateItem(item.id, "unit", event.currentTarget.value)} />
              </td>
              <td>
                <input value={item.quantity ?? ""} onChange={(event) => updateItem(item.id, "quantity", event.currentTarget.value)} />
              </td>
              <td>
                <input value={item.unit_price ?? ""} onChange={(event) => updateItem(item.id, "unit_price", event.currentTarget.value)} />
              </td>
              <td>
                <input value={item.amount ?? ""} onChange={(event) => updateItem(item.id, "amount", event.currentTarget.value)} />
              </td>
              <td>
                <input value={item.tax_rate ?? ""} onChange={(event) => updateItem(item.id, "tax_rate", event.currentTarget.value)} />
              </td>
              <td>
                <input value={item.tax_amount ?? ""} onChange={(event) => updateItem(item.id, "tax_amount", event.currentTarget.value)} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
