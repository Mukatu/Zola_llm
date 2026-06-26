"""Achats v2 : engagements d'achats (chaîne EB → DA → BC)

Revision ID: 20260626_0015
Revises: 20260626_0014
Create Date: 2026-06-26
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260626_0015"
down_revision: str | None = "20260626_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "store_engagements",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("numero_eb", sa.String(32), nullable=False),
        sa.Column("numero_da", sa.String(32), nullable=True),
        sa.Column("numero_bc", sa.String(32), nullable=True),
        sa.Column("date_eb", sa.Date, nullable=True),
        sa.Column("date_da", sa.Date, nullable=True),
        sa.Column("date_bc", sa.Date, nullable=True),
        sa.Column("direction", sa.String(40), nullable=True),
        sa.Column("service", sa.String(120), nullable=True),
        sa.Column("demandeur", sa.String(120), nullable=True),
        sa.Column("acheteur", sa.String(120), nullable=True),
        sa.Column("fournisseur", sa.String(200), nullable=True),
        sa.Column("description_besoin", sa.Text, nullable=False, server_default=""),
        sa.Column("description_da", sa.Text, nullable=False, server_default=""),
        sa.Column("description_bc", sa.Text, nullable=False, server_default=""),
        sa.Column("estimation_xaf", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("montant_xaf", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("statut_ebda", sa.String(40), nullable=False, server_default=""),
        sa.Column("statut_bc", sa.String(40), nullable=False, server_default=""),
        sa.Column("country", sa.String(2), nullable=False, server_default="cg"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_store_engagements_tenant_id", "store_engagements", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_store_engagements_tenant_id", table_name="store_engagements")
    op.drop_table("store_engagements")
