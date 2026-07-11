// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ProjectFileTable, type ProjectFileSummary } from "../components/ProjectFileTable";

const file: ProjectFileSummary = {
  content_type: "application/pdf",
  created_at: "2026-07-11T12:00:00Z",
  document_kind: "project_file",
  file_ext: "pdf",
  file_size: 1536,
  id: "file-1",
  original_filename: "出租车小票.pdf",
  project: { id: "project-1", name: "车辆项目" },
  sha256: "a".repeat(64),
  uploaded_by_user: { display_name: "苏钰溪", email: "user@example.com", id: "user-1" },
};

describe("ProjectFileTable", () => {
  afterEach(cleanup);

  it("shows project file metadata and download action", () => {
    render(<ProjectFileTable busyId={null} files={[file]} onDelete={vi.fn()} />);

    expect(screen.getByText("出租车小票.pdf")).toBeTruthy();
    expect(screen.getByText("PDF")).toBeTruthy();
    expect(screen.getByText("1.5 KB")).toBeTruthy();
    expect(screen.getByText("苏钰溪")).toBeTruthy();
    expect(screen.getByRole("link", { name: "下载 出租车小票.pdf" }).getAttribute("href")).toBe("/api/v1/documents/file-1/download");
  });

  it("requires an inline second click before deleting", () => {
    const onDelete = vi.fn();
    render(<ProjectFileTable busyId={null} files={[file]} onDelete={onDelete} />);

    fireEvent.click(screen.getByRole("button", { name: "删除 出租车小票.pdf" }));
    expect(onDelete).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "确认删除 出租车小票.pdf" }));
    expect(onDelete).toHaveBeenCalledWith("file-1");
  });

  it("shows a useful empty state", () => {
    render(<ProjectFileTable busyId={null} files={[]} onDelete={vi.fn()} />);
    expect(screen.getByText("当前项目还没有普通文件")).toBeTruthy();
  });
});
