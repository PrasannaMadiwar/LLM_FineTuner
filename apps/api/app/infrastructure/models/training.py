from datetime import UTC, datetime
from uuid import UUID as PythonUUID
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class TrainingJobModel(Base):
    __tablename__ = "training_jobs"

    id: Mapped[PythonUUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[PythonUUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    project_id: Mapped[PythonUUID | None] = mapped_column(PostgresUUID(as_uuid=True), index=True)
    status: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    model_key: Mapped[str] = mapped_column(String(128), nullable=False)
    model_id: Mapped[str] = mapped_column(String(512), nullable=False)
    template_name: Mapped[str] = mapped_column(String(128), nullable=False)
    training_config_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    dataset_id: Mapped[str] = mapped_column(String(512), nullable=False)
    normalized_dataset_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    gpu_instance_id: Mapped[PythonUUID | None] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("gpu_instances.id", ondelete="SET NULL"),
        index=True,
    )
    error_message: Mapped[str | None] = mapped_column(Text)
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
    queued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TrainingJobEventModel(Base):
    __tablename__ = "training_job_events"

    id: Mapped[PythonUUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    training_job_id: Mapped[PythonUUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("training_jobs.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    user_id: Mapped[PythonUUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    from_status: Mapped[str | None] = mapped_column(String(64))
    to_status: Mapped[str] = mapped_column(String(64), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )


class TrainingMetricModel(Base):
    __tablename__ = "training_metrics"

    id: Mapped[PythonUUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    training_job_id: Mapped[PythonUUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("training_jobs.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)
    epoch: Mapped[float | None] = mapped_column(Float)
    global_step: Mapped[int | None] = mapped_column(Integer)
    loss: Mapped[float | None] = mapped_column(Float)
    learning_rate: Mapped[float | None] = mapped_column(Float)
    tokens_per_second: Mapped[float | None] = mapped_column(Float)
    samples_per_second: Mapped[float | None] = mapped_column(Float)
    gpu_utilization: Mapped[float | None] = mapped_column(Float)
    gpu_memory_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    cpu_usage: Mapped[float | None] = mapped_column(Float)
    ram_usage_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    eta_seconds: Mapped[float | None] = mapped_column(Float)


class TrainingCheckpointModel(Base):
    __tablename__ = "training_checkpoints"

    id: Mapped[PythonUUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    training_job_id: Mapped[PythonUUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("training_jobs.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    epoch: Mapped[float | None] = mapped_column(Float)
    global_step: Mapped[int | None] = mapped_column(Integer)
    path: Mapped[str] = mapped_column(String(1024), nullable=False)
    is_latest: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)


class TrainingArtifactModel(Base):
    __tablename__ = "training_artifacts"

    id: Mapped[PythonUUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    training_job_id: Mapped[PythonUUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("training_jobs.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    user_id: Mapped[PythonUUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[PythonUUID | None] = mapped_column(PostgresUUID(as_uuid=True), index=True)
    artifact_type: Mapped[str] = mapped_column(String(64), nullable=False)
    path: Mapped[str] = mapped_column(String(1024), nullable=False)
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    checksum: Mapped[str | None] = mapped_column(String(128))
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)
