import { ChangeEvent, DragEvent, useId, useState } from "react";

export function UploadDropzone({ disabled = false, onFiles }: { disabled?: boolean; onFiles: (files: File[]) => void }) {
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
        accept=".png,.jpg,.jpeg,.pdf,image/png,image/jpeg,application/pdf"
        className="visually-hidden"
        disabled={disabled}
        id={inputId}
        multiple
        onChange={handleChange}
        type="file"
      />
      <span className="section-label">上传识别</span>
      <strong>拖入发票原件或选择文件</strong>
      <p>支持 PNG、JPG、JPEG、PDF。系统会在上传前检查类型、大小和图片尺寸。</p>
      <span className="button secondary" aria-hidden="true">
        选择文件
      </span>
    </label>
  );
}
