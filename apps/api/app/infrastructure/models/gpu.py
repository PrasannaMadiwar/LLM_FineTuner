from datetime import UTC, datetime
from uuid import UUID as PythonUUID
from uuid import uuid4

from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class GPUInstanceModel(Base):
    __tablename__ = "gpu_instances"

    id: Mapped[PythonUUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_instance_id: Mapped[str | None] = mapped_column(String(255), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    user_id: Mapped[PythonUUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    project_id: Mapped[PythonUUID | None] = mapped_column(PostgresUUID(as_uuid=True), index=True)
    gpu_type: Mapped[str | None] = mapped_column(String(128))
    endpoint_url: Mapped[str | None] = mapped_column(String(1024))
    cost_estimate: Mapped[float | None] = mapped_column(Float)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
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
    terminated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TrainingSessionModel(Base):
    __tablename__ = "training_sessions"

    id: Mapped[PythonUUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    gpu_instance_id: Mapped[PythonUUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("gpu_instances.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    user_id: Mapped[PythonUUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    project_id: Mapped[PythonUUID | None] = mapped_column(PostgresUUID(as_uuid=True), index=True)
    status: Mapped[str] = mapped_column(String(64), nullable=False)
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


class GPUEventModel(Base):
    __tablename__ = "gpu_events"

    id: Mapped[PythonUUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    gpu_instance_id: Mapped[PythonUUID | None] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("gpu_instances.id", ondelete="SET NULL"),
        index=True,
    )
    user_id: Mapped[PythonUUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
