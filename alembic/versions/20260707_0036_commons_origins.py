"""Commons Phase B — colonne origins (k-anonymat sur origines distinctes)

Revision ID: 20260707_0036
Revises: 20260707_0035
Create Date: 2026-07-07
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260707_0036"
down_revision: str | None = "20260707_0035"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "store_contrib_candidates",
        sa.Column("origins", sa.JSON, nullable=False, server_default="[]"),
    )


def downgrade() -> None:
    op.drop_column("store_contrib_candidates", "origins")
