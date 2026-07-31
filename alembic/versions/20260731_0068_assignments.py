"""Staffing : core.assignments (plan de charge)

Revision ID: 20260731_0068
Revises: 20260731_0067
Create Date: 2026-07-31

Affectation prévisionnelle d'un consultant à une mission pour une semaine
(`week_start` = lundi), avec une capacité allouée. Agrégées, les affectations
donnent le plan de charge (charge vs capacité). Une ligne par (consultant, mission,
semaine).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "20260731_0068"
down_revision: str | None = "20260731_0067"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "assignments",
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
        sa.Column("week_start", sa.Date, nullable=False),
        sa.Column("allocated_minutes", sa.Integer, nullable=False),
        sa.Column("note", sa.Text, nullable=False, server_default=""),
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
        sa.CheckConstraint("allocated_minutes > 0", name="ck_assignments_minutes_positive"),
        sa.UniqueConstraint(
            "consultant_user_id", "mission_id", "week_start", name="uq_assignments_slot"
        ),
        schema="core",
    )
    op.create_index(
        "ix_assignments_consultant_week",
        "assignments",
        ["consultant_user_id", "week_start"],
        schema="core",
    )
    op.create_index("ix_assignments_mission", "assignments", ["mission_id"], schema="core")
    op.create_index("ix_assignments_week", "assignments", ["week_start"], schema="core")


def downgrade() -> None:
    op.drop_index("ix_assignments_week", table_name="assignments", schema="core")
    op.drop_index("ix_assignments_mission", table_name="assignments", schema="core")
    op.drop_index("ix_assignments_consultant_week", table_name="assignments", schema="core")
    op.drop_table("assignments", schema="core")
