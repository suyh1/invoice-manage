import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { Archive, Folder, FolderLock, FolderPlus, Pencil, RotateCcw, Users } from "lucide-react";

import { useAuth } from "../auth/AuthContext";
import { ProjectEditorDialog, type ProjectDialogAction } from "../components/ProjectEditorDialog";
import { ApiError, apiGet, apiPatch, apiPost } from "../lib/api";
import { projectCreationModes } from "../lib/permissions";
import { groupProjects, type ProjectSummary } from "../lib/projects";

export function ProjectManagementPage() {
  const auth = useAuth();
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [pageError, setPageError] = useState<string | null>(null);
  const [dialogError, setDialogError] = useState<string | null>(null);
  const [dialogAction, setDialogAction] = useState<ProjectDialogAction | null>(null);
  const [busy, setBusy] = useState(false);
  const grouped = useMemo(() => groupProjects(projects), [projects]);
  const creationModes = projectCreationModes(auth.user?.role ?? "user");

  const loadProjects = useCallback(async () => {
    setLoading(true);
    setPageError(null);
    try {
      setProjects(await apiGet<ProjectSummary[]>("/api/v1/projects?include_archived=true"));
    } catch (error) {
      setPageError(projectError(error));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadProjects();
  }, [loadProjects]);

  async function submitProject(payload: { name: string; description: string | null; visibility?: "private" | "shared" }) {
    if (!dialogAction) return;
    setBusy(true);
    setDialogError(null);
    try {
      if (dialogAction.mode === "create") {
        await apiPost<ProjectSummary>("/api/v1/projects", payload);
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
      setBusy(false);
    }
  }

  async function changeArchiveState(project: ProjectSummary) {
    setBusy(true);
    setPageError(null);
    try {
      const action = project.status === "archived" ? "restore" : "archive";
      await apiPost<ProjectSummary>(`/api/v1/projects/${project.id}/${action}`);
      await loadProjects();
    } catch (error) {
      setPageError(projectError(error));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="management-page project-management-page">
      <div className="management-toolbar">
        <div>
          <span className="section-label">发票组织范围</span>
          <h2>项目管理</h2>
          <p>按共享项目或个人私有项目组织上传、校对和导出。</p>
        </div>
        <button
          className="button primary"
          onClick={() => {
            setDialogError(null);
            setDialogAction({ mode: "create" });
          }}
          type="button"
        >
          <FolderPlus aria-hidden="true" size={17} />
          创建项目
        </button>
      </div>

      {pageError ? (
        <div className="inline-message error management-page-message" role="alert">
          {pageError}
          <button className="button secondary" onClick={() => void loadProjects()} type="button">
            重新加载
          </button>
        </div>
      ) : null}

      {loading ? (
        <div className="management-loading">正在加载项目...</div>
      ) : (
        <div className="project-groups">
          <ProjectGroup
            description="未指定项目的发票默认进入这里。"
            icon={<Folder aria-hidden="true" size={19} />}
            projects={grouped.system}
            title="系统项目"
            onArchive={changeArchiveState}
            onEdit={(project) => setDialogAction({ mode: "edit", project })}
          />
          <ProjectGroup
            description="团队成员按权限共同使用。"
            icon={<Users aria-hidden="true" size={19} />}
            projects={grouped.shared}
            title="共享项目"
            onArchive={changeArchiveState}
            onEdit={(project) => setDialogAction({ mode: "edit", project })}
          />
          <ProjectGroup
            description="仅创建者和财务、管理员可见。"
            icon={<FolderLock aria-hidden="true" size={19} />}
            projects={grouped.private}
            title="私有项目"
            onArchive={changeArchiveState}
            onEdit={(project) => setDialogAction({ mode: "edit", project })}
          />
          <ProjectGroup
            description="保留历史发票和导出记录，不再接收新发票。"
            icon={<Archive aria-hidden="true" size={19} />}
            projects={grouped.archived}
            title="已归档"
            onArchive={changeArchiveState}
            onEdit={(project) => setDialogAction({ mode: "edit", project })}
          />
        </div>
      )}

      {dialogAction ? (
        <ProjectEditorDialog
          action={dialogAction}
          busy={busy}
          creationModes={creationModes}
          errorMessage={dialogError}
          onClose={() => setDialogAction(null)}
          onSubmit={submitProject}
        />
      ) : null}
    </section>
  );
}

function ProjectGroup({
  description,
  icon,
  projects,
  title,
  onArchive,
  onEdit,
}: {
  description: string;
  icon: ReactNode;
  projects: ProjectSummary[];
  title: string;
  onArchive: (project: ProjectSummary) => Promise<void>;
  onEdit: (project: ProjectSummary) => void;
}) {
  return (
    <section className="project-group">
      <div className="project-group-heading">
        <span className="project-group-icon">{icon}</span>
        <div>
          <h3>{title}</h3>
          <p>{description}</p>
        </div>
        <span className="status-token neutral">{projects.length}</span>
      </div>
      {projects.length === 0 ? (
        <p className="project-group-empty">暂无项目。</p>
      ) : (
        <div className="management-table-wrap">
          <table className="management-table project-table">
            <thead>
              <tr>
                <th>项目</th>
                <th>类型</th>
                <th>说明</th>
                <th>状态</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {projects.map((project) => (
                <tr key={project.id}>
                  <td>
                    <strong>{project.name}</strong>
                    {project.system_key ? <span>默认分类</span> : null}
                  </td>
                  <td>{project.visibility === "system" ? "系统" : project.visibility === "shared" ? "共享" : "私有"}</td>
                  <td>{project.description || "未填写"}</td>
                  <td>
                    <span className={`status-token ${project.status === "active" ? "success" : "neutral"}`}>
                      {project.status === "active" ? "使用中" : "已归档"}
                    </span>
                  </td>
                  <td>
                    {project.can_manage ? (
                      <div className="row-actions">
                        {project.status === "active" ? (
                          <button className="button secondary" onClick={() => onEdit(project)} type="button">
                            <Pencil aria-hidden="true" size={16} />
                            编辑
                          </button>
                        ) : null}
                        <button className="button secondary" onClick={() => void onArchive(project)} type="button">
                          {project.status === "archived" ? (
                            <RotateCcw aria-hidden="true" size={16} />
                          ) : (
                            <Archive aria-hidden="true" size={16} />
                          )}
                          {project.status === "archived" ? "恢复" : "归档"}
                        </button>
                      </div>
                    ) : (
                      <span className="management-muted">系统维护</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function projectError(error: unknown): string {
  if (!(error instanceof ApiError)) {
    return "暂时无法连接系统，请稍后重试。";
  }
  const messages: Record<string, string> = {
    PROJECT_FORBIDDEN: "你没有权限管理该项目。",
    PROJECT_NAME_EXISTS: "同一范围内已存在同名项目。",
    PROJECT_NOT_FOUND: "项目不存在或已被移除。",
    PROJECT_SYSTEM_IMMUTABLE: "系统项目不可编辑或归档。",
  };
  return messages[error.code] ?? "暂时无法完成项目操作，请稍后重试。";
}
