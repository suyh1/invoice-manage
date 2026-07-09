import { useState } from "react";

export type InvoiceDocumentMeta = {
  content_type: string;
  file_ext: string;
  file_size: number;
  id: string;
  original_filename: string;
  sha256: string;
  status: string;
};

export function InvoicePreview({ document }: { document: InvoiceDocumentMeta | null }) {
  const [rotation, setRotation] = useState(0);
  const [zoom, setZoom] = useState(1);

  if (!document) {
    return (
      <section className="surface-panel invoice-preview">
        <span className="section-label">原件预览</span>
        <strong>暂无原件</strong>
      </section>
    );
  }

  const downloadUrl = `/api/v1/documents/${document.id}/download`;
  const isPdf = document.file_ext === "pdf";

  return (
    <section className="surface-panel invoice-preview">
      <div className="panel-heading">
        <div>
          <span className="section-label">原件预览</span>
          <h2>{document.original_filename}</h2>
        </div>
        <a className="button secondary" href={downloadUrl} target="_blank" rel="noreferrer">
          下载
        </a>
      </div>
      <div className="preview-toolbar" aria-label="预览工具">
        <button className="button secondary" type="button" onClick={() => setZoom((current) => Math.max(0.5, current - 0.1))}>
          缩小
        </button>
        <button className="button secondary" type="button" onClick={() => setZoom((current) => Math.min(2, current + 0.1))}>
          放大
        </button>
        <button className="button secondary" type="button" onClick={() => setZoom(1)}>
          适应
        </button>
        <button className="button secondary" type="button" onClick={() => setRotation((current) => current + 90)}>
          旋转
        </button>
      </div>
      <div className="preview-canvas">
        {isPdf ? (
          <iframe title="发票 PDF 原件" src={downloadUrl} style={{ transform: `scale(${zoom}) rotate(${rotation}deg)` }} />
        ) : (
          <img
            alt={document.original_filename}
            src={downloadUrl}
            style={{ transform: `scale(${zoom}) rotate(${rotation}deg)` }}
          />
        )}
      </div>
      <dl className="document-meta">
        <div>
          <dt>类型</dt>
          <dd>{document.file_ext.toUpperCase()}</dd>
        </div>
        <div>
          <dt>大小</dt>
          <dd>{formatBytes(document.file_size)}</dd>
        </div>
        <div>
          <dt>SHA256</dt>
          <dd>{document.sha256.slice(0, 12)}</dd>
        </div>
      </dl>
    </section>
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
