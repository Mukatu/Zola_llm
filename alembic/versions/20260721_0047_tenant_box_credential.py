"""tenants.box_credential : credential par box pour le tunnel (mTLS applicatif)

Revision ID: 20260721_0047
Revises: 20260720_0046
Create Date: 2026-07-21

Durcissement P-A.2 : chaque box s'authentifie au tunnel avec un credential UNIQUE
(haché HMAC), au lieu d'un secret partagé. Révocable individuellement (NULL = révoqué).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260721_0047"
down_revision: str | None = "20260720_0046"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("tenants", sa.Column("box_credential_hash", sa.String(128), nullable=True), schema="core")
    op.add_column("tenants", sa.Column("box_credential_prefix", sa.String(16), nullable=True), schema="core")


def downgrade() -> None:
    op.drop_column("tenants", "box_credential_prefix", schema="core")
    op.drop_column("tenants", "box_credential_hash", schema="core")
