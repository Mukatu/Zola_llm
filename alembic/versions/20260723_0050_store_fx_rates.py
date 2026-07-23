"""Change / multi-devise : taux de change gouvernés (override tenant)

Revision ID: 20260723_0050
Revises: 20260722_0049
Create Date: 2026-07-23
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260723_0050"
down_revision: str | None = "20260722_0049"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "store_fx_rates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("country", sa.String(2), nullable=False, server_default="cg"),
        sa.Column("devise", sa.String(3), nullable=False),
        sa.Column("taux_vers_xaf", sa.Numeric(18, 6), nullable=True),
        sa.Column("validated", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("validated_by", sa.String(120), nullable=False, server_default=""),
        sa.Column("source", sa.String(255), nullable=False, server_default=""),
        sa.Column("note", sa.Text, nullable=False, server_default=""),
        sa.Column("validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("tenant_id", "country", "devise", name="uq_fx_rate"),
    )
    op.create_index("ix_store_fx_rates_tenant_id", "store_fx_rates", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_store_fx_rates_tenant_id", table_name="store_fx_rates")
    op.drop_table("store_fx_rates")
