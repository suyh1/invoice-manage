import { useCallback, useEffect, useMemo, useState } from "react";
import { Download, FilePlus2, RefreshCw } from "lucide-react";

import { ProjectFilter } from "../components/ProjectFilter";
import { ApiError, apiGet, apiPost } from "../lib/api";
import { canDownloadExport, exportStatusLabel, shouldPollExport, toReexportPayload, type ExportStatus } from "../lib/exportTasks";
import type { ProjectSummary } from "../lib/projects";

type ExportTask = {
  id: string;
  format: "csv" | "json" | "xlsx";
  filters: Record<string, unknown>;
  status: ExportStatus;
  storage_key: string | null;
  error_message: string | null;
  created_by: string;
  created_by_user: { id: string; display_name: string; email: string } | null;
  created_at: string | null;
  expires_at: string | null;
};

export function ExportRecordsPage() {
  const [tasks, setTasks] = useState<ExportTask[]>([]);
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [projectId, setProjectId] = useState("");
  const [status, setStatus] = useState("");
  const [format, setFormat] = useState<ExportTask["format"]>("xlsx");
  const [includeItems, setIncludeItems] = useState(true);
  const [includeOcrMeta, setIncludeOcrMeta] = useState(true);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const loadTasks = useCallback(async () => {
    try {
      const data = await apiGet<ExportTask[]>("/api/v1/exports");
      setTasks(data);
    } catch (error) {
      setMessage(exportError(error));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadTasks();
    apiGet<ProjectSummary[]>("/api/v1/projects").then(setProjects).catch(() => setProjects([]));
  }, [loadTasks]);

  const hasRunningTask = useMemo(() => tasks.some((task) => shouldPollExport(task.status)), [tasks]);
  useEffect(() => {
    if (!hasRunningTask) return;
    const timer = window.setInterval(() => void loadTasks(), 2500);
    return () => window.clearInterval(timer);
  }, [hasRunningTask, loadTasks]);

  async function createExport(payload = currentPayload()) {
    setBusy(true);
    setMessage(null);
    try {
      await apiPost<ExportTask>("/api/v1/exports", payload);
      await loadTasks();
    } catch (error) {
      setMessage(exportError(error));
    } finally {
      setBusy(false);
    }
  }

  function currentPayload() {
    const filters: Record<string, unknown> = {};
    if (projectId) filters.project_id = projectId;
    if (status) filters.status = [status];
    return { format, scope: "filtered_invoices", filters, include_items: includeItems, include_ocr_meta: includeOcrMeta };
  }

  return (
    <div className="page-stack export-page export-ledger">
      <section className="surface-panel export-create editorial-page-heading">
        <div>
          <span className="section-label">DATA DELIVERY / 数据交付</span>
          <h2>创建导出</h2>
          <p>按当前项目和发票状态生成可下载的数据文件。</p>
        </div>
        <div className="export-create-controls">
          <ProjectFilter label="项目" onChange={setProjectId} projects={projects} value={projectId} />
          <label>发票状态<select value={status} onChange={(event) => setStatus(event.currentTarget.value)}><option value="">全部状态</option><option value="confirmed">已确认</option><option value="needs_review">待人工确认</option><option value="archived">已归档</option></select></label>
          <label>格式<select value={format} onChange={(event) => setFormat(event.currentTarget.value as ExportTask["format"])}><option value="xlsx">XLSX 工作簿</option><option value="csv">CSV</option><option value="json">JSON</option></select></label>
          <label className="check-row"><input checked={includeItems} onChange={(event) => setIncludeItems(event.currentTarget.checked)} type="checkbox" /><span>包含明细</span></label>
          <label className="check-row"><input checked={includeOcrMeta} onChange={(event) => setIncludeOcrMeta(event.currentTarget.checked)} type="checkbox" /><span>包含 OCR 元数据</span></label>
          <button className="button primary" disabled={busy} onClick={() => void createExport()} type="button"><FilePlus2 aria-hidden="true" size={17} />{busy ? "正在创建..." : "创建导出"}</button>
        </div>
      </section>

      <section className="surface-panel export-records ledger-surface">
        <div className="panel-heading"><div><span className="section-label">导出记录</span><h2>{loading ? "正在加载" : `${tasks.length} 个任务`}</h2></div></div>
        {message ? <p className="inline-message error" role="alert">{message}</p> : null}
        {loading ? <div className="empty-state"><strong>正在加载导出记录...</strong></div> : !tasks.length ? <div className="empty-state"><strong>暂无导出记录</strong><p>创建导出后，文件状态和下载入口会显示在这里。</p></div> : <div className="export-table-wrap"><table className="export-table"><thead><tr><th>范围</th><th>格式</th><th>创建人</th><th>状态</th><th>创建时间</th><th>过期时间</th><th>操作</th></tr></thead><tbody>{tasks.map((task) => { const canDownload = canDownloadExport(task); return <tr key={task.id}><td>{describeFilters(task.filters)}</td><td>{task.format.toUpperCase()}</td><td>{task.created_by_user?.display_name || "未知"}</td><td><span className={`status-token ${task.status === "completed" ? "success" : task.status === "failed" ? "danger" : "neutral"}`}>{exportStatusLabel(task.status)}</span>{task.error_message ? <small>{task.error_message}</small> : null}</td><td>{formatDateTime(task.created_at)}</td><td>{task.expires_at ? formatDateTime(task.expires_at) : "-"}</td><td><div className="row-actions">{canDownload ? <a className="button secondary" href={`/api/v1/exports/${task.id}/download`}><Download aria-hidden="true" size={16} />下载</a> : null}{(task.status === "failed" || (task.status === "completed" && !canDownload)) ? <button className="button secondary" disabled={busy} onClick={() => void createExport(toReexportPayload(task))} type="button"><RefreshCw aria-hidden="true" size={16} />重新创建</button> : null}</div></td></tr>; })}</tbody></table></div>}
      </section>
    </div>
  );
}

function describeFilters(filters: Record<string, unknown>) { return filters.project_id ? "已筛选项目" : "全部可见发票"; }
function formatDateTime(value: string | null) { return value ? new Intl.DateTimeFormat("zh-CN", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value)) : "-"; }
function exportError(error: unknown) { return error instanceof ApiError ? "暂时无法完成导出操作，请稍后重试。" : "暂时无法连接系统，请稍后重试。"; }
