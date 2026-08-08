"""training pipeline hardening

Revision ID: 20260808_0005
Revises: 20260808_0004
Create Date: 2026-08-08 00:05:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260808_0005"
down_revision: str | None = "20260808_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("dataset_normalization_history", sa.Column("artifact_path", sa.String(length=1024), nullable=True))
    op.add_column("dataset_normalization_history", sa.Column("user_id", sa.String(length=128), nullable=True))
    op.add_column("dataset_normalization_history", sa.Column("project_id", sa.String(length=128), nullable=True))
    op.create_index(op.f("ix_dataset_normalization_history_user_id"), "dataset_normalization_history", ["user_id"])
    op.create_index(op.f("ix_dataset_normalization_history_project_id"), "dataset_normalization_history", ["project_id"])

    op.create_table(
        "training_metrics",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("training_job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("epoch", sa.Float(), nullable=True),
        sa.Column("global_step", sa.Integer(), nullable=True),
        sa.Column("loss", sa.Float(), nullable=True),
        sa.Column("learning_rate", sa.Float(), nullable=True),
        sa.Column("tokens_per_second", sa.Float(), nullable=True),
        sa.Column("samples_per_second", sa.Float(), nullable=True),
        sa.Column("gpu_utilization", sa.Float(), nullable=True),
        sa.Column("gpu_memory_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("cpu_usage", sa.Float(), nullable=True),
        sa.Column("ram_usage_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("eta_seconds", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(["training_job_id"], ["training_jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_training_metrics_training_job_id"), "training_metrics", ["training_job_id"])

    op.create_table(
        "training_checkpoints",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("training_job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("epoch", sa.Float(), nullable=True),
        sa.Column("global_step", sa.Integer(), nullable=True),
        sa.Column("path", sa.String(length=1024), nullable=False),
        sa.Column("is_latest", sa.Boolean(), nullable=False),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["training_job_id"], ["training_jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_training_checkpoints_training_job_id"), "training_checkpoints", ["training_job_id"])

    op.create_table(
        "training_artifacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("training_job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("artifact_type", sa.String(length=64), nullable=False),
        sa.Column("path", sa.String(length=1024), nullable=False),
        sa.Column("filename", sa.String(length=512), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("checksum", sa.String(length=128), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["training_job_id"], ["training_jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_training_artifacts_training_job_id"), "training_artifacts", ["training_job_id"])
    op.create_index(op.f("ix_training_artifacts_user_id"), "training_artifacts", ["user_id"])
    op.create_index(op.f("ix_training_artifacts_project_id"), "training_artifacts", ["project_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_training_artifacts_project_id"), table_name="training_artifacts")
    op.drop_index(op.f("ix_training_artifacts_user_id"), table_name="training_artifacts")
    op.drop_index(op.f("ix_training_artifacts_training_job_id"), table_name="training_artifacts")
    op.drop_table("training_artifacts")
    op.drop_index(op.f("ix_training_checkpoints_training_job_id"), table_name="training_checkpoints")
    op.drop_table("training_checkpoints")
    op.drop_index(op.f("ix_training_metrics_training_job_id"), table_name="training_metrics")
    op.drop_table("training_metrics")
    op.drop_index(op.f("ix_dataset_normalization_history_project_id"), table_name="dataset_normalization_history")
    op.drop_index(op.f("ix_dataset_normalization_history_user_id"), table_name="dataset_normalization_history")
    op.drop_column("dataset_normalization_history", "project_id")
    op.drop_column("dataset_normalization_history", "user_id")
    op.drop_column("dataset_normalization_history", "artifact_path")
