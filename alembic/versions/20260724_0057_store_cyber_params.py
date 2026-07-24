"""Cyber : paramètres gouvernés (base de durcissement + seuils, override tenant)

Revision ID: 20260724_0057
Revises: 20260724_0056
Create Date: 2026-07-24
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260724_0057"
down_revision: str | None = "20260724_0056"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "store_cyber_params",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("country", sa.String(2), nullable=False, server_default="cg"),
        sa.Column("version", sa.String(64), nullable=False, server_default=""),
        sa.Column("payload", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("validated", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("validated_by", sa.String(120), nullable=False, server_default=""),
        sa.Column("note", sa.Text, nullable=False, server_default=""),
        sa.Column("validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("tenant_id", "country", name="uq_cyber_params"),
    )
    op.create_index("ix_store_cyber_params_tenant_id", "store_cyber_params", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_store_cyber_params_tenant_id", table_name="store_cyber_params")
    op.drop_table("store_cyber_params")
