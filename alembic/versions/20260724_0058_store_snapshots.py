"""Historisation pilotage : instantanés horodatés (BI, portefeuille)

Revision ID: 20260724_0058
Revises: 20260724_0057
Create Date: 2026-07-24
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260724_0058"
down_revision: str | None = "20260724_0057"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "store_snapshots",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("domaine", sa.String(30), nullable=False),
        sa.Column("payload", sa.JSON, nullable=False, server_default="{}"),
        sa.Column(
            "captured_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("country", sa.String(2), nullable=False, server_default="cg"),
    )
    op.create_index("ix_store_snapshots_tenant_id", "store_snapshots", ["tenant_id"])
    op.create_index("ix_store_snapshots_domaine", "store_snapshots", ["domaine"])


def downgrade() -> None:
    op.drop_index("ix_store_snapshots_domaine", table_name="store_snapshots")
    op.drop_index("ix_store_snapshots_tenant_id", table_name="store_snapshots")
    op.drop_table("store_snapshots")
