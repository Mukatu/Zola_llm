"""SIRH-3b : évaluations (performance × potentiel)

Revision ID: 20260624_0012
Revises: 20260624_0011
Create Date: 2026-06-24
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260624_0012"
down_revision: str | None = "20260624_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "store_evaluations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("employee_matricule", sa.String(32), nullable=False),
        sa.Column("periode", sa.String(16), nullable=False, server_default=""),
        sa.Column("performance", sa.Integer, nullable=False, server_default="3"),
        sa.Column("potentiel", sa.Integer, nullable=False, server_default="3"),
        sa.Column("objectifs", sa.Text, nullable=False, server_default=""),
        sa.Column("commentaire", sa.Text, nullable=False, server_default=""),
        sa.Column("statut", sa.String(12), nullable=False, server_default="brouillon"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_store_evaluations_tenant_id", "store_evaluations", ["tenant_id"])
    op.create_index("ix_store_evaluations_emp", "store_evaluations", ["employee_matricule"])


def downgrade() -> None:
    op.drop_index("ix_store_evaluations_emp", table_name="store_evaluations")
    op.drop_index("ix_store_evaluations_tenant_id", table_name="store_evaluations")
    op.drop_table("store_evaluations")
