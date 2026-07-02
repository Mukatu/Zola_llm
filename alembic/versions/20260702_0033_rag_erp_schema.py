"""rag_erp : schéma + table documents + index vectoriel (corpus ERP — AUDCIF, CGI, SYSCOHADA)

Revision ID: 20260702_0033
Revises: 20260701_0031
Create Date: 2026-07-02

Décision design : même patron que rag_health / rag_legal (migration 20260517_0002).
- Un seul schéma `rag_erp` pour tous les modules ERP comptables/fiscaux.
- Les modules (AUDCIF, CGI, SYSCOHADA, OHADA-compta…) sont différenciés par le
  tag `module:<name>` à l'ingestion.
- Schéma déclaré sensible (SENSITIVE_SCHEMAS dans pii.py) : politique PII
  obligatoire à l'ingestion, PIIRedactionPolicy.FISCAL recommandée.
- Index HNSW ivfflat cosine identique aux autres schémas RAG (bge-m3, 1024d).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import ARRAY, JSONB

revision: str = "20260702_0033"
down_revision: str | None = "20260701_0031"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EMBEDDING_DIM = 1024
SCHEMA = "rag_erp"


def upgrade() -> None:
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")
    op.create_table(
        "documents",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("source_uri", sa.Text, nullable=False),
        sa.Column("source_id", sa.String(200), nullable=True),
        sa.Column("chunk_index", sa.Integer, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("content_tokens", sa.Integer, nullable=True),
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=False),
        sa.Column("tags", ARRAY(sa.Text), nullable=False, server_default="{}"),
        sa.Column("extra_metadata", JSONB, nullable=False, server_default="{}"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "char_length(content) > 0", name=f"ck_{SCHEMA}_doc_content"
        ),
        sa.UniqueConstraint(
            "source_uri", "chunk_index", name=f"uq_{SCHEMA}_doc_chunk"
        ),
        schema=SCHEMA,
    )
    op.create_index(
        f"ix_{SCHEMA}_doc_tags_gin",
        "documents",
        ["tags"],
        schema=SCHEMA,
        postgresql_using="gin",
    )
    op.create_index(
        f"ix_{SCHEMA}_doc_metadata_gin",
        "documents",
        ["extra_metadata"],
        schema=SCHEMA,
        postgresql_using="gin",
    )
    op.create_index(
        f"ix_{SCHEMA}_doc_source",
        "documents",
        ["source_uri", "chunk_index"],
        schema=SCHEMA,
    )
    op.create_index(
        f"ix_{SCHEMA}_doc_embedding_hnsw",
        "documents",
        ["embedding"],
        schema=SCHEMA,
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 64},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )


def downgrade() -> None:
    op.drop_index(
        f"ix_{SCHEMA}_doc_embedding_hnsw", table_name="documents", schema=SCHEMA
    )
    op.drop_index(
        f"ix_{SCHEMA}_doc_source", table_name="documents", schema=SCHEMA
    )
    op.drop_index(
        f"ix_{SCHEMA}_doc_metadata_gin", table_name="documents", schema=SCHEMA
    )
    op.drop_index(
        f"ix_{SCHEMA}_doc_tags_gin", table_name="documents", schema=SCHEMA
    )
    op.drop_table("documents", schema=SCHEMA)
    op.execute(f"DROP SCHEMA IF EXISTS {SCHEMA}")
