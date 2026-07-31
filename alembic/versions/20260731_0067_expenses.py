"""Notes de frais : core.expenses

Revision ID: 20260731_0067
Revises: 20260730_0066
Create Date: 2026-07-31

L'autre engagement du consultant sur une mission (avec le temps) : le frais. S'il
est facturable, il rejoint la facture d'honoraires comme débours (`invoice_id`) ;
approuvé, il est un coût du cabinet. Miroir de `time_entries`.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "20260731_0067"
down_revision: str | None = "20260730_0066"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "expenses",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column(
            "consultant_user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("core.users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "mission_id",
            UUID(as_uuid=True),
            sa.ForeignKey("core.missions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("expense_date", sa.Date, nullable=False),
        sa.Column("category", sa.String(24), nullable=False),
        sa.Column("amount", sa.BigInteger, nullable=False),
        sa.Column("billable", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
        sa.Column(
            "invoice_id",
            UUID(as_uuid=True),
            sa.ForeignKey("core.invoices.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("amount > 0", name="ck_expenses_amount_positive"),
        sa.CheckConstraint(
            "status IN ('draft', 'submitted', 'approved', 'rejected')", name="ck_expenses_status"
        ),
        schema="core",
    )
    op.create_index("ix_expenses_mission", "expenses", ["mission_id"], schema="core")
    op.create_index(
        "ix_expenses_consultant_date",
        "expenses",
        ["consultant_user_id", "expense_date"],
        schema="core",
    )
    op.create_index("ix_expenses_invoice", "expenses", ["invoice_id"], schema="core")


def downgrade() -> None:
    op.drop_index("ix_expenses_invoice", table_name="expenses", schema="core")
    op.drop_index("ix_expenses_consultant_date", table_name="expenses", schema="core")
    op.drop_index("ix_expenses_mission", table_name="expenses", schema="core")
    op.drop_table("expenses", schema="core")
