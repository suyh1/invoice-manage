import { useEffect, useRef } from "react";
import { Download, ExternalLink, X } from "lucide-react";

import type { ProjectFileSummary } from "./ProjectFileTable";

export function ProjectFilePreviewDialog({
  file,
  onClose,
}: {
  file: ProjectFileSummary;
  onClose: () => void;
}) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const previewUrl = `/api/v1/documents/${file.id}/preview`;
  const downloadUrl = `/api/v1/documents/${file.id}/download`;
  const isPdf = file.file_ext.toLowerCase() === "pdf";

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (typeof dialog.showModal === "function") {
      dialog.showModal();
    } else {
      dialog.setAttribute("open", "");
    }
    return () => {
      if (typeof dialog.close === "function" && dialog.open) dialog.close();
    };
  }, []);

  function closeDialog() {
    const dialog = dialogRef.current;
    if (dialog && typeof dialog.close === "function" && dialog.open) dialog.close();
    onClose();
  }

  return (
    <dialog
      aria-label={`预览 ${file.original_filename}`}
      aria-modal="true"
      className="project-file-preview-dialog"
      onCancel={(event) => {
        event.preventDefault();
        closeDialog();
      }}
      onClose={onClose}
      ref={dialogRef}
    >
      <header className="project-file-preview-heading">
        <div>
          <span className="section-label">PROJECT FILE / 项目文件</span>
          <h2 title={file.original_filename}>{file.original_filename}</h2>
        </div>
        <div className="project-file-preview-actions">
          <a
            aria-label={`在新窗口打开 ${file.original_filename}`}
            className="icon-button"
            href={previewUrl}
            rel="noreferrer"
            target="_blank"
            title="在新窗口打开"
          >
            <ExternalLink aria-hidden="true" size={17} />
          </a>
          <a
            aria-label={`下载 ${file.original_filename}`}
            className="icon-button"
            href={downloadUrl}
            title="下载"
          >
            <Download aria-hidden="true" size={17} />
          </a>
          <button aria-label="关闭预览" className="icon-button" onClick={closeDialog} title="关闭" type="button">
            <X aria-hidden="true" size={18} />
          </button>
        </div>
      </header>
      <div className={`project-file-preview-canvas ${isPdf ? "pdf" : "image"}`}>
        {isPdf ? (
          <iframe src={previewUrl} title="项目文件 PDF 预览" />
        ) : (
          <img alt={file.original_filename} src={previewUrl} />
        )}
      </div>
    </dialog>
  );
}
