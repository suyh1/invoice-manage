from __future__ import annotations

import hashlib
from dataclasses import dataclass

from app.core.config import UPLOAD_VALIDATION_DEFAULTS
from app.core.errors import AppError
from app.domain.file.pdf import count_pdf_pages


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
PDF_SIGNATURE = b"%PDF-"
JPEG_SIGNATURE = b"\xff\xd8"
GIF_SIGNATURES = (b"GIF87a", b"GIF89a")
JPEG_SOF_MARKERS = {
    0xC0,
    0xC1,
    0xC2,
    0xC3,
    0xC5,
    0xC6,
    0xC7,
    0xC9,
    0xCA,
    0xCB,
    0xCD,
    0xCE,
    0xCF,
}
ALLOWED_CONTENT_TYPES = {
    "png": {"image/png"},
    "jpg": {"image/jpeg", "image/pjpeg"},
    "pdf": {"application/pdf"},
    "gif": {"image/gif"},
}


@dataclass(frozen=True)
class ValidatedUpload:
    original_filename: str
    content_type: str | None
    file_ext: str
    file_size: int
    base64_size: int
    sha256: str
    page_count: int
    image_width: int | None
    image_height: int | None
    content: bytes


def validate_upload(filename: str, content_type: str | None, content: bytes) -> ValidatedUpload:
    file_ext = normalize_extension(filename)
    detected_type = detect_file_type(content)

    if detected_type == "gif":
        raise AppError("OCR_GIF_NOT_SUPPORTED", "The current OCR provider does not support GIF files", status_code=400)
    if detected_type not in {"png", "jpg", "pdf"}:
        raise AppError("OCR_UNSUPPORTED_FILE_TYPE", "Only PNG, JPG, JPEG, and PDF files are supported", status_code=400)
    if file_ext not in UPLOAD_VALIDATION_DEFAULTS.allowed_extensions:
        raise AppError("OCR_UNSUPPORTED_FILE_TYPE", "Only PNG, JPG, JPEG, and PDF files are supported", status_code=400)
    if not extension_matches(file_ext, detected_type):
        raise AppError("OCR_UNSUPPORTED_FILE_TYPE", "File extension does not match the uploaded content", status_code=400)
    if not content_type_matches(content_type, detected_type):
        raise AppError("OCR_UNSUPPORTED_FILE_TYPE", "Uploaded MIME type is not supported for this file", status_code=400)

    file_size = len(content)
    base64_size = exact_base64_size(file_size)
    if base64_size > UPLOAD_VALIDATION_DEFAULTS.max_base64_size_bytes:
        raise AppError("OCR_FILE_TOO_LARGE", "The file exceeds the 10MB Base64 OCR limit", status_code=400)

    image_width: int | None = None
    image_height: int | None = None
    page_count = 1
    if detected_type == "png":
        image_width, image_height = extract_png_dimensions(content)
    elif detected_type == "jpg":
        image_width, image_height = extract_jpeg_dimensions(content)
    elif detected_type == "pdf":
        page_count = count_pdf_pages(content)
        if page_count > UPLOAD_VALIDATION_DEFAULTS.max_pdf_pages:
            raise AppError("OCR_PDF_MULTI_PAGE_NOT_SUPPORTED", "PDF files must be split into single pages", status_code=400)

    if image_width is not None and image_height is not None:
        min_size = UPLOAD_VALIDATION_DEFAULTS.min_image_dimension_px
        max_size = UPLOAD_VALIDATION_DEFAULTS.max_image_dimension_px
        if not (min_size <= image_width <= max_size and min_size <= image_height <= max_size):
            raise AppError(
                "OCR_INVALID_IMAGE_SIZE",
                "Image dimensions must be between 20px and 10000px",
                status_code=400,
            )

    return ValidatedUpload(
        original_filename=filename,
        content_type=content_type,
        file_ext=file_ext,
        file_size=file_size,
        base64_size=base64_size,
        sha256=hashlib.sha256(content).hexdigest(),
        page_count=page_count,
        image_width=image_width,
        image_height=image_height,
        content=content,
    )


def normalize_extension(filename: str) -> str:
    parts = filename.rsplit(".", 1)
    if len(parts) != 2 or not parts[1]:
        raise AppError("OCR_UNSUPPORTED_FILE_TYPE", "The uploaded file must include an extension", status_code=400)
    return parts[1].lower()


def detect_file_type(content: bytes) -> str | None:
    if content.startswith(PNG_SIGNATURE):
        return "png"
    if content.startswith(JPEG_SIGNATURE):
        return "jpg"
    if content.startswith(PDF_SIGNATURE):
        return "pdf"
    if any(content.startswith(signature) for signature in GIF_SIGNATURES):
        return "gif"
    return None


def extension_matches(file_ext: str, detected_type: str) -> bool:
    if detected_type == "jpg":
        return file_ext in {"jpg", "jpeg"}
    return file_ext == detected_type


def content_type_matches(content_type: str | None, detected_type: str) -> bool:
    if not content_type or content_type == "application/octet-stream":
        return True
    return content_type in ALLOWED_CONTENT_TYPES[detected_type]


def exact_base64_size(file_size: int) -> int:
    return ((file_size + 2) // 3) * 4


def extract_png_dimensions(content: bytes) -> tuple[int, int]:
    if len(content) < 24:
        raise AppError("OCR_UNSUPPORTED_FILE_TYPE", "The uploaded PNG is truncated", status_code=400)
    return int.from_bytes(content[16:20], "big"), int.from_bytes(content[20:24], "big")


def extract_jpeg_dimensions(content: bytes) -> tuple[int, int]:
    if not content.startswith(JPEG_SIGNATURE):
        raise AppError("OCR_UNSUPPORTED_FILE_TYPE", "The uploaded JPEG is invalid", status_code=400)

    offset = 2
    while offset < len(content):
        if content[offset] != 0xFF:
            offset += 1
            continue
        while offset < len(content) and content[offset] == 0xFF:
            offset += 1
        if offset >= len(content):
            break

        marker = content[offset]
        offset += 1
        if marker in {0xD8, 0xD9, 0x01} or 0xD0 <= marker <= 0xD7:
            continue
        if offset + 2 > len(content):
            break

        segment_length = int.from_bytes(content[offset : offset + 2], "big")
        if segment_length < 2 or offset + segment_length > len(content):
            break
        if marker in JPEG_SOF_MARKERS:
            if segment_length < 7:
                break
            height = int.from_bytes(content[offset + 3 : offset + 5], "big")
            width = int.from_bytes(content[offset + 5 : offset + 7], "big")
            return width, height
        offset += segment_length

    raise AppError("OCR_UNSUPPORTED_FILE_TYPE", "The uploaded JPEG is invalid", status_code=400)
