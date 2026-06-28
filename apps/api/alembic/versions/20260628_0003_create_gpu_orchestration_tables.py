"""create gpu orchestration tables

Revision ID: 20260628_0003
Revises: 20260628_0002
Create Date: 2026-06-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260628_0003"
down_revision: str | None = "20260628_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "gpu_instances",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("provider_instance_id", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("gpu_type", sa.String(length=128), nullable=True),
        sa.Column("endpoint_url", sa.String(length=1024), nullable=True),
        sa.Column("cost_estimate", sa.Float(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("terminated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_gpu_instances_provider_instance_id"), "gpu_instances", ["provider_instance_id"], unique=True)
    op.create_index(op.f("ix_gpu_instances_project_id"), "gpu_instances", ["project_id"], unique=False)
    op.create_index(op.f("ix_gpu_instances_status"), "gpu_instances", ["status"], unique=False)
    op.create_index(op.f("ix_gpu_instances_user_id"), "gpu_instances", ["user_id"], unique=False)

    op.create_table(
        "training_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("gpu_instance_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["gpu_instance_id"], ["gpu_instances.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_training_sessions_gpu_instance_id"), "training_sessions", ["gpu_instance_id"], unique=False)
    op.create_index(op.f("ix_training_sessions_project_id"), "training_sessions", ["project_id"], unique=False)
    op.create_index(op.f("ix_training_sessions_user_id"), "training_sessions", ["user_id"], unique=False)

    op.create_table(
        "gpu_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("gpu_instance_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["gpu_instance_id"], ["gpu_instances.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_gpu_events_gpu_instance_id"), "gpu_events", ["gpu_instance_id"], unique=False)
    op.create_index(op.f("ix_gpu_events_user_id"), "gpu_events", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_gpu_events_user_id"), table_name="gpu_events")
    op.drop_index(op.f("ix_gpu_events_gpu_instance_id"), table_name="gpu_events")
    op.drop_table("gpu_events")
    op.drop_index(op.f("ix_training_sessions_user_id"), table_name="training_sessions")
    op.drop_index(op.f("ix_training_sessions_project_id"), table_name="training_sessions")
    op.drop_index(op.f("ix_training_sessions_gpu_instance_id"), table_name="training_sessions")
    op.drop_table("training_sessions")
    op.drop_index(op.f("ix_gpu_instances_user_id"), table_name="gpu_instances")
    op.drop_index(op.f("ix_gpu_instances_status"), table_name="gpu_instances")
    op.drop_index(op.f("ix_gpu_instances_project_id"), table_name="gpu_instances")
    op.drop_index(op.f("ix_gpu_instances_provider_instance_id"), table_name="gpu_instances")
    op.drop_table("gpu_instances")
