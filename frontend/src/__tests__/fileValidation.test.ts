import { describe, expect, it } from "vitest";

import { estimateBase64Size, validateUploadCandidate } from "../lib/fileValidation";

describe("fileValidation", () => {
  it("accepts supported PNG and PDF files within provider limits", async () => {
    const png = new File([makePngBytes(120, 80)], "invoice.png", { type: "image/png" });
    const pdf = new File([new Uint8Array([0x25, 0x50, 0x44, 0x46, 0x2d])], "invoice.pdf", {
      type: "application/pdf",
    });

    await expect(validateUploadCandidate(png)).resolves.toMatchObject({ accepted: true });
    await expect(validateUploadCandidate(pdf)).resolves.toMatchObject({ accepted: true });
  });

  it("blocks GIF and unsupported file types before upload", async () => {
    const gif = new File([new Uint8Array([0x47, 0x49, 0x46])], "invoice.gif", { type: "image/gif" });
    const text = new File(["hello"], "invoice.txt", { type: "text/plain" });

    await expect(validateUploadCandidate(gif)).resolves.toMatchObject({
      accepted: false,
      issues: [expect.objectContaining({ code: "OCR_GIF_NOT_SUPPORTED" })],
    });
    await expect(validateUploadCandidate(text)).resolves.toMatchObject({
      accepted: false,
      issues: [expect.objectContaining({ code: "OCR_UNSUPPORTED_FILE_TYPE" })],
    });
  });

  it("blocks files that likely exceed Tencent base64 payload limits", async () => {
    const oversized = new File([new Uint8Array(7_864_321)], "large.jpg", { type: "image/jpeg" });

    expect(estimateBase64Size(7_864_321)).toBeGreaterThan(10 * 1024 * 1024);
    await expect(validateUploadCandidate(oversized)).resolves.toMatchObject({
      accepted: false,
      issues: [expect.objectContaining({ code: "OCR_FILE_TOO_LARGE" })],
    });
  });

  it("blocks images outside the provider dimension range", async () => {
    const tooSmall = new File([makePngBytes(19, 120)], "small.png", { type: "image/png" });
    const tooWide = new File([makePngBytes(10_001, 120)], "wide.png", { type: "image/png" });

    await expect(validateUploadCandidate(tooSmall)).resolves.toMatchObject({
      accepted: false,
      issues: [expect.objectContaining({ code: "OCR_INVALID_IMAGE_SIZE" })],
    });
    await expect(validateUploadCandidate(tooWide)).resolves.toMatchObject({
      accepted: false,
      issues: [expect.objectContaining({ code: "OCR_INVALID_IMAGE_SIZE" })],
    });
  });
});

function makePngBytes(width: number, height: number) {
  const bytes = new Uint8Array(33);
  bytes.set([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a], 0);
  bytes.set([0x00, 0x00, 0x00, 0x0d], 8);
  bytes.set([0x49, 0x48, 0x44, 0x52], 12);
  bytes[16] = (width >>> 24) & 0xff;
  bytes[17] = (width >>> 16) & 0xff;
  bytes[18] = (width >>> 8) & 0xff;
  bytes[19] = width & 0xff;
  bytes[20] = (height >>> 24) & 0xff;
  bytes[21] = (height >>> 16) & 0xff;
  bytes[22] = (height >>> 8) & 0xff;
  bytes[23] = height & 0xff;
  return bytes;
}
