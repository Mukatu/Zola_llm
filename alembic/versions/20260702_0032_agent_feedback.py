"""Boucle de feedback agents — table store_agent_feedback

Revision ID: 20260702_0032
Revises: 20260701_0031
Create Date: 2026-07-02
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260702_0032"
down_revision: str | None = "20260701_0031"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "store_agent_feedback",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False, server_default="local"),
        sa.Column("request_id", sa.String(64), nullable=True),
        sa.Column("agent", sa.String(64), nullable=False),
        sa.Column("query", sa.Text, nullable=False),
        sa.Column("response", sa.Text, nullable=False),
        sa.Column("verdict", sa.String(4), nullable=False),
        sa.Column("correction", sa.Text, nullable=True),
        sa.Column("context_snapshot", sa.JSON, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_store_agent_feedback_tenant_id", "store_agent_feedback", ["tenant_id"])
    op.create_index("ix_store_agent_feedback_request_id", "store_agent_feedback", ["request_id"])


def downgrade() -> None:
    op.drop_index("ix_store_agent_feedback_request_id", table_name="store_agent_feedback")
    op.drop_index("ix_store_agent_feedback_tenant_id", table_name="store_agent_feedback")
    op.drop_table("store_agent_feedback")
