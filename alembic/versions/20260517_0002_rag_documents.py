"""rag tables: rag_health.documents + rag_legal.documents (multi-module via tags)

Revision ID: 20260517_0002
Revises: 20260515_0001
Create Date: 2026-05-17

Décision design : un seul schéma par pôle (rag_health, rag_legal), pas un schéma
par module. Les modules juridiques (ohada, travail_cg, fiscal_cg) sont
différenciés via le tag `module:<name>`. Avantages :
- Permissions inchangées quand on ajoute un module (le rôle zolaos_legal_agent
  voit tout le schéma rag_legal, le filtre tags fait le RBAC fonctionnel).
- Pas de migration à chaque nouveau module.
- Possibilité de requêtes cross-modules (ex: chercher dans OHADA + travail_cg).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import ARRAY, JSONB

revision: str = "20260517_0002"
down_revision: str | None = "20260515_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EMBEDDING_DIM = 1024
RAG_SCHEMAS = ("rag_health", "rag_legal")


def upgrade() -> None:
    for schema in RAG_SCHEMAS:
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
            sa.CheckConstraint("char_length(content) > 0", name=f"ck_{schema}_doc_content"),
            sa.UniqueConstraint("source_uri", "chunk_index", name=f"uq_{schema}_doc_chunk"),
            schema=schema,
        )
        op.create_index(
            f"ix_{schema}_doc_tags_gin",
            "documents",
            ["tags"],
            schema=schema,
            postgresql_using="gin",
        )
        op.create_index(
            f"ix_{schema}_doc_metadata_gin",
            "documents",
            ["extra_metadata"],
            schema=schema,
            postgresql_using="gin",
        )
        op.create_index(
            f"ix_{schema}_doc_source",
            "documents",
            ["source_uri", "chunk_index"],
            schema=schema,
        )
        op.create_index(
            f"ix_{schema}_doc_embedding_hnsw",
            "documents",
            ["embedding"],
            schema=schema,
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        )


def downgrade() -> None:
    for schema in RAG_SCHEMAS:
        op.drop_index(f"ix_{schema}_doc_embedding_hnsw", table_name="documents", schema=schema)
        op.drop_index(f"ix_{schema}_doc_source", table_name="documents", schema=schema)
        op.drop_index(f"ix_{schema}_doc_metadata_gin", table_name="documents", schema=schema)
        op.drop_index(f"ix_{schema}_doc_tags_gin", table_name="documents", schema=schema)
        op.drop_table("documents", schema=schema)
