export type ExportStatus = "queued" | "running" | "completed" | "failed";

const exportStatusLabels: Record<ExportStatus, string> = {
  queued: "等待导出",
  running: "正在导出",
  completed: "已完成",
  failed: "导出失败",
};

export function exportStatusLabel(status: ExportStatus): string {
  return exportStatusLabels[status];
}

export function shouldPollExport(status: ExportStatus): boolean {
  return status === "queued" || status === "running";
}

export function canDownloadExport(
  task: { status: ExportStatus; expires_at: string | null },
  now = new Date(),
): boolean {
  return task.status === "completed" && (!task.expires_at || new Date(task.expires_at) > now);
}

export function toReexportPayload(task: {
  format: "csv" | "json" | "xlsx";
  filters: Record<string, unknown>;
}) {
  const { include_items = true, include_ocr_meta = true, scope = "filtered_invoices", ...filters } = task.filters;
  return {
    format: task.format,
    scope: String(scope),
    filters,
    include_items: Boolean(include_items),
    include_ocr_meta: Boolean(include_ocr_meta),
  };
}
