"""PSA : core.time_entries (feuilles de temps) + users.grade

Revision ID: 20260730_0064
Revises: 20260730_0063
Create Date: 2026-07-30

Socle du PSA (outillage cabinet) : la feuille de temps (consultant × mission ×
jour × durée), d'où découlent honoraires, rentabilité et taux d'occupation. Les
taux (bill_rate/cost_rate) sont figés à la saisie. Ajoute aussi `users.grade`
(rattachement au barème d'honoraires).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "20260730_0064"
down_revision: str | None = "20260730_0063"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("grade", sa.String(20), nullable=True), schema="core")

    op.create_table(
        "time_entries",
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
        sa.Column("entry_date", sa.Date, nullable=False),
        sa.Column("minutes", sa.Integer, nullable=False),
        sa.Column("billable", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("activity", sa.Text, nullable=False, server_default=""),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
        sa.Column("bill_rate", sa.Integer, nullable=False, server_default="0"),
        sa.Column("cost_rate", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("minutes > 0", name="ck_time_entries_minutes_positive"),
        sa.CheckConstraint(
            "status IN ('draft', 'submitted', 'approved', 'rejected')",
            name="ck_time_entries_status",
        ),
        schema="core",
    )
    op.create_index("ix_time_entries_mission", "time_entries", ["mission_id"], schema="core")
    op.create_index(
        "ix_time_entries_consultant_date",
        "time_entries",
        ["consultant_user_id", "entry_date"],
        schema="core",
    )


def downgrade() -> None:
    op.drop_index("ix_time_entries_consultant_date", table_name="time_entries", schema="core")
    op.drop_index("ix_time_entries_mission", table_name="time_entries", schema="core")
    op.drop_table("time_entries", schema="core")
    op.drop_column("users", "grade", schema="core")
