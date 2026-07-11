import { ChangeEvent, DragEvent, useId, useState } from "react";

type UploadMode = "invoice" | "project_file";

export function UploadDropzone({ disabled = false, mode = "invoice", onFiles }: { disabled?: boolean; mode?: UploadMode; onFiles: (files: File[]) => void }) {
  const inputId = useId();
  const [dragging, setDragging] = useState(false);

  function handleDrop(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault();
    setDragging(false);
    if (disabled) {
      return;
    }
    onFiles(Array.from(event.dataTransfer.files));
  }

  function handleChange(event: ChangeEvent<HTMLInputElement>) {
    onFiles(Array.from(event.currentTarget.files ?? []));
    event.currentTarget.value = "";
  }

  return (
    <label
      className={`upload-dropzone ${dragging ? "dragging" : ""} ${disabled ? "disabled" : ""}`}
      htmlFor={inputId}
      onDragEnter={(event) => {
        event.preventDefault();
        setDragging(true);
      }}
      onDragOver={(event) => event.preventDefault()}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
    >
      <input
        accept={mode === "project_file"
          ? ".png,.jpg,.jpeg,.pdf,.docx,.xlsx,image/png,image/jpeg,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
          : ".png,.jpg,.jpeg,.pdf,image/png,image/jpeg,application/pdf"}
        className="visually-hidden"
        disabled={disabled}
        id={inputId}
        multiple
        onChange={handleChange}
        type="file"
      />
      <span className="section-label">{mode === "project_file" ? "项目文件" : "上传识别"}</span>
      <strong>{mode === "project_file" ? "拖入项目资料或选择文件" : "拖入发票原件或选择文件"}</strong>
      <p>{mode === "project_file"
        ? "支持 PDF、PNG、JPG、JPEG、DOCX、XLSX，单文件最大 50MB。"
        : "支持 PNG、JPG、JPEG、PDF。系统会在上传前检查类型、大小和图片尺寸。"}</p>
      <span className="button secondary" aria-hidden="true">
        选择文件
      </span>
    </label>
  );
}
