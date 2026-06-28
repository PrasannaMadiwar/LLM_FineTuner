"""create dataset intelligence tables

Revision ID: 20260628_0002
Revises: 20260628_0001
Create Date: 2026-06-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260628_0002"
down_revision: str | None = "20260628_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "dataset_metadata_cache",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("dataset_id", sa.String(length=512), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=512), nullable=False),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_dataset_metadata_cache_dataset_id"), "dataset_metadata_cache", ["dataset_id"], unique=True)

    op.create_table(
        "dataset_mappings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("dataset_name", sa.String(length=512), nullable=False),
        sa.Column("mapping_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_dataset_mappings_dataset_name"), "dataset_mappings", ["dataset_name"], unique=True)

    op.create_table(
        "dataset_normalization_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("dataset_name", sa.String(length=512), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("mapping_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("validation_report_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("normalized_sample_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_dataset_normalization_history_dataset_name"),
        "dataset_normalization_history",
        ["dataset_name"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_dataset_normalization_history_dataset_name"), table_name="dataset_normalization_history")
    op.drop_table("dataset_normalization_history")
    op.drop_index(op.f("ix_dataset_mappings_dataset_name"), table_name="dataset_mappings")
    op.drop_table("dataset_mappings")
    op.drop_index(op.f("ix_dataset_metadata_cache_dataset_id"), table_name="dataset_metadata_cache")
    op.drop_table("dataset_metadata_cache")
