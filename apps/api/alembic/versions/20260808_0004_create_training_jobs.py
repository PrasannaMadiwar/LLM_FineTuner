"""create training jobs

Revision ID: 20260808_0004
Revises: 20260628_0003
Create Date: 2026-08-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260808_0004"
down_revision: str | None = "20260628_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "training_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("model_key", sa.String(length=128), nullable=False),
        sa.Column("model_id", sa.String(length=512), nullable=False),
        sa.Column("template_name", sa.String(length=128), nullable=False),
        sa.Column("training_config_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("dataset_id", sa.String(length=512), nullable=False),
        sa.Column("normalized_dataset_path", sa.String(length=1024), nullable=False),
        sa.Column("gpu_instance_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("queued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["gpu_instance_id"], ["gpu_instances.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_training_jobs_gpu_instance_id"), "training_jobs", ["gpu_instance_id"], unique=False)
    op.create_index(op.f("ix_training_jobs_project_id"), "training_jobs", ["project_id"], unique=False)
    op.create_index(op.f("ix_training_jobs_status"), "training_jobs", ["status"], unique=False)
    op.create_index(op.f("ix_training_jobs_user_id"), "training_jobs", ["user_id"], unique=False)

    op.create_table(
        "training_job_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("training_job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("from_status", sa.String(length=64), nullable=True),
        sa.Column("to_status", sa.String(length=64), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["training_job_id"], ["training_jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_training_job_events_training_job_id"),
        "training_job_events",
        ["training_job_id"],
        unique=False,
    )
    op.create_index(op.f("ix_training_job_events_user_id"), "training_job_events", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_training_job_events_user_id"), table_name="training_job_events")
    op.drop_index(op.f("ix_training_job_events_training_job_id"), table_name="training_job_events")
    op.drop_table("training_job_events")
    op.drop_index(op.f("ix_training_jobs_user_id"), table_name="training_jobs")
    op.drop_index(op.f("ix_training_jobs_status"), table_name="training_jobs")
    op.drop_index(op.f("ix_training_jobs_project_id"), table_name="training_jobs")
    op.drop_index(op.f("ix_training_jobs_gpu_instance_id"), table_name="training_jobs")
    op.drop_table("training_jobs")
