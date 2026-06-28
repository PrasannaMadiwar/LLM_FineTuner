from datetime import UTC, datetime
from uuid import UUID as PythonUUID
from uuid import uuid4

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class DatasetMetadataCacheModel(Base):
    __tablename__ = "dataset_metadata_cache"

    id: Mapped[PythonUUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    dataset_id: Mapped[str] = mapped_column(String(512), unique=True, index=True, nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(512), nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )


class DatasetMappingModel(Base):
    __tablename__ = "dataset_mappings"

    id: Mapped[PythonUUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    dataset_name: Mapped[str] = mapped_column(String(512), unique=True, index=True, nullable=False)
    mapping_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )


class DatasetNormalizationHistoryModel(Base):
    __tablename__ = "dataset_normalization_history"

    id: Mapped[PythonUUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    dataset_name: Mapped[str] = mapped_column(String(512), index=True, nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    mapping_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    validation_report_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    normalized_sample_json: Mapped[list] = mapped_column(JSONB, nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
