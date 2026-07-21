"""users.role : rôle RBAC (admin | consultant | client) — scopes dérivés au login

Revision ID: 20260719_0044
Revises: 20260719_0043
Create Date: 2026-07-19

Le login projette le rôle en scopes JWT (cf. zolaos.core.rbac). Colonne NOT NULL
avec défaut `consultant` : les comptes existants sont rattachés au cabinet.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260719_0044"
down_revision: str | None = "20260719_0043"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("role", sa.String(20), nullable=False, server_default="consultant"),
        schema="core",
    )
    op.create_check_constraint(
        "users_role_valid",
        "users",
        "role IN ('admin', 'consultant', 'client')",
        schema="core",
    )


def downgrade() -> None:
    op.drop_constraint("users_role_valid", "users", schema="core", type_="check")
    op.drop_column("users", "role", schema="core")
