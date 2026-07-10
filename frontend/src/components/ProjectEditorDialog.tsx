import { useEffect, useRef, type FormEvent } from "react";
import { FolderPlus, Save, X } from "lucide-react";

import type { ProjectCreationMode } from "../lib/permissions";
import type { ProjectSummary } from "../lib/projects";

export type ProjectDialogAction = { mode: "create" } | { mode: "edit"; project: ProjectSummary };

type ProjectEditorDialogProps = {
  action: ProjectDialogAction;
  busy: boolean;
  creationModes: ProjectCreationMode[];
  errorMessage: string | null;
  onClose: () => void;
  onSubmit: (payload: { name: string; description: string | null; visibility?: ProjectCreationMode }) => Promise<void> | void;
};

export function ProjectEditorDialog({
  action,
  busy,
  creationModes,
  errorMessage,
  onClose,
  onSubmit,
}: ProjectEditorDialogProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const project = action.mode === "edit" ? action.project : null;

  useEffect(() => {
    dialogRef.current?.showModal();
    return () => dialogRef.current?.close();
  }, []);

  function closeDialog() {
    dialogRef.current?.close();
    onClose();
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    await onSubmit({
      name: String(data.get("name") ?? "").trim(),
      description: String(data.get("description") ?? "").trim() || null,
      visibility:
        action.mode === "create" ? (String(data.get("visibility")) as ProjectCreationMode) : undefined,
    });
  }

  return (
    <dialog className="management-dialog" onClose={onClose} ref={dialogRef}>
      <div className="management-dialog-heading">
        <div>
          <h2>{action.mode === "create" ? "创建项目" : `编辑 ${project?.name}`}</h2>
          <p>{action.mode === "create" ? "项目用于组织上传、校对和导出范围。" : "修改名称和项目说明。"}</p>
        </div>
        <button aria-label="关闭项目对话框" className="icon-button" onClick={closeDialog} title="关闭" type="button">
          <X aria-hidden="true" size={18} />
        </button>
      </div>

      {errorMessage ? (
        <p className="inline-message error management-dialog-message" role="alert">
          {errorMessage}
        </p>
      ) : null}

      <form className="management-form" onSubmit={handleSubmit}>
        <label htmlFor="managed-project-name">
          项目名称
          <input
            defaultValue={project?.name ?? ""}
            disabled={busy}
            id="managed-project-name"
            maxLength={120}
            name="name"
            required
          />
        </label>
        <label htmlFor="managed-project-description">
          项目说明
          <textarea
            defaultValue={project?.description ?? ""}
            disabled={busy}
            id="managed-project-description"
            maxLength={1000}
            name="description"
            placeholder="可选"
            rows={4}
          />
        </label>
        {action.mode === "create" ? (
          <label htmlFor="managed-project-visibility">
            项目类型
            <select defaultValue={creationModes.includes("shared") ? "shared" : "private"} disabled={busy} id="managed-project-visibility" name="visibility">
              {creationModes.includes("private") ? <option value="private">我的私有项目</option> : null}
              {creationModes.includes("shared") ? <option value="shared">共享项目</option> : null}
            </select>
          </label>
        ) : null}

        <div className="management-dialog-actions">
          <button className="button secondary" onClick={closeDialog} type="button">
            返回
          </button>
          <button className="button primary" disabled={busy} type="submit">
            {action.mode === "create" ? <FolderPlus aria-hidden="true" size={17} /> : <Save aria-hidden="true" size={17} />}
            {busy ? "正在保存..." : action.mode === "create" ? "创建项目" : "保存项目"}
          </button>
        </div>
      </form>
    </dialog>
  );
}
