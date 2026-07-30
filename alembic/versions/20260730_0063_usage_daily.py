"""core.usage_daily : grand livre d'usage durable par tenant/jour (facturation)

Revision ID: 20260730_0063
Revises: 20260729_0062
Create Date: 2026-07-30

Persiste l'usage (requêtes + tokens) par tenant et par jour — base de facturation
durable, en complément des compteurs Redis éphémères du quota temps-réel. Upsert
par `require_quota` quand `BILLING_LEDGER_ENABLED`. PK composite (tenant_id, day).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260730_0063"
down_revision: str | None = "20260729_0062"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "usage_daily",
        sa.Column("tenant_id", sa.String(64), primary_key=True, nullable=False),
        sa.Column("day", sa.Date, primary_key=True, nullable=False),
        sa.Column("requests", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("tokens", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        schema="core",
    )
    op.create_index("ix_usage_daily_day", "usage_daily", ["day"], schema="core")


def downgrade() -> None:
    op.drop_index("ix_usage_daily_day", table_name="usage_daily", schema="core")
    op.drop_table("usage_daily", schema="core")
