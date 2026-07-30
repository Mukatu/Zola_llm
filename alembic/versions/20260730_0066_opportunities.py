"""CRM : core.opportunities (pipeline commercial)

Revision ID: 20260730_0066
Revises: 20260730_0065
Create Date: 2026-07-30

Amont du cabinet : le pipeline commercial (prospect → opportunité → proposition →
gagné → mission). Une opportunité gagnée peut être convertie en `Mission`
(`mission_id`). Client = tenant existant OU prospect libre (`client_name`).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "20260730_0066"
down_revision: str | None = "20260730_0065"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "opportunities",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column(
            "client_tenant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("core.tenants.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("client_name", sa.String(200), nullable=True),
        sa.Column("offre", sa.String(64), nullable=False),
        sa.Column("amount_estimate", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("currency", sa.String(8), nullable=False, server_default="XAF"),
        sa.Column("stage", sa.String(16), nullable=False, server_default="lead"),
        sa.Column("probability", sa.Integer, nullable=False, server_default="10"),
        sa.Column("expected_close_date", sa.Date, nullable=True),
        sa.Column(
            "owner_user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("core.users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "mission_id",
            UUID(as_uuid=True),
            sa.ForeignKey("core.missions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("notes", sa.Text, nullable=False, server_default=""),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            "stage IN ('lead', 'qualified', 'proposal', 'won', 'lost')",
            name="ck_opportunities_stage",
        ),
        sa.CheckConstraint("probability BETWEEN 0 AND 100", name="ck_opportunities_probability"),
        schema="core",
    )
    op.create_index("ix_opportunities_stage", "opportunities", ["stage"], schema="core")
    op.create_index("ix_opportunities_owner", "opportunities", ["owner_user_id"], schema="core")


def downgrade() -> None:
    op.drop_index("ix_opportunities_owner", table_name="opportunities", schema="core")
    op.drop_index("ix_opportunities_stage", table_name="opportunities", schema="core")
    op.drop_table("opportunities", schema="core")
