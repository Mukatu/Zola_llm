"""refresh_tokens : jetons de rafraîchissement (login navigateur, cookies httpOnly)

Revision ID: 20260719_0043
Revises: 20260708_0042
Create Date: 2026-07-19

Auth de production : le login vérifie email + mot de passe (bcrypt) et émet un
access token JWT court + un refresh token opaque, stocké **haché** ici. La
rotation à chaque refresh révoque l'ancien (défense anti-rejeu).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260719_0043"
down_revision: str | None = "20260708_0042"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("core.users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("user_agent", sa.String(255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("token_hash", name="uq_refresh_tokens_token_hash"),
        schema="core",
    )
    op.create_index(
        "ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"], schema="core"
    )
    op.create_index(
        "ix_refresh_tokens_token_hash", "refresh_tokens", ["token_hash"], schema="core"
    )


def downgrade() -> None:
    op.drop_index("ix_refresh_tokens_token_hash", table_name="refresh_tokens", schema="core")
    op.drop_index("ix_refresh_tokens_user_id", table_name="refresh_tokens", schema="core")
    op.drop_table("refresh_tokens", schema="core")
