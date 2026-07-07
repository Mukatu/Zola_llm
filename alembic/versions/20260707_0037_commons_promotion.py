"""Commons Phase C — rag_commons.documents + journal d'audit de promotion

Revision ID: 20260707_0037
Revises: 20260707_0036
Create Date: 2026-07-07

- rag_commons.documents : corpus RAG du savoir promu (schéma créé par le bootstrap ;
  app en lecture seule). Même DDL que les autres corpus (bge-m3 1024d, HNSW cosine).
- store_commons_audit : journal ANONYME des promotions (content_hash, cible,
  validateur, date) — aucune référence locataire.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import ARRAY, JSONB

revision: str = "20260707_0037"
down_revision: str | None = "20260707_0036"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EMBEDDING_DIM = 1024
SCHEMA = "rag_commons"


def upgrade() -> None:
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
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("char_length(content) > 0", name=f"ck_{SCHEMA}_doc_content"),
        sa.UniqueConstraint("source_uri", "chunk_index", name=f"uq_{SCHEMA}_doc_chunk"),
        schema=SCHEMA,
    )
    op.create_index(
        f"ix_{SCHEMA}_doc_tags_gin", "documents", ["tags"], schema=SCHEMA, postgresql_using="gin"
    )
    op.create_index(
        f"ix_{SCHEMA}_doc_metadata_gin",
        "documents",
        ["extra_metadata"],
        schema=SCHEMA,
        postgresql_using="gin",
    )
    op.create_index(
        f"ix_{SCHEMA}_doc_source", "documents", ["source_uri", "chunk_index"], schema=SCHEMA
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

    op.create_table(
        "store_commons_audit",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("target", sa.String(24), nullable=False),  # rag_commons | learned_rules
        sa.Column("domaine", sa.String(64), nullable=False, server_default=""),
        sa.Column("source_uri", sa.Text, nullable=True),
        sa.Column("validated_by", sa.String(120), nullable=True),
        sa.Column(
            "promoted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index(
        "ix_store_commons_audit_content_hash", "store_commons_audit", ["content_hash"]
    )


def downgrade() -> None:
    op.drop_index("ix_store_commons_audit_content_hash", table_name="store_commons_audit")
    op.drop_table("store_commons_audit")
    op.drop_index(f"ix_{SCHEMA}_doc_embedding_hnsw", table_name="documents", schema=SCHEMA)
    op.drop_index(f"ix_{SCHEMA}_doc_source", table_name="documents", schema=SCHEMA)
    op.drop_index(f"ix_{SCHEMA}_doc_metadata_gin", table_name="documents", schema=SCHEMA)
    op.drop_index(f"ix_{SCHEMA}_doc_tags_gin", table_name="documents", schema=SCHEMA)
    op.drop_table("documents", schema=SCHEMA)
