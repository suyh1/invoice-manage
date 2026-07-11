import { useState } from "react";
import { Download, Eye, Trash2 } from "lucide-react";

import { ProjectFilePreviewDialog } from "./ProjectFilePreviewDialog";

export type ProjectFileSummary = {
  content_type: string;
  created_at: string | null;
  document_kind: "project_file";
  file_ext: string;
  file_size: number;
  id: string;
  original_filename: string;
  project: { id: string; name: string };
  sha256: string;
  uploaded_by_user: {
    display_name: string;
    email: string;
    id: string;
  };
};

export function ProjectFileTable({
  busyId,
  files,
  onDelete,
}: {
  busyId: string | null;
  files: ProjectFileSummary[];
  onDelete: (id: string) => void;
}) {
  const [confirmingId, setConfirmingId] = useState<string | null>(null);
  const [previewFile, setPreviewFile] = useState<ProjectFileSummary | null>(null);

  if (!files.length) {
    return (
      <div className="empty-state invoice-empty">
        <strong>当前项目还没有普通文件</strong>
        <p>可在上传页切换到“项目文件”，将无需识别的资料直接归档到项目。</p>
        <div className="empty-actions">
          <a className="button primary" href="#/upload">上传项目文件</a>
        </div>
      </div>
    );
  }

  return (
    <div className="project-file-table-wrap">
      <table className="project-file-table">
        <thead>
          <tr>
            <th>文件</th>
            <th>格式</th>
            <th>大小</th>
            <th>上传人</th>
            <th>上传时间</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          {files.map((file) => {
            const isConfirming = confirmingId === file.id;
            const isBusy = busyId === file.id;
            return (
              <tr key={file.id}>
                <td className="project-file-name" title={file.original_filename}>
                  <strong>{file.original_filename}</strong>
                  <small>{file.project.name}</small>
                </td>
                <td>{file.file_ext.toUpperCase()}</td>
                <td>{formatBytes(file.file_size)}</td>
                <td title={file.uploaded_by_user.email}>{file.uploaded_by_user.display_name}</td>
                <td>{formatDateTime(file.created_at)}</td>
                <td>
                  <div className="project-file-actions">
                    {isInlinePreview(file.file_ext) ? (
                      <button
                        aria-label={`预览 ${file.original_filename}`}
                        className="icon-button"
                        onClick={() => setPreviewFile(file)}
                        title="预览"
                        type="button"
                      >
                        <Eye aria-hidden="true" size={16} />
                      </button>
                    ) : (
                      <a
                        aria-label={`预览 ${file.original_filename}`}
                        className="icon-button"
                        href={`/api/v1/documents/${file.id}/preview`}
                        rel="noreferrer"
                        target="_blank"
                        title="在新窗口预览"
                      >
                        <Eye aria-hidden="true" size={16} />
                      </a>
                    )}
                    <a
                      aria-label={`下载 ${file.original_filename}`}
                      className="icon-button"
                      href={`/api/v1/documents/${file.id}/download`}
                      title="下载"
                    >
                      <Download aria-hidden="true" size={16} />
                    </a>
                    <button
                      aria-label={`${isConfirming ? "确认删除" : "删除"} ${file.original_filename}`}
                      className={`icon-button ${isConfirming ? "confirm-delete" : ""}`}
                      disabled={isBusy}
                      onClick={() => {
                        if (!isConfirming) {
                          setConfirmingId(file.id);
                          return;
                        }
                        onDelete(file.id);
                      }}
                      title={isConfirming ? "再次点击确认删除" : "删除"}
                      type="button"
                    >
                      <Trash2 aria-hidden="true" size={16} />
                    </button>
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {previewFile ? <ProjectFilePreviewDialog file={previewFile} onClose={() => setPreviewFile(null)} /> : null}
    </div>
  );
}

function isInlinePreview(fileExt: string) {
  return ["jpeg", "jpg", "pdf", "png"].includes(fileExt.toLowerCase());
}

function formatBytes(size: number) {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${formatNumber(size / 1024)} KB`;
  return `${formatNumber(size / (1024 * 1024))} MB`;
}

function formatNumber(value: number) {
  return Number.isInteger(value) ? value.toFixed(0) : value.toFixed(1);
}

function formatDateTime(value: string | null) {
  if (!value) return "-";
  return new Intl.DateTimeFormat("zh-CN", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}
