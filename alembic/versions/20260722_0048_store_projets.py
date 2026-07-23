"""Projets ONG : projets financés par bailleur + lignes budgétaires

Revision ID: 20260722_0048
Revises: 20260721_0047
Create Date: 2026-07-22
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260722_0048"
down_revision: str | None = "20260721_0047"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "store_projects",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("intitule", sa.String(200), nullable=False),
        sa.Column("bailleur", sa.String(200), nullable=False),
        sa.Column("convention_ref", sa.String(80), nullable=True),
        sa.Column("devise", sa.String(3), nullable=False, server_default="XAF"),
        sa.Column("budget_total", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("date_debut", sa.Date, nullable=True),
        sa.Column("date_fin", sa.Date, nullable=True),
        sa.Column("statut", sa.String(20), nullable=False, server_default="en_cours"),
        sa.Column("responsable", sa.String(120), nullable=True),
        sa.Column("country", sa.String(2), nullable=False, server_default="cg"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_store_projects_tenant_id", "store_projects", ["tenant_id"])

    op.create_table(
        "store_budget_lines",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("project_id", sa.String(36), nullable=False),
        sa.Column("rubrique", sa.String(120), nullable=False),
        sa.Column("activite", sa.String(200), nullable=True),
        sa.Column("montant_prevu", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("montant_engage", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("montant_realise", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("eligible", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_store_budget_lines_tenant_id", "store_budget_lines", ["tenant_id"])
    op.create_index("ix_store_budget_lines_project_id", "store_budget_lines", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_store_budget_lines_project_id", table_name="store_budget_lines")
    op.drop_index("ix_store_budget_lines_tenant_id", table_name="store_budget_lines")
    op.drop_table("store_budget_lines")
    op.drop_index("ix_store_projects_tenant_id", table_name="store_projects")
    op.drop_table("store_projects")
