import { useEffect, useState } from "react";
import { AlertTriangle, CheckCheck, FileOutput, ListTodo } from "lucide-react";

import { OcrQuotaStatus } from "../components/OcrQuotaStatus";
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
    { label: "待人工确认", value: String(summary.needs_review), note: "进入待校对处理队列", icon: CheckCheck },
    { label: "疑似重复", value: String(summary.duplicates), note: "需要核验重复风险", icon: AlertTriangle },
    { label: "近 30 天已确认金额", value: `¥${summary.confirmed_amount_30d}`, note: "只统计已确认发票", icon: FileOutput },
    { label: "OCR 队列积压", value: String(summary.queued_ocr), note: `识别失败 ${summary.ocr_failed} 条`, icon: ListTodo },
  ] : [];
  return <div className="page-stack"><section className="dashboard-band"><div><span className="section-label">工作台</span><h2>集中处理发票上传、OCR、校对与导出</h2><p>从识别结果进入待校对，再按项目生成可追溯导出文件。</p></div><OcrQuotaStatus /></section>{error ? <p className="inline-message error" role="alert">{error}</p> : null}<section className="metric-grid" aria-label="关键指标">{metrics.length ? metrics.map(({ icon: Icon, ...metric }) => <article className="metric-card" key={metric.label}><Icon aria-hidden="true" size={19} /><span>{metric.label}</span><strong>{metric.value}</strong><p>{metric.note}</p></article>) : <div className="management-loading">正在加载总览指标...</div>}</section><section className="surface-panel split-panel"><div><span className="section-label">最近导出</span><h2>{summary?.recent_exports.length ? `${summary.recent_exports.length} 个最近任务` : "暂无导出任务"}</h2></div><ul className="task-list">{summary?.recent_exports.length ? summary.recent_exports.map((task) => <li key={task.id}>{task.format.toUpperCase()} · {task.status}</li>) : <li>完成校对后，可在导出记录创建结构化文件。</li>}</ul></section></div>;
}
