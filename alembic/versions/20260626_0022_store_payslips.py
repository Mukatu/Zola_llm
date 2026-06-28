"""PAIE-1 : bulletins de paie historisés

Revision ID: 20260626_0022
Revises: 20260626_0021
Create Date: 2026-06-28
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260626_0022"
down_revision: str | None = "20260626_0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "store_payslips",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("employee_matricule", sa.String(32), nullable=False),
        sa.Column("periode", sa.String(7), nullable=False),
        sa.Column("brut_xaf", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("cotisations_salariales", sa.JSON, nullable=False, server_default="{}"),
        sa.Column(
            "total_cotisations_salariales_xaf",
            sa.Numeric(18, 2),
            nullable=False,
            server_default="0",
        ),
        sa.Column("base_imposable_xaf", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("irpp_xaf", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("net_a_payer_xaf", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("cotisations_patronales", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("cout_employeur_xaf", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("statut", sa.String(12), nullable=False, server_default="brouillon"),
        sa.Column("date_paiement", sa.Date, nullable=True),
        sa.Column("country", sa.String(2), nullable=False, server_default="cg"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_store_payslips_tenant_id", "store_payslips", ["tenant_id"])
    op.create_index("ix_store_payslips_matricule", "store_payslips", ["employee_matricule"])


def downgrade() -> None:
    op.drop_index("ix_store_payslips_matricule", table_name="store_payslips")
    op.drop_index("ix_store_payslips_tenant_id", table_name="store_payslips")
    op.drop_table("store_payslips")
