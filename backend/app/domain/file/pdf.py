from __future__ import annotations

import re

from app.core.errors import AppError


PDF_PAGE_PATTERN = re.compile(rb"/Type\s*/Page\b")


def count_pdf_pages(content: bytes) -> int:
    page_count = len(PDF_PAGE_PATTERN.findall(content))
    if page_count < 1:
        raise AppError("OCR_UNSUPPORTED_FILE_TYPE", "The uploaded PDF could not be parsed", status_code=400)
    return page_count
