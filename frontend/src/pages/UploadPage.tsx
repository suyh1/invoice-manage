import { useEffect, useMemo, useState } from "react";

import { OcrQuotaStatus } from "../components/OcrQuotaStatus";
import { ProjectFilter } from "../components/ProjectFilter";
import { UploadDropzone } from "../components/UploadDropzone";
import { UploadQueue, type UploadQueueItem } from "../components/UploadQueue";
import { ApiError, apiGet, apiPost, apiPostForm } from "../lib/api";
import { EXPENSE_SCENE_OPTIONS } from "../lib/expenseScenes";
import { validateProjectFileCandidate, validateUploadCandidate } from "../lib/fileValidation";
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

type UploadMode = "invoice" | "project_file";

export function UploadPage() {
  const [items, setItems] = useState<UploadQueueItem[]>([]);
  const [scene, setScene] = useState("");
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [projectId, setProjectId] = useState("");
  const [autoOcr, setAutoOcr] = useState(true);
  const [uploadMode, setUploadMode] = useState<UploadMode>("invoice");

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

    pendingItems.forEach((item) => validateQueueItem(item, uploadMode));
  }

  function changeUploadMode(mode: UploadMode) {
    if (mode === uploadMode || busy) return;
    setUploadMode(mode);
    setItems((current) => current.map((item) => ({ ...item, error: undefined, status: "validating" })));
    items.forEach((item) => validateQueueItem(item, mode));
  }

  function validateQueueItem(item: UploadQueueItem, mode: UploadMode) {
    const validator = mode === "project_file" ? validateProjectFileCandidate : validateUploadCandidate;
    validator(item.file)
      .then((validation) => {
        updateItem(item.id, { status: validation.accepted ? "ready" : "blocked", validation });
      })
      .catch(() => {
        updateItem(item.id, { error: "文件校验失败，请重新选择。", status: "blocked" });
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
    body.append("document_kind", uploadMode);
    body.append("auto_ocr", String(uploadMode === "invoice" && autoOcr));
    body.append("idempotency_key", item.id);
    if (uploadMode === "invoice" && scene.trim()) {
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
    <div className="page-stack upload-editorial">
      <section className="dashboard-band upload-band editorial-page-heading">
        <div>
          <span className="section-label">INGEST / 文件入库</span>
          <h2>{uploadMode === "project_file" ? "把项目资料放到正确的位置。" : <>把原件交给系统，<em>数据从这里开始。</em></>}</h2>
          <p>{uploadMode === "project_file"
            ? "项目文件直接归档，不创建 OCR 作业或发票数据。"
            : "上传前会拦截不支持的类型、GIF、Base64 后超过 10MB 的文件，以及超出 OCR 尺寸限制的图片。"}</p>
        </div>
        {uploadMode === "invoice" ? <OcrQuotaStatus compact /> : null}
      </section>

      <section className="upload-flow" aria-label="上传识别流程">
        <div className="upload-mode-switch" role="group" aria-label="上传类型">
          <button className={uploadMode === "invoice" ? "active" : ""} disabled={busy} onClick={() => changeUploadMode("invoice")} type="button">发票识别</button>
          <button className={uploadMode === "project_file" ? "active" : ""} disabled={busy} onClick={() => changeUploadMode("project_file")} type="button">项目文件</button>
        </div>
        <ol className="workflow-steps">
          <li className="active"><span>01</span>选择文件</li>
          <li className={items.length ? "active" : ""}><span>02</span>确认归属</li>
          <li className={busy || items.some((item) => ["uploaded", "ocr_queued", "recognizing", "completed", "failed"].includes(item.status)) ? "active" : ""}><span>03</span>{uploadMode === "project_file" ? "上传与归档" : "上传与识别"}</li>
        </ol>

        <div className="upload-stage">
          <UploadDropzone disabled={busy} mode={uploadMode} onFiles={addFiles} />
          {items.length ? (
            <div className="upload-batch-settings" aria-label="上传设置">
              <ProjectFilter disabled={busy || projects.length === 0} includeAll={false} label="归属项目" onChange={setProjectId} projects={projects} value={projectId} />
              {uploadMode === "invoice" ? <label>
                业务场景
                <select value={scene} onChange={(event) => setScene(event.currentTarget.value)}>
                  <option value="">不指定</option>
                  {EXPENSE_SCENE_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
                </select>
              </label> : null}
              {uploadMode === "invoice" ? <label className="check-row"><input checked={autoOcr} onChange={(event) => setAutoOcr(event.currentTarget.checked)} type="checkbox" /><span>上传后自动识别</span></label> : null}
              <button className="button primary" disabled={readyCount === 0 || busy} onClick={uploadAllReady} type="button">{readyCount ? `上传 ${readyCount} 个文件` : "等待文件校验"}</button>
            </div>
          ) : null}
        </div>
        {items.length ? <UploadQueue items={items} mode={uploadMode} onRemove={removeItem} onRetry={retryItem} onUploadReady={uploadReadyById} /> : null}
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
