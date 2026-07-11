import { useEffect, useMemo, useState } from "react";

import { OcrQuotaStatus } from "../components/OcrQuotaStatus";
import { ProjectFilter } from "../components/ProjectFilter";
import { UploadDropzone } from "../components/UploadDropzone";
import { UploadQueue, type UploadQueueItem } from "../components/UploadQueue";
import { ApiError, apiGet, apiPost, apiPostForm } from "../lib/api";
import { validateUploadCandidate } from "../lib/fileValidation";
import type { ProjectSummary } from "../lib/projects";

type DocumentUploadResponse = {
  document_id: string;
  ocr_job_id: string | null;
  status: string;
  sha256: string;
};

type OcrJobResponse = {
  id: string;
  status: string;
  provider_error_code?: string | null;
  request_id?: string | null;
};

export function UploadPage() {
  const [items, setItems] = useState<UploadQueueItem[]>([]);
  const [scene, setScene] = useState("");
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [projectId, setProjectId] = useState("");
  const [autoOcr, setAutoOcr] = useState(true);

  const readyCount = useMemo(() => items.filter((item) => item.status === "ready").length, [items]);
  const busy = items.some((item) => item.status === "uploading" || item.status === "recognizing" || item.status === "ocr_queued");

  useEffect(() => {
    let cancelled = false;
    apiGet<ProjectSummary[]>("/api/v1/projects")
      .then((data) => {
        if (cancelled) return;
        setProjects(data);
        setProjectId((current) => current || data.find((project) => project.system_key === "uncategorized")?.id || "");
      })
      .catch(() => {
        if (!cancelled) setProjects([]);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  function addFiles(files: File[]) {
    const pendingItems: UploadQueueItem[] = files.map((file) => ({
      file,
      id: createQueueId(),
      status: "validating",
    }));
    setItems((current) => [...pendingItems, ...current]);

    pendingItems.forEach((item) => {
      validateUploadCandidate(item.file)
        .then((validation) => {
          updateItem(item.id, {
            status: validation.accepted ? "ready" : "blocked",
            validation,
          });
        })
        .catch(() => {
          updateItem(item.id, {
            error: "文件校验失败，请重新选择。",
            status: "blocked",
          });
        });
    });
  }

  function removeItem(id: string) {
    setItems((current) => current.filter((item) => item.id !== id));
  }

  async function uploadAllReady() {
    const uploadItems = items.filter((item) => item.status === "ready");
    for (const item of uploadItems) {
      await uploadItem(item);
    }
  }

  async function uploadReadyById(id: string) {
    const item = items.find((candidate) => candidate.id === id);
    if (item) {
      await uploadItem(item);
    }
  }

  async function retryItem(id: string) {
    const item = items.find((candidate) => candidate.id === id);
    if (!item) {
      return;
    }
    if (!item.ocrJobId) {
      await uploadItem(item);
      return;
    }

    updateItem(item.id, { error: undefined, status: "ocr_queued" });
    try {
      await apiPost(`/api/v1/ocr-jobs/${item.ocrJobId}/retry`);
      void pollOcrJob(item.id, item.ocrJobId);
    } catch (error) {
      updateItem(item.id, {
        error: apiErrorMessage(error, "OCR 重试请求失败。"),
        status: "failed",
      });
    }
  }

  async function uploadItem(item: UploadQueueItem) {
    if (item.status !== "ready" && item.status !== "failed") {
      return;
    }
    updateItem(item.id, { error: undefined, status: "uploading" });

    const body = new FormData();
    body.append("file", item.file);
    body.append("auto_ocr", String(autoOcr));
    body.append("idempotency_key", item.id);
    if (scene.trim()) {
      body.append("scene", scene.trim());
    }
    if (projectId) {
      body.append("project_id", projectId);
    }

    try {
      const uploaded = await apiPostForm<DocumentUploadResponse>("/api/v1/documents", body);
      const nextStatus = uploaded.ocr_job_id ? "ocr_queued" : "uploaded";
      updateItem(item.id, {
        documentId: uploaded.document_id,
        error: undefined,
        ocrJobId: uploaded.ocr_job_id,
        status: nextStatus,
      });
      if (uploaded.ocr_job_id) {
        void pollOcrJob(item.id, uploaded.ocr_job_id);
      }
    } catch (error) {
      updateItem(item.id, {
        error: apiErrorMessage(error, "上传失败。"),
        status: "failed",
      });
    }
  }

  async function pollOcrJob(itemId: string, jobId: string) {
    updateItem(itemId, { status: "recognizing" });
    for (let attempt = 0; attempt < 24; attempt += 1) {
      await delay(attempt === 0 ? 1000 : 2500);
      try {
        const job = await apiGet<OcrJobResponse>(`/api/v1/ocr-jobs/${jobId}`);
        const nextStatus = mapOcrJobStatus(job.status);
        updateItem(itemId, {
          error: job.provider_error_code ? `OCR 运营商错误：${job.provider_error_code}` : undefined,
          status: nextStatus,
        });
        if (nextStatus === "completed" || nextStatus === "failed") {
          return;
        }
      } catch (error) {
        updateItem(itemId, {
          error: apiErrorMessage(error, "OCR 状态查询失败。"),
          status: "failed",
        });
        return;
      }
    }
    updateItem(itemId, {
      error: "OCR 识别仍在进行，请稍后在发票库查看结果。",
      status: "failed",
    });
  }

  function updateItem(id: string, patch: Partial<UploadQueueItem>) {
    setItems((current) => current.map((item) => (item.id === id ? { ...item, ...patch } : item)));
  }

  return (
    <div className="page-stack">
      <section className="dashboard-band upload-band">
        <div>
          <span className="section-label">上传识别</span>
          <h2>先检查文件，再创建 OCR 作业</h2>
          <p>上传前会拦截不支持的类型、GIF、Base64 后超过 10MB 的文件，以及超出 OCR 尺寸限制的图片。</p>
        </div>
        <OcrQuotaStatus compact />
      </section>

      <section className="upload-flow" aria-label="上传识别流程">
        <ol className="workflow-steps">
          <li className="active"><span>1</span>选择文件</li>
          <li className={items.length ? "active" : ""}><span>2</span>确认归属</li>
          <li className={busy || items.some((item) => ["uploaded", "ocr_queued", "recognizing", "completed", "failed"].includes(item.status)) ? "active" : ""}><span>3</span>上传与识别</li>
        </ol>

        <div className="upload-stage">
          <UploadDropzone disabled={busy} onFiles={addFiles} />
          {items.length ? (
            <div className="upload-batch-settings" aria-label="上传设置">
              <ProjectFilter disabled={busy || projects.length === 0} includeAll={false} label="归属项目" onChange={setProjectId} projects={projects} value={projectId} />
              <label>业务场景<select value={scene} onChange={(event) => setScene(event.currentTarget.value)}><option value="">不指定</option><option value="travel">差旅</option><option value="purchase">采购</option><option value="office">办公</option><option value="meal">餐饮</option><option value="transport">交通</option></select></label>
              <label className="check-row"><input checked={autoOcr} onChange={(event) => setAutoOcr(event.currentTarget.checked)} type="checkbox" /><span>上传后自动识别</span></label>
              <button className="button primary" disabled={readyCount === 0 || busy} onClick={uploadAllReady} type="button">{readyCount ? `上传 ${readyCount} 个文件` : "等待文件校验"}</button>
            </div>
          ) : null}
        </div>
        {items.length ? <UploadQueue items={items} onRemove={removeItem} onRetry={retryItem} onUploadReady={uploadReadyById} /> : null}
      </section>
    </div>
  );
}

function mapOcrJobStatus(status: string): UploadQueueItem["status"] {
  if (status === "completed") {
    return "completed";
  }
  if (status === "failed_final" || status === "cancelled" || status === "failed") {
    return "failed";
  }
  if (status === "queued" || status === "retry_scheduled") {
    return "ocr_queued";
  }
  return "recognizing";
}

function createQueueId() {
  return typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function apiErrorMessage(error: unknown, fallback: string) {
  return error instanceof ApiError ? error.message : fallback;
}

function delay(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}
