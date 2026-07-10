from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import JSON, DateTime, MetaData, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


metadata = MetaData(
    naming_convention={
        "ix": "ix_%(table_name)s_%(column_0_name)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    }
)


JSON_VARIANT = JSON().with_variant(JSONB, "postgresql")


class Base(DeclarativeBase):
    metadata = metadata
    type_annotation_map = {dict[str, Any]: JSON_VARIANT}


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), onupdate=func.now())


def import_all_models() -> None:
    from app.domain.export import models as export_models  # noqa: F401
    from app.domain.file import models as file_models  # noqa: F401
    from app.domain.invoice import models as invoice_models  # noqa: F401
    from app.domain.ocr import models as ocr_models  # noqa: F401
    from app.domain.system import models as system_models  # noqa: F401
    from app.domain.user import models as user_models  # noqa: F401


__all__ = ["Base", "JSON_VARIANT", "TimestampMixin", "UUID", "import_all_models"]
