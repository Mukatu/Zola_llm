"""Documents (artefacts générés, transverse)

Revision ID: 20260623_0010
Revises: 20260623_0009
Create Date: 2026-06-23
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260623_0010"
down_revision: str | None = "20260623_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "store_documents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("type", sa.String(32), nullable=False, server_default="autre"),
        sa.Column("metier", sa.String(20), nullable=False, server_default="rh"),
        sa.Column("titre", sa.String(200), nullable=False),
        sa.Column("contenu", sa.Text, nullable=False, server_default=""),
        sa.Column("tags", sa.JSON, nullable=False),
        sa.Column("source_ref", sa.String(64), nullable=True),
        sa.Column("statut", sa.String(12), nullable=False, server_default="brouillon"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_store_documents_tenant_id", "store_documents", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_store_documents_tenant_id", table_name="store_documents")
    op.drop_table("store_documents")
