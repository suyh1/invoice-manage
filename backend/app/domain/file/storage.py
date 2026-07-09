from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from app.domain.file.validators import ValidatedUpload


class LocalFileStorage:
    def __init__(self, root_path: Path) -> None:
        self.root_path = root_path

    def save(self, validated_upload: ValidatedUpload, created_at: datetime | None = None) -> str:
        timestamp = created_at or datetime.now(UTC)
        storage_key = "{year:04d}/{month:02d}/{sha256}.{ext}".format(
            year=timestamp.year,
            month=timestamp.month,
            sha256=validated_upload.sha256,
            ext=validated_upload.file_ext,
        )
        destination = self.root_path / storage_key
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(validated_upload.content)
        return storage_key
