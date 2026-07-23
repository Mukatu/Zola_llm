"""Secrétariat sociétaire : mandats sociaux + résolutions AG/CA

Revision ID: 20260722_0049
Revises: 20260722_0048
Create Date: 2026-07-22
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260722_0049"
down_revision: str | None = "20260722_0048"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "store_mandates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("titulaire", sa.String(120), nullable=False),
        sa.Column("fonction", sa.String(60), nullable=False, server_default="autre"),
        sa.Column("date_nomination", sa.Date, nullable=False),
        sa.Column("duree_annees", sa.Integer, nullable=False, server_default="0"),
        sa.Column("organe", sa.String(40), nullable=True),
        sa.Column("statut", sa.String(20), nullable=False, server_default="actif"),
        sa.Column("country", sa.String(2), nullable=False, server_default="cg"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_store_mandates_tenant_id", "store_mandates", ["tenant_id"])

    op.create_table(
        "store_resolutions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("type_reunion", sa.String(8), nullable=False),
        sa.Column("date_reunion", sa.Date, nullable=False),
        sa.Column("objet", sa.String(200), nullable=False),
        sa.Column("decision", sa.Text, nullable=False, server_default=""),
        sa.Column("reference_pv", sa.String(40), nullable=True),
        sa.Column("quorum", sa.String(40), nullable=True),
        sa.Column("country", sa.String(2), nullable=False, server_default="cg"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_store_resolutions_tenant_id", "store_resolutions", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_store_resolutions_tenant_id", table_name="store_resolutions")
    op.drop_table("store_resolutions")
    op.drop_index("ix_store_mandates_tenant_id", table_name="store_mandates")
    op.drop_table("store_mandates")
