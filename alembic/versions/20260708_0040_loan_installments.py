"""FINTECH-6 : échéancier de remboursement (échéances de prêt)

Revision ID: 20260708_0040
Revises: 20260708_0039
Create Date: 2026-07-08
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260708_0040"
down_revision: str | None = "20260708_0039"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "store_loan_installments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("application_id", sa.String(36), nullable=False),
        sa.Column("numero", sa.Integer, nullable=False),
        sa.Column("date_echeance", sa.Date, nullable=False),
        sa.Column("principal_xaf", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("interet_xaf", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("montant_xaf", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("montant_paye_xaf", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("statut", sa.String(12), nullable=False, server_default="a_venir"),
        sa.Column("paye_le", sa.Date, nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index(
        "ix_store_loan_installments_tenant_id", "store_loan_installments", ["tenant_id"]
    )
    op.create_index(
        "ix_store_loan_installments_application_id",
        "store_loan_installments",
        ["application_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_store_loan_installments_application_id", table_name="store_loan_installments"
    )
    op.drop_index("ix_store_loan_installments_tenant_id", table_name="store_loan_installments")
    op.drop_table("store_loan_installments")
