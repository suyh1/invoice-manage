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

  it("previews PDF files in an accessible dialog", () => {
    render(<ProjectFileTable busyId={null} files={[file]} onDelete={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: "预览 出租车小票.pdf" }));

    expect(screen.getByRole("dialog", { name: "预览 出租车小票.pdf" })).toBeTruthy();
    expect(screen.getByTitle("项目文件 PDF 预览").getAttribute("src")).toBe("/api/v1/documents/file-1/preview");
    expect(screen.getByRole("link", { name: "在新窗口打开 出租车小票.pdf" }).getAttribute("href")).toBe("/api/v1/documents/file-1/preview");
    fireEvent.click(screen.getByRole("button", { name: "关闭预览" }));
    expect(screen.queryByRole("dialog", { name: "预览 出租车小票.pdf" })).toBeNull();
  });

  it("opens Office files in a new window for preview", () => {
    const officeFile: ProjectFileSummary = {
      ...file,
      content_type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      file_ext: "docx",
      id: "file-2",
      original_filename: "车辆说明.docx",
    };
    render(<ProjectFileTable busyId={null} files={[officeFile]} onDelete={vi.fn()} />);

    const preview = screen.getByRole("link", { name: "预览 车辆说明.docx" });
    expect(preview.getAttribute("href")).toBe("/api/v1/documents/file-2/preview");
    expect(preview.getAttribute("target")).toBe("_blank");
  });

  it("shows a useful empty state", () => {
    render(<ProjectFileTable busyId={null} files={[]} onDelete={vi.fn()} />);
    expect(screen.getByText("当前项目还没有普通文件")).toBeTruthy();
  });
});
