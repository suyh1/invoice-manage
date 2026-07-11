import type { UploadValidationIssue, UploadValidationResult } from "../lib/fileValidation";

export type UploadQueueStatus = "validating" | "blocked" | "ready" | "uploading" | "uploaded" | "ocr_queued" | "recognizing" | "completed" | "failed";

export type UploadQueueItem = {
  id: string;
  documentId?: string;
  error?: string;
  file: File;
  ocrJobId?: string | null;
  status: UploadQueueStatus;
  validation?: UploadValidationResult;
};

const statusCopy: Record<UploadQueueStatus, string> = {
  blocked: "需处理",
  completed: "已完成",
  failed: "失败",
  ocr_queued: "等待 OCR",
  ready: "待上传",
  recognizing: "识别中",
  uploaded: "已上传",
  uploading: "上传中",
  validating: "检查中",
};

export function UploadQueue({
  items,
  mode = "invoice",
  onRemove,
  onRetry,
  onUploadReady,
}: {
  items: UploadQueueItem[];
  mode?: "invoice" | "project_file";
  onRemove: (id: string) => void;
  onRetry: (id: string) => void;
  onUploadReady: (id: string) => void;
}) {
  if (!items.length) {
    return (
      <section className="surface-panel empty-upload-queue">
        <span className="section-label">上传队列</span>
        <strong>等待添加文件</strong>
        <p>{mode === "project_file" ? "文件会先在本地校验，通过后直接归档到项目。" : "文件会先在本地校验，通过后再发送到后端创建 OCR 作业。"}</p>
      </section>
    );
  }

  return (
    <section className="surface-panel upload-queue" aria-label="上传队列">
      <div className="panel-heading">
        <div>
          <span className="section-label">上传队列</span>
          <h2>{items.length} 个文件</h2>
        </div>
      </div>

      <div className="upload-queue-list">
        {items.map((item) => (
          <article className={`upload-queue-row ${item.status}`} key={item.id}>
            <div className="file-summary">
              <strong>{item.file.name}</strong>
              <span>
                {formatBytes(item.file.size)}
                {item.validation ? ` · Base64 ${formatBytes(item.validation.metadata.base64Size)}` : ""}
              </span>
            </div>
            <div className="upload-state">
              <span className={`status-token ${item.status === "completed" ? "success" : item.status === "failed" || item.status === "blocked" ? "danger" : "neutral"}`}>
                {statusCopy[item.status]}
              </span>
              {item.documentId ? <span>文档 {shortId(item.documentId)}</span> : null}
              {item.ocrJobId ? <span>作业 {shortId(item.ocrJobId)}</span> : null}
            </div>
            <IssueList issues={item.validation?.issues ?? []} error={item.error} />
            <div className="row-actions">
              {item.status === "ready" ? (
                <button className="button primary" onClick={() => onUploadReady(item.id)} type="button">
                  上传
                </button>
              ) : null}
              {item.status === "failed" ? (
                <button className="button secondary" onClick={() => onRetry(item.id)} type="button">
                  重试
                </button>
              ) : null}
              {item.status === "ready" || item.status === "blocked" || item.status === "failed" ? (
                <button className="button secondary" onClick={() => onRemove(item.id)} type="button">
                  移除
                </button>
              ) : null}
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

function IssueList({ error, issues }: { error?: string; issues: UploadValidationIssue[] }) {
  if (!issues.length && !error) {
    return <p className="queue-note">校验通过，等待上传。</p>;
  }

  return (
    <ul className="issue-list">
      {issues.map((issue) => (
        <li key={issue.code}>{issue.message}</li>
      ))}
      {error ? <li>{error}</li> : null}
    </ul>
  );
}

function formatBytes(bytes: number) {
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function shortId(id: string) {
  return id.slice(0, 8);
}
