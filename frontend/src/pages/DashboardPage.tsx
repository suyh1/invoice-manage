import { OcrQuotaStatus } from "../components/OcrQuotaStatus";

const metrics = [
  { label: "待校对", value: "0", note: "等待 OCR 结果接入" },
  { label: "识别失败", value: "0", note: "可重试任务将在队列页显示" },
  { label: "近 30 天金额", value: "¥0.00", note: "确认后纳入统计" },
  { label: "队列积压", value: "0", note: "Celery worker 状态" },
];

export function DashboardPage() {
  return (
    <div className="page-stack">
      <section className="dashboard-band">
        <div>
          <span className="section-label">工作台</span>
          <h2>集中处理发票上传、OCR、校对与导出</h2>
          <p>当前壳层先接入导航、设置和状态区，后续页面会逐步连到上传队列、发票库与导出任务。</p>
        </div>
        <OcrQuotaStatus />
      </section>

      <section className="metric-grid" aria-label="关键指标">
        {metrics.map((metric) => (
          <article className="metric-card" key={metric.label}>
            <span>{metric.label}</span>
            <strong>{metric.value}</strong>
            <p>{metric.note}</p>
          </article>
        ))}
      </section>

      <section className="surface-panel split-panel">
        <div>
          <span className="section-label">当前优先事项</span>
          <h2>先确认 OCR 运营商，再开始批量上传</h2>
        </div>
        <ul className="task-list">
          <li>配置默认 Tencent 或 Mock OCR 运营商</li>
          <li>校准免费额度或资源包提醒阈值</li>
          <li>确认 Celery worker 和 Redis 队列在线</li>
        </ul>
      </section>
    </div>
  );
}
