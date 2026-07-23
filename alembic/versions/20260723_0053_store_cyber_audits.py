"""Cyber : registre des audits de durcissement (défensif)

Revision ID: 20260723_0053
Revises: 20260723_0052
Create Date: 2026-07-23
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260723_0053"
down_revision: str | None = "20260723_0052"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "store_cyber_audits",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("cible", sa.String(200), nullable=False, server_default=""),
        sa.Column("score_conformite", sa.Numeric(5, 1), nullable=False, server_default="0"),
        sa.Column("nb_conforme", sa.Integer, nullable=False, server_default="0"),
        sa.Column("nb_non_conforme", sa.Integer, nullable=False, server_default="0"),
        sa.Column("nb_a_verifier", sa.Integer, nullable=False, server_default="0"),
        sa.Column("niveau", sa.String(10), nullable=False, server_default="aucun"),
        sa.Column("config", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("resultat", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("commentaire", sa.Text, nullable=True),
        sa.Column("country", sa.String(2), nullable=False, server_default="cg"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_store_cyber_audits_tenant_id", "store_cyber_audits", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_store_cyber_audits_tenant_id", table_name="store_cyber_audits")
    op.drop_table("store_cyber_audits")
