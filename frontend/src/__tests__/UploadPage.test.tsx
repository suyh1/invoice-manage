// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { apiGet, apiPostForm } from "../lib/api";
import { UploadPage } from "../pages/UploadPage";

vi.mock("../lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../lib/api")>();
  return { ...actual, apiGet: vi.fn(), apiPost: vi.fn(), apiPostForm: vi.fn() };
});

const project = {
  can_manage: true,
  created_by: "user-1",
  id: "project-1",
  name: "车辆项目",
  status: "active",
  system_key: null,
  visibility: "private",
};

describe("UploadPage project file mode", () => {
  beforeEach(() => {
    vi.mocked(apiGet).mockResolvedValue([project]);
    vi.mocked(apiPostForm).mockResolvedValue({
      document_id: "document-1",
      document_kind: "project_file",
      ocr_job_id: null,
      sha256: "hash",
      status: "uploaded",
    });
  });

  afterEach(cleanup);

  it("uploads ordinary project files without OCR-only settings", async () => {
    const { container } = render(<UploadPage />);
    await waitFor(() => expect(apiGet).toHaveBeenCalledWith("/api/v1/projects"));

    fireEvent.click(screen.getByRole("button", { name: "项目文件" }));
    const fileInput = container.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File(["package"], "vehicle.docx", {
      type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    });
    fireEvent.change(fileInput, { target: { files: [file] } });

    const uploadButton = await screen.findByRole("button", { name: "上传 1 个文件" });
    fireEvent.change(screen.getByRole("combobox", { name: "归属项目" }), { target: { value: "project-1" } });
    expect(screen.queryByText("业务场景")).toBeNull();
    expect(screen.queryByText("上传后自动识别")).toBeNull();
    expect(fileInput.accept).toContain(".docx");

    fireEvent.click(uploadButton);
    await waitFor(() => expect(apiPostForm).toHaveBeenCalledTimes(1));
    const body = vi.mocked(apiPostForm).mock.calls[0]?.[1] as FormData;
    expect(body.get("document_kind")).toBe("project_file");
    expect(body.get("auto_ocr")).toBe("false");
    expect(body.get("project_id")).toBe("project-1");
    expect(body.has("scene")).toBe(false);
  });
});
