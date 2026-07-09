export type UploadValidationCode =
  | "OCR_UNSUPPORTED_FILE_TYPE"
  | "OCR_GIF_NOT_SUPPORTED"
  | "OCR_FILE_TOO_LARGE"
  | "OCR_INVALID_IMAGE_SIZE";

export type UploadValidationIssue = {
  code: UploadValidationCode;
  message: string;
  severity: "error" | "warning";
};

export type UploadValidationResult = {
  accepted: boolean;
  issues: UploadValidationIssue[];
  metadata: {
    base64Size: number;
    extension: string;
    imageHeight: number | null;
    imageWidth: number | null;
  };
};

const MAX_BASE64_BYTES = 10 * 1024 * 1024;
const MIN_IMAGE_DIMENSION = 20;
const MAX_IMAGE_DIMENSION = 10_000;
const SUPPORTED_EXTENSIONS = new Set(["png", "jpg", "jpeg", "pdf"]);
const SUPPORTED_MIME_TYPES = new Set(["image/png", "image/jpeg", "application/pdf"]);

export function estimateBase64Size(byteSize: number) {
  return Math.ceil(byteSize / 3) * 4;
}

export async function validateUploadCandidate(file: File): Promise<UploadValidationResult> {
  const extension = getExtension(file.name);
  const base64Size = estimateBase64Size(file.size);
  const issues: UploadValidationIssue[] = [];
  let imageWidth: number | null = null;
  let imageHeight: number | null = null;

  if (extension === "gif" || file.type === "image/gif") {
    issues.push({
      code: "OCR_GIF_NOT_SUPPORTED",
      message: "当前 OCR 运营商不支持 GIF，请转换为 PNG/JPG/PDF 后上传。",
      severity: "error",
    });
  } else if (!isSupportedFile(extension, file.type)) {
    issues.push({
      code: "OCR_UNSUPPORTED_FILE_TYPE",
      message: "仅支持 PNG、JPG、JPEG 或 PDF 发票文件。",
      severity: "error",
    });
  }

  if (base64Size > MAX_BASE64_BYTES) {
    issues.push({
      code: "OCR_FILE_TOO_LARGE",
      message: "文件 Base64 编码后可能超过 10MB，请压缩后重试。",
      severity: "error",
    });
  }

  const shouldReadDimensions =
    issues.length === 0 && (extension === "png" || extension === "jpg" || extension === "jpeg" || file.type === "image/png" || file.type === "image/jpeg");

  if (shouldReadDimensions) {
    const dimensions = await readImageDimensions(file);
    imageWidth = dimensions?.width ?? null;
    imageHeight = dimensions?.height ?? null;
    if (!dimensions || !isValidImageDimension(dimensions.width) || !isValidImageDimension(dimensions.height)) {
      issues.push({
        code: "OCR_INVALID_IMAGE_SIZE",
        message: "图片宽高需要在 20 到 10000 像素之间。",
        severity: "error",
      });
    }
  }

  return {
    accepted: issues.every((issue) => issue.severity !== "error"),
    issues,
    metadata: {
      base64Size,
      extension,
      imageHeight,
      imageWidth,
    },
  };
}

function getExtension(filename: string) {
  const index = filename.lastIndexOf(".");
  return index >= 0 ? filename.slice(index + 1).toLowerCase() : "";
}

function isSupportedFile(extension: string, mimeType: string) {
  return SUPPORTED_EXTENSIONS.has(extension) || SUPPORTED_MIME_TYPES.has(mimeType);
}

function isValidImageDimension(value: number) {
  return value >= MIN_IMAGE_DIMENSION && value <= MAX_IMAGE_DIMENSION;
}

async function readImageDimensions(file: File) {
  const bytes = new Uint8Array(await file.slice(0, 4096).arrayBuffer());
  if (isPng(bytes)) {
    return parsePngDimensions(bytes);
  }
  if (isJpeg(bytes)) {
    return parseJpegDimensions(bytes);
  }
  return null;
}

function isPng(bytes: Uint8Array) {
  return bytes.length >= 24 && bytes[0] === 0x89 && bytes[1] === 0x50 && bytes[2] === 0x4e && bytes[3] === 0x47;
}

function parsePngDimensions(bytes: Uint8Array) {
  if (bytes.length < 24) {
    return null;
  }
  return {
    width: readUint32(bytes, 16),
    height: readUint32(bytes, 20),
  };
}

function isJpeg(bytes: Uint8Array) {
  return bytes.length >= 3 && bytes[0] === 0xff && bytes[1] === 0xd8 && bytes[2] === 0xff;
}

function parseJpegDimensions(bytes: Uint8Array) {
  let offset = 2;
  while (offset + 9 < bytes.length) {
    if (bytes[offset] !== 0xff) {
      offset += 1;
      continue;
    }
    const marker = bytes[offset + 1];
    const length = (bytes[offset + 2] << 8) + bytes[offset + 3];
    if (length < 2) {
      return null;
    }
    if (isStartOfFrame(marker)) {
      return {
        height: (bytes[offset + 5] << 8) + bytes[offset + 6],
        width: (bytes[offset + 7] << 8) + bytes[offset + 8],
      };
    }
    offset += 2 + length;
  }
  return null;
}

function isStartOfFrame(marker: number) {
  return (
    (marker >= 0xc0 && marker <= 0xc3) ||
    (marker >= 0xc5 && marker <= 0xc7) ||
    (marker >= 0xc9 && marker <= 0xcb) ||
    (marker >= 0xcd && marker <= 0xcf)
  );
}

function readUint32(bytes: Uint8Array, offset: number) {
  return (bytes[offset] << 24) + (bytes[offset + 1] << 16) + (bytes[offset + 2] << 8) + bytes[offset + 3];
}
