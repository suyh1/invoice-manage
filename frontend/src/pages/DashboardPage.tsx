import { useEffect, useState } from "react";
import { ArrowRight, Check, FileOutput, RotateCcw, ScanLine } from "lucide-react";
import { ApiError, apiGet } from "../lib/api";

type DashboardSummary = {
  needs_review: number;
  duplicates: number;
  ocr_failed: number;
  confirmed_amount_30d: string;
  queued_ocr: number;
  recent_exports: Array<{ id: string; format: string; status: string; created_at: string | null }>;
};

export function DashboardPage() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [error, setError] = useState("");
  useEffect(() => { apiGet<DashboardSummary>("/api/v1/dashboard/summary").then(setSummary).catch((value) => setError(value instanceof ApiError ? value.message : "无法加载总览。")); }, []);
  const metrics = summary ? [
    { index: "01", label: "待人工确认", value: String(summary.needs_review).padStart(2, "0"), note: "进入待校对处理队列" },
    { index: "02", label: "疑似重复", value: String(summary.duplicates).padStart(2, "0"), note: "需要逐张核验" },
    { index: "03", label: "近 30 天确认金额", value: `¥ ${summary.confirmed_amount_30d}`, note: "只统计已确认发票", wide: true },
    { index: "04", label: "OCR 队列", value: String(summary.queued_ocr).padStart(2, "0"), note: `识别失败 ${summary.ocr_failed} 条` },
  ] : [];

  return (
    <div className="page-stack dashboard-page">
      <section className="dashboard-editorial-heading">
        <div>
          <span className="desk-kicker">OPERATIONS DESK · TODAY</span>
          <h1>今天有 <em>{summary?.needs_review ?? "—"} 张</em>发票<br />等待你的判断。</h1>
        </div>
        <div className="dashboard-heading-action">
          <p>识别、校对、归档与导出，所有动作都留有清晰记录。</p>
          <a href="#/review">开始处理 <ArrowRight aria-hidden="true" size={16} /></a>
        </div>
      </section>

      {error ? <p className="inline-message error" role="alert">{error}</p> : null}

      <section className="dashboard-ledger" aria-label="关键指标">
        {metrics.length ? metrics.map((metric) => (
          <article className={metric.wide ? "wide" : ""} key={metric.label}>
            <span>{metric.index} / {metric.label}</span>
            <strong>{metric.value}</strong>
            <p><i aria-hidden="true" />{metric.note}</p>
          </article>
        )) : <div className="management-loading">正在加载总览指标...</div>}
      </section>

      <div className="dashboard-desk-grid">
        <section className="priority-queue">
          <header className="desk-section-heading">
            <div><span>PRIORITY QUEUE / 优先队列</span><h2>今天需要处理</h2></div>
            <a href="#/review">查看全部 <ArrowRight aria-hidden="true" size={13} /></a>
          </header>
          <div className="priority-list">
            <a href="#/review"><b>01</b><span className="priority-symbol hatch" /><div><strong>待人工确认</strong><small>核对 OCR 字段并完成确认</small></div><em>{summary?.needs_review ?? "—"}</em><ArrowRight size={15} /></a>
            <a href="#/review"><b>02</b><span className="priority-symbol split" /><div><strong>疑似重复</strong><small>确认是否为重复上传原件</small></div><em>{summary?.duplicates ?? "—"}</em><ArrowRight size={15} /></a>
            <a href="#/review"><b>03</b><span className="priority-symbol ring" /><div><strong>识别失败</strong><small>检查原件质量并重新识别</small></div><em>{summary?.ocr_failed ?? "—"}</em><RotateCcw size={14} /></a>
          </div>
        </section>

        <aside className="activity-ledger">
          <header className="desk-section-heading"><div><span>ACTIVITY / 流转记录</span><h2>最近导出</h2></div></header>
          <ul>
            {summary?.recent_exports.length ? summary.recent_exports.map((task, index) => (
              <li key={task.id}><time>{String(index + 1).padStart(2, "0")}</time><FileOutput aria-hidden="true" size={14} /><div><strong>{task.format.toUpperCase()} · {task.status}</strong><p>{task.created_at ? new Date(task.created_at).toLocaleString("zh-CN") : "等待任务时间"}</p></div></li>
            )) : <li><time>—</time><ScanLine aria-hidden="true" size={14} /><div><strong>暂无导出任务</strong><p>完成校对后可生成结构化文件</p></div></li>}
          </ul>
          <div className="traceable-stamp"><span>Traceable.</span><strong><Check size={12} /> 全部操作可追溯</strong><small>ACTIVITY LOG · 365 DAYS</small></div>
        </aside>
      </div>
    </div>
  );
}
