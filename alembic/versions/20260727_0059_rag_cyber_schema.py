"""rag_cyber : schéma + table documents + index vectoriel (corpus standards cyber)

Revision ID: 20260727_0059
Revises: 20260724_0058
Create Date: 2026-07-27

Corpus **public** (NIST CSF, OWASP, ANSSI, Loi 29-2019 CG) : hors
SENSITIVE_SCHEMAS (pas de PII), lecture seule pour l'app. Même patron que
rag_fintech (20260708_0042). La migration crée le schéma (idempotent) pour
fonctionner aussi sur les bases existantes où le bootstrap n'a pas rejoué.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import ARRAY, JSONB

revision: str = "20260727_0059"
down_revision: str | None = "20260724_0058"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EMBEDDING_DIM = 1024
SCHEMA = "rag_cyber"


def upgrade() -> None:
    # Le schéma `rag_cyber` est créé par le bootstrap (01_init_schemas.sql) ou,
    # sur une base existante, manuellement en superutilisateur (le rôle migrator
    # n'a pas le privilège CREATE SCHEMA). Alembic ne gère que la table interne.
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


def downgrade() -> None:
    op.drop_index(f"ix_{SCHEMA}_doc_embedding_hnsw", table_name="documents", schema=SCHEMA)
    op.drop_index(f"ix_{SCHEMA}_doc_source", table_name="documents", schema=SCHEMA)
    op.drop_index(f"ix_{SCHEMA}_doc_metadata_gin", table_name="documents", schema=SCHEMA)
    op.drop_index(f"ix_{SCHEMA}_doc_tags_gin", table_name="documents", schema=SCHEMA)
    op.drop_table("documents", schema=SCHEMA)
