import { useState } from "react";
import { Download, ExternalLink, Maximize2, RotateCw, ZoomIn, ZoomOut } from "lucide-react";

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

  const previewUrl = `/api/v1/documents/${document.id}/preview`;
  const downloadUrl = `/api/v1/documents/${document.id}/download`;
  const isPdf = document.file_ext.toLowerCase() === "pdf";

  return (
    <section className="surface-panel invoice-preview">
      <div className="panel-heading">
        <div>
          <span className="section-label">原件预览</span>
          <h2>{document.original_filename}</h2>
        </div>
        <div className="preview-heading-actions">
          <a aria-label="在新窗口打开原件" className="icon-button" href={previewUrl} rel="noreferrer" target="_blank" title="在新窗口打开">
            <ExternalLink aria-hidden="true" size={17} />
          </a>
          <a aria-label="下载原件" className="icon-button" href={downloadUrl} title="下载原件">
            <Download aria-hidden="true" size={17} />
          </a>
        </div>
      </div>

      {!isPdf ? (
        <div className="preview-toolbar" aria-label="图片预览工具">
          <button aria-label="缩小" className="icon-button" onClick={() => setZoom((current) => Math.max(0.5, current - 0.1))} title="缩小" type="button">
            <ZoomOut aria-hidden="true" size={17} />
          </button>
          <button aria-label="放大" className="icon-button" onClick={() => setZoom((current) => Math.min(2, current + 0.1))} title="放大" type="button">
            <ZoomIn aria-hidden="true" size={17} />
          </button>
          <button aria-label="适应窗口" className="icon-button" onClick={() => setZoom(1)} title="适应窗口" type="button">
            <Maximize2 aria-hidden="true" size={17} />
          </button>
          <button aria-label="顺时针旋转" className="icon-button" onClick={() => setRotation((current) => (current + 90) % 360)} title="顺时针旋转" type="button">
            <RotateCw aria-hidden="true" size={17} />
          </button>
          <span>{Math.round(zoom * 100)}%</span>
        </div>
      ) : null}

      <div className={`preview-canvas ${isPdf ? "pdf-preview" : "image-preview"}`}>
        {isPdf ? (
          <iframe title="发票 PDF 原件" src={previewUrl} />
        ) : (
          <img
            alt={document.original_filename}
            src={previewUrl}
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
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}
