"""FINTECH-7 : date de décaissement sur le dossier de crédit (millésime cohortes)

Revision ID: 20260708_0041
Revises: 20260708_0040
Create Date: 2026-07-08
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260708_0041"
down_revision: str | None = "20260708_0040"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "store_credit_applications",
        sa.Column("date_decaissement", sa.Date, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("store_credit_applications", "date_decaissement")
