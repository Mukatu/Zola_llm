"""PAIE-3c : champs déclaratifs DAS 1 sur l'employé (CNSS/fiscal)

Revision ID: 20260626_0023
Revises: 20260626_0022
Create Date: 2026-06-28
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260626_0023"
down_revision: str | None = "20260626_0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("store_employees", sa.Column("livret_cnss", sa.String(32), nullable=True))
    op.add_column("store_employees", sa.Column("n_contribuable", sa.String(32), nullable=True))
    op.add_column(
        "store_employees",
        sa.Column("situation_matrimoniale", sa.String(12), nullable=False, server_default=""),
    )
    op.add_column(
        "store_employees",
        sa.Column("nationalite", sa.String(40), nullable=False, server_default=""),
    )
    op.add_column(
        "store_employees", sa.Column("nb_enfants", sa.Integer, nullable=False, server_default="0")
    )


def downgrade() -> None:
    op.drop_column("store_employees", "nb_enfants")
    op.drop_column("store_employees", "nationalite")
    op.drop_column("store_employees", "situation_matrimoniale")
    op.drop_column("store_employees", "n_contribuable")
    op.drop_column("store_employees", "livret_cnss")
