"""Fintech : registre AML (dossiers de surveillance persistés)

Revision ID: 20260723_0052
Revises: 20260723_0051
Create Date: 2026-07-23
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260723_0052"
down_revision: str | None = "20260723_0051"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "store_aml_cases",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("reference", sa.String(64), nullable=False, server_default=""),
        sa.Column("client", sa.String(200), nullable=False),
        sa.Column("nb_operations", sa.Integer, nullable=False, server_default="0"),
        sa.Column("volume_total_xaf", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("volume_especes_xaf", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("niveau", sa.String(10), nullable=False, server_default="info"),
        sa.Column("nb_alertes", sa.Integer, nullable=False, server_default="0"),
        sa.Column("statut", sa.String(12), nullable=False, server_default="a_examiner"),
        sa.Column("declaration_ref", sa.String(64), nullable=True),
        sa.Column("transactions", sa.JSON, nullable=False, server_default="[]"),
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
    op.create_index("ix_store_aml_cases_tenant_id", "store_aml_cases", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_store_aml_cases_tenant_id", table_name="store_aml_cases")
    op.drop_table("store_aml_cases")
