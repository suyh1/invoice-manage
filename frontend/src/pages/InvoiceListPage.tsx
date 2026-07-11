import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { Archive, Folder, FolderLock, FolderPlus, Pencil, RotateCcw, Users } from "lucide-react";

import { useAuth } from "../auth/AuthContext";
import { InvoiceTable, type InvoiceSummary } from "../components/InvoiceTable";
import { ProjectEditorDialog, type ProjectDialogAction } from "../components/ProjectEditorDialog";
import { ApiError, apiGet, apiPatch, apiPost } from "../lib/api";
import { projectCreationModes } from "../lib/permissions";
import { groupProjects, type ProjectSummary } from "../lib/projects";

type InvoiceListResponse = {
  items: InvoiceSummary[];
  total: number;
};

type InvoiceFilters = {
  duplicate: string;
  file_type: string;
  q: string;
  project_id: string;
  scene: string;
  status: string;
};

const emptyFilters: InvoiceFilters = {
  duplicate: "",
  file_type: "",
  q: "",
  project_id: "",
  scene: "",
  status: "",
};

const savedViews: Array<{ filters: Partial<InvoiceFilters>; label: string }> = [
  { filters: {}, label: "全部" },
  { filters: { status: "needs_review" }, label: "待校对" },
  { filters: { duplicate: "true" }, label: "疑似重复" },
  { filters: { status: "confirmed" }, label: "已确认" },
  { filters: { file_type: "pdf" }, label: "PDF" },
];

export function InvoiceListPage() {
  const auth = useAuth();
  const [filters, setFilters] = useState<InvoiceFilters>(emptyFilters);
  const [invoices, setInvoices] = useState<InvoiceSummary[]>([]);
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [message, setMessage] = useState("");
  const [projectErrorMessage, setProjectErrorMessage] = useState<string | null>(null);
  const [dialogError, setDialogError] = useState<string | null>(null);
  const [dialogAction, setDialogAction] = useState<ProjectDialogAction | null>(null);
  const [busyProjectId, setBusyProjectId] = useState<string | null>(null);
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");

  const query = useMemo(() => buildQuery(filters), [filters]);
  const groupedProjects = useMemo(() => groupProjects(projects), [projects]);
  const selectedProject = projects.find((project) => project.id === filters.project_id) ?? null;
  const creationModes = projectCreationModes(auth.user?.role ?? "user");

  const loadProjects = useCallback(async () => {
    try {
      setProjects(await apiGet<ProjectSummary[]>("/api/v1/projects?include_archived=true"));
      setProjectErrorMessage(null);
    } catch (error) {
      setProjectErrorMessage(projectError(error));
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    setStatus("loading");
    apiGet<InvoiceListResponse>(`/api/v1/invoices${query}`)
      .then((data) => {
        if (!cancelled) {
          setInvoices(data.items);
          setStatus("ready");
          setMessage("");
        }
      })
      .catch((error) => {
        if (!cancelled) {
          setStatus("error");
          setMessage(error instanceof ApiError ? error.message : "无法加载发票列表。");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [query]);

  useEffect(() => {
    void loadProjects();
  }, [loadProjects]);

  function applySavedView(viewFilters: Partial<InvoiceFilters>) {
    setFilters((current) => ({ ...emptyFilters, project_id: current.project_id, ...viewFilters }));
  }

  async function submitProject(payload: { name: string; description: string | null; visibility?: "private" | "shared" }) {
    if (!dialogAction) return;
    setBusyProjectId(dialogAction.mode === "edit" ? dialogAction.project.id : "new");
    setDialogError(null);
    try {
      if (dialogAction.mode === "create") {
        const created = await apiPost<ProjectSummary>("/api/v1/projects", payload);
        setFilters((current) => ({ ...current, project_id: created.id }));
      } else {
        await apiPatch<ProjectSummary>(`/api/v1/projects/${dialogAction.project.id}`, {
          name: payload.name,
          description: payload.description,
        });
      }
      setDialogAction(null);
      await loadProjects();
    } catch (error) {
      setDialogError(projectError(error));
    } finally {
      setBusyProjectId(null);
    }
  }

  async function changeArchiveState(project: ProjectSummary) {
    setBusyProjectId(project.id);
    setProjectErrorMessage(null);
    try {
      const action = project.status === "archived" ? "restore" : "archive";
      await apiPost<ProjectSummary>(`/api/v1/projects/${project.id}/${action}`);
      if (project.id === filters.project_id && action === "archive") {
        setFilters((current) => ({ ...current, project_id: "" }));
      }
      await loadProjects();
    } catch (error) {
      setProjectErrorMessage(projectError(error));
    } finally {
      setBusyProjectId(null);
    }
  }

  return (
    <div className="invoice-workbench">
      <aside className="project-rail" aria-label="项目导航">
        <div className="project-rail-heading">
          <div>
            <span className="section-label">项目</span>
            <h2>发票范围</h2>
          </div>
          <button
            aria-label="创建项目"
            className="icon-button"
            onClick={() => {
              setDialogError(null);
              setDialogAction({ mode: "create" });
            }}
            title="创建项目"
            type="button"
          >
            <FolderPlus aria-hidden="true" size={18} />
          </button>
        </div>

        {projectErrorMessage ? <p className="project-rail-error">{projectErrorMessage}</p> : null}

        <button
          className={`project-rail-all ${filters.project_id === "" ? "active" : ""}`}
          onClick={() => setFilters((current) => ({ ...current, project_id: "" }))}
          type="button"
        >
          <Folder aria-hidden="true" size={17} />
          <span>全部发票</span>
        </button>

        <div className="project-rail-sections">
          <ProjectRailSection
            icon={<Folder aria-hidden="true" size={15} />}
            projects={groupedProjects.system}
            selectedId={filters.project_id}
            title="系统项目"
            onArchive={changeArchiveState}
            onEdit={(project) => setDialogAction({ mode: "edit", project })}
            onSelect={(projectId) => setFilters((current) => ({ ...current, project_id: projectId }))}
            busyProjectId={busyProjectId}
          />
          <ProjectRailSection
            icon={<Users aria-hidden="true" size={15} />}
            projects={groupedProjects.shared}
            selectedId={filters.project_id}
            title="共享项目"
            onArchive={changeArchiveState}
            onEdit={(project) => setDialogAction({ mode: "edit", project })}
            onSelect={(projectId) => setFilters((current) => ({ ...current, project_id: projectId }))}
            busyProjectId={busyProjectId}
          />
          <ProjectRailSection
            icon={<FolderLock aria-hidden="true" size={15} />}
            projects={groupedProjects.private}
            selectedId={filters.project_id}
            title="我的项目"
            onArchive={changeArchiveState}
            onEdit={(project) => setDialogAction({ mode: "edit", project })}
            onSelect={(projectId) => setFilters((current) => ({ ...current, project_id: projectId }))}
            busyProjectId={busyProjectId}
          />
          {groupedProjects.archived.length ? (
            <ProjectRailSection
              archived
              icon={<Archive aria-hidden="true" size={15} />}
              projects={groupedProjects.archived}
              selectedId={filters.project_id}
              title="已归档"
              onArchive={changeArchiveState}
              onEdit={(project) => setDialogAction({ mode: "edit", project })}
              onSelect={(projectId) => setFilters((current) => ({ ...current, project_id: projectId }))}
              busyProjectId={busyProjectId}
            />
          ) : null}
        </div>
      </aside>

      <div className="invoice-workbench-main">
        <header className="invoice-list-header">
          <div>
            <span className="section-label">发票工作台</span>
            <h2>{selectedProject?.name || "全部发票"}</h2>
            <p>{selectedProject?.description || "按项目组织、筛选并进入发票校对流程。"}</p>
          </div>
          <div className="saved-view-bar" aria-label="常用视图">
            {savedViews.map((view) => (
              <button className="button secondary" key={view.label} onClick={() => applySavedView(view.filters)} type="button">
                {view.label}
              </button>
            ))}
          </div>
        </header>

        <section className="surface-panel invoice-filters" aria-label="发票筛选">
          <label>
            搜索
            <input
              value={filters.q}
              onChange={(event) => setFilters({ ...filters, q: event.currentTarget.value })}
              placeholder="号码、代码、销售方、购买方"
            />
          </label>
          <label>
            状态
            <select value={filters.status} onChange={(event) => setFilters({ ...filters, status: event.currentTarget.value })}>
              <option value="">全部状态</option>
              <option value="needs_review">待校对</option>
              <option value="duplicate_suspected">疑似重复</option>
              <option value="confirmed">已确认</option>
              <option value="archived">已归档</option>
            </select>
          </label>
          <label>
            疑似重复
            <select value={filters.duplicate} onChange={(event) => setFilters({ ...filters, duplicate: event.currentTarget.value })}>
              <option value="">全部</option>
              <option value="true">仅疑似重复</option>
              <option value="false">排除疑似重复</option>
            </select>
          </label>
          <label>
            文件类型
            <select value={filters.file_type} onChange={(event) => setFilters({ ...filters, file_type: event.currentTarget.value })}>
              <option value="">全部类型</option>
              <option value="png">PNG</option>
              <option value="jpg">JPG</option>
              <option value="jpeg">JPEG</option>
              <option value="pdf">PDF</option>
            </select>
          </label>
          <label>
            场景
            <select value={filters.scene} onChange={(event) => setFilters({ ...filters, scene: event.currentTarget.value })}>
              <option value="">全部场景</option>
              <option value="travel">差旅</option>
              <option value="purchase">采购</option>
              <option value="office">办公</option>
              <option value="meal">餐饮</option>
              <option value="transport">交通</option>
            </select>
          </label>
        </section>

        <section className="surface-panel invoice-list-panel">
          <div className="panel-heading">
            <div>
              <span className="section-label">查询结果</span>
              <h2>{status === "loading" ? "加载中" : `${invoices.length} 张发票`}</h2>
            </div>
            {message ? <span className="status-token danger">{message}</span> : null}
          </div>
          <InvoiceTable invoices={invoices} />
        </section>
      </div>

      {dialogAction ? (
        <ProjectEditorDialog
          action={dialogAction}
          busy={busyProjectId !== null}
          creationModes={creationModes}
          errorMessage={dialogError}
          onClose={() => setDialogAction(null)}
          onSubmit={submitProject}
        />
      ) : null}
    </div>
  );
}

function ProjectRailSection({
  archived = false,
  busyProjectId,
  icon,
  projects,
  selectedId,
  title,
  onArchive,
  onEdit,
  onSelect,
}: {
  archived?: boolean;
  busyProjectId: string | null;
  icon: ReactNode;
  projects: ProjectSummary[];
  selectedId: string;
  title: string;
  onArchive: (project: ProjectSummary) => Promise<void>;
  onEdit: (project: ProjectSummary) => void;
  onSelect: (projectId: string) => void;
}) {
  if (!projects.length) return null;

  return (
    <section className="project-rail-section">
      <h3>
        {icon}
        {title}
      </h3>
      <div className="project-rail-list">
        {projects.map((project) => (
          <div className={`project-rail-row ${selectedId === project.id ? "active" : ""}`} key={project.id}>
            <button className="project-rail-select" onClick={() => onSelect(project.id)} type="button">
              <span>{project.name}</span>
            </button>
            {project.can_manage ? (
              <div className="project-rail-actions">
                {!archived ? (
                  <button aria-label={`编辑 ${project.name}`} onClick={() => onEdit(project)} title="编辑项目" type="button">
                    <Pencil aria-hidden="true" size={14} />
                  </button>
                ) : null}
                <button
                  aria-label={`${archived ? "恢复" : "归档"} ${project.name}`}
                  disabled={busyProjectId === project.id}
                  onClick={() => void onArchive(project)}
                  title={archived ? "恢复项目" : "归档项目"}
                  type="button"
                >
                  {archived ? <RotateCcw aria-hidden="true" size={14} /> : <Archive aria-hidden="true" size={14} />}
                </button>
              </div>
            ) : null}
          </div>
        ))}
      </div>
    </section>
  );
}

function buildQuery(filters: InvoiceFilters) {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value) params.set(key, value);
  });
  const query = params.toString();
  return query ? `?${query}` : "";
}

function projectError(error: unknown): string {
  if (!(error instanceof ApiError)) return "暂时无法连接系统，请稍后重试。";
  const messages: Record<string, string> = {
    PROJECT_FORBIDDEN: "你没有权限管理该项目。",
    PROJECT_NAME_EXISTS: "同一范围内已存在同名项目。",
    PROJECT_NOT_FOUND: "项目不存在或已被移除。",
    PROJECT_SYSTEM_IMMUTABLE: "系统项目不可编辑或归档。",
  };
  return messages[error.code] ?? "暂时无法完成项目操作，请稍后重试。";
}
