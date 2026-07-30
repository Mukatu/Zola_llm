"""Facturation d'honoraires : core.invoices + time_entries.invoice_id

Revision ID: 20260730_0065
Revises: 20260730_0064
Create Date: 2026-07-30

Aval du PSA : la facture d'honoraires regroupe les feuilles de temps facturables
approuvées d'une mission. On crée `core.invoices` puis on ajoute la clé de
rattachement `time_entries.invoice_id` (SET NULL si la facture disparaît).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "20260730_0065"
down_revision: str | None = "20260730_0064"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "invoices",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column(
            "mission_id",
            UUID(as_uuid=True),
            sa.ForeignKey("core.missions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "client_tenant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("core.tenants.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("number", sa.String(32), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
        sa.Column("amount", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("currency", sa.String(8), nullable=False, server_default="XAF"),
        sa.Column("issued_date", sa.Date, nullable=True),
        sa.Column("due_date", sa.Date, nullable=True),
        sa.Column("paid_date", sa.Date, nullable=True),
        sa.Column("notes", sa.Text, nullable=False, server_default=""),
        sa.Column(
            "created_by_user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("core.users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'issued', 'paid', 'cancelled')", name="ck_invoices_status"
        ),
        sa.UniqueConstraint("number", name="uq_invoices_number"),
        schema="core",
    )
    op.create_index(
        "ix_invoices_client", "invoices", ["client_tenant_id", "status"], schema="core"
    )
    op.create_index("ix_invoices_mission", "invoices", ["mission_id"], schema="core")

    op.add_column(
        "time_entries",
        sa.Column(
            "invoice_id",
            UUID(as_uuid=True),
            sa.ForeignKey("core.invoices.id", ondelete="SET NULL"),
            nullable=True,
        ),
        schema="core",
    )
    op.create_index("ix_time_entries_invoice", "time_entries", ["invoice_id"], schema="core")


def downgrade() -> None:
    op.drop_index("ix_time_entries_invoice", table_name="time_entries", schema="core")
    op.drop_column("time_entries", "invoice_id", schema="core")
    op.drop_index("ix_invoices_mission", table_name="invoices", schema="core")
    op.drop_index("ix_invoices_client", table_name="invoices", schema="core")
    op.drop_table("invoices", schema="core")
