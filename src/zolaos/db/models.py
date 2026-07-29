"""Modèles SQLAlchemy — Phase 1.

Tables créées :
- core.users : utilisateurs applicatifs.
- core.api_keys : clés d'API par utilisateur.
- memory.entries : mémoire sémantique partagée (pgvector).

Toutes les tables portent un champ `country` (par défaut 'cg') pour préparer
l'extension multi-pays. Les schémas sont créés par 01_init_schemas.sql.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    ARRAY,
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from zolaos.db.base import Base

EMBEDDING_DIM = 1024  # bge-m3


# =============================================================================
# core schema
# =============================================================================
class Tenant(Base):
    """Entité logique (cabinet ou client) — Polaris-6.

    - `tenant_type='cabinet'` : entité opératrice (ex: Polaris). Peut être parent
      de plusieurs tenants `client`.
    - `tenant_type='client'` : entreprise cliente d'un cabinet. Le `parent_tenant_id`
      pointe vers le cabinet de référence (le cabinet qui a "onboardé" ce client).

    Le tag RBAC associé est `tenant:<type>:<name>` (ex: `tenant:cabinet:polaris`).
    """

    __tablename__ = "tenants"
    __table_args__ = (
        CheckConstraint(
            "tenant_type IN ('cabinet', 'client')",
            name="ck_tenants_type",
        ),
        CheckConstraint("char_length(country) = 2", name="ck_tenants_country_iso2"),
        {"schema": "core"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    tenant_type: Mapped[str] = mapped_column(String(16), nullable=False)
    parent_tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("core.tenants.id", ondelete="SET NULL"),
        nullable=True,
    )
    country: Mapped[str] = mapped_column(String(2), default="cg", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Adresse par laquelle le Cortex joint la Zolabox du client pour le RAG distant
    # (Zero Trust). En dev : URL directe. En prod (tunnel sortant) : endpoint local
    # au Cortex attribué au canal de la box. NULL = pas de box → retrieve local.
    box_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Credential par box (tunnel) : hash HMAC du secret présenté au handshake.
    # NULL = aucune box autorisée à se déclarer pour ce tenant. Révoquer = mettre à NULL.
    box_credential_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    box_credential_prefix: Mapped[str | None] = mapped_column(String(16), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("char_length(country) = 2", name="country_iso2"),
        {"schema": "core"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Rôle RBAC : admin | consultant | client. Le login en dérive les scopes JWT
    # (cf. zolaos.core.rbac). Défaut `consultant` (rattachement cabinet).
    role: Mapped[str] = mapped_column(String(20), default="consultant", nullable=False)
    country: Mapped[str] = mapped_column(String(2), default="cg", nullable=False)
    # `tenant_id` legacy : tag string libre. Conservé pour compatibilité ascendante
    # avec les RBAC tags existants. Le rattachement structuré passe par
    # `tenant_uuid` ci-dessous (ajouté Polaris-6).
    tenant_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    tenant_uuid: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("core.tenants.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    api_keys: Mapped[list[ApiKey]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    tenant: Mapped[Tenant | None] = relationship(foreign_keys=[tenant_uuid])


class ApiKey(Base):
    __tablename__ = "api_keys"
    __table_args__ = ({"schema": "core"},)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("core.users.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Hash HMAC-SHA256(pepper, key). La clé en clair n'est jamais stockée.
    key_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    # Prefix lisible (8 premiers caractères) pour identifier la clé dans les logs.
    key_prefix: Mapped[str] = mapped_column(String(16), nullable=False)
    label: Mapped[str] = mapped_column(String(100), nullable=False, default="default")
    scopes: Mapped[list[str]] = mapped_column(ARRAY(String), default=list, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped[User] = relationship(back_populates="api_keys")


class RefreshToken(Base):
    """Jeton de rafraîchissement (login navigateur).

    Opaque, à durée de vie longue (jours), stocké **haché** (SHA-256). Il permet
    de réémettre un access token JWT court sans redemander le mot de passe. La
    rotation révoque l'ancien à chaque usage : un jeton volé cesse de fonctionner
    dès le prochain refresh légitime (détection de rejeu possible en aval).
    """

    __tablename__ = "refresh_tokens"
    __table_args__ = ({"schema": "core"},)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("core.users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # SHA-256(token) en hexadécimal : le jeton clair n'est jamais stocké.
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Contexte d'émission (traçabilité / révocation ciblée d'une session).
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped[User] = relationship()


class Mission(Base):
    """Mission d'audit Polaris (Polaris-7).

    Une mission relie un consultant d'un tenant `cabinet` à un tenant `client`,
    avec un scope (offre + tags) et une fenêtre de validité. Le JWT mission
    émis pour le consultant porte `mission_id` en claim ; les requêtes
    Zolacortex → Zolabox vérifient que la mission est `active` et non expirée.

    Statuts : active | expired | revoked | completed.
    """

    __tablename__ = "missions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'expired', 'revoked', 'completed')",
            name="ck_missions_status",
        ),
        CheckConstraint(
            "cabinet_tenant_id != client_tenant_id",
            name="ck_missions_distinct_tenants",
        ),
        CheckConstraint(
            "expires_at > started_at",
            name="ck_missions_valid_window",
        ),
        {"schema": "core"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cabinet_tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("core.tenants.id", ondelete="RESTRICT"),
        nullable=False,
    )
    client_tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("core.tenants.id", ondelete="RESTRICT"),
        nullable=False,
    )
    offre: Mapped[str] = mapped_column(String(64), nullable=False)
    consultant_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("core.users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="active", nullable=False)
    scope_tags: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list, nullable=False)
    # Dernier audit exécuté (overlay Polaris) : {offre, query, synthese, findings,
    # citations, ran_at}. Sert de source au rapport .docx sans ré-exécuter le LLM.
    last_audit: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    cabinet: Mapped[Tenant] = relationship(foreign_keys=[cabinet_tenant_id])
    client: Mapped[Tenant] = relationship(foreign_keys=[client_tenant_id])


class LicenseGrant(Base):
    """Entitlement de modules émis par Polaris pour un tenant client (cockpit cortex).

    Persiste la licence **signée** (JWT RS256) et ses métadonnées, pour la gérer
    dans la durée : émettre, lister, révoquer, (re)livrer à la box. La box ne voit
    JAMAIS cette table — elle reçoit seulement le `token` (fichier ou tunnel) et le
    vérifie avec la clé publique. `license_id` = claim `jti` du jeton (unicité).

    Cycle de vie **dérivé** (pas une colonne d'état à maintenir) : `revoked`
    (revoked_at non nul) > `expired` (>= expires_at) > `active`. À l'émission d'une
    nouvelle licence pour un tenant, les précédentes actives sont révoquées : une
    seule licence vivante par tenant (modèle « renouvellement remplace »).
    """

    __tablename__ = "license_grants"
    __table_args__ = (
        CheckConstraint("expires_at > issued_at", name="ck_license_grants_window"),
        Index("ix_license_grants_tenant", "tenant_id", "revoked_at"),
        {"schema": "core"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("core.tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    # `jti` du jeton — identifiant humain/uuid unique de la licence.
    license_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    tier: Mapped[str] = mapped_column(String(20), nullable=False)
    # Options à la carte EN PLUS du tier (cf. modèle hybride). Modules effectifs
    # = tier ∪ options, recalculés à la lecture (jamais dénormalisés).
    modules: Mapped[list[str]] = mapped_column(ARRAY(String), default=list, nullable=False)
    # Jeton JWT signé (RS256) — le livrable déposé sur la box. Pas un secret au
    # sens strict (la box le vérifie avec la clé publique) mais réservé cortex+admin.
    token: Mapped[str] = mapped_column(Text, nullable=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Consultant/admin qui a émis la licence (traçabilité). SET NULL si le compte part.
    issued_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("core.users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    tenant: Mapped[Tenant] = relationship(foreign_keys=[tenant_id])


# NB : le journal d'audit du cabinet n'a PAS de modèle ORM ici — il est écrit dans
# la table canonique `audit.log` (schéma `audit`, chaîne de hachage + triggers
# d'immuabilité, cf. `infra/postgres/02_audit_log.sql`) via `zolaos.audit.recorder`,
# et lu en SQL par `api/v1/cortex_audit.py`. On NE réinvente PAS une table parallèle.


# =============================================================================
# memory schema
# =============================================================================
class MemoryEntry(Base):
    """Mémoire sémantique partagée.

    `tags` : liste de tags d'accès (`country:cg`, `tenant:xyz`, `health`, `legal:ohada`…).
    Le filtrage RBAC se fait par intersection de tags à la requête.
    """

    __tablename__ = "entries"
    __table_args__ = (
        CheckConstraint("char_length(content) > 0", name="content_not_empty"),
        Index("ix_entries_tags_gin", "tags", postgresql_using="gin"),
        Index(
            "ix_entries_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        {"schema": "memory"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM), nullable=False)
    tags: Mapped[list[str]] = mapped_column(ARRAY(String), default=list, nullable=False)
    source: Mapped[str | None] = mapped_column(String(200), nullable=True)
    extra_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


# =============================================================================
# RAG documents (Phase 2) — un schéma par pôle, distinction des modules via tags
# =============================================================================
def _rag_doc_table_args(schema: str) -> tuple:
    """Index + contraintes communs aux tables rag_*.documents."""
    return (
        CheckConstraint("char_length(content) > 0", name=f"ck_{schema}_doc_content"),
        UniqueConstraint("source_uri", "chunk_index", name=f"uq_{schema}_doc_chunk"),
        Index(f"ix_{schema}_doc_tags_gin", "tags", postgresql_using="gin"),
        Index(f"ix_{schema}_doc_metadata_gin", "extra_metadata", postgresql_using="gin"),
        Index(f"ix_{schema}_doc_source", "source_uri", "chunk_index"),
        Index(
            f"ix_{schema}_doc_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        {"schema": schema},
    )


class _RagDocumentMixin:
    """Colonnes communes aux tables rag_*.documents.

    Pas un Base SQLAlchemy : juste un mixin de colonnes (chaque table concrète
    déclare son `__tablename__` et son schéma via `__table_args__`).
    """

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source_uri: Mapped[str] = mapped_column(Text, nullable=False)
    source_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM), nullable=False)
    tags: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list, nullable=False)
    extra_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class RagHealthDocument(_RagDocumentMixin, Base):
    __tablename__ = "documents"
    __table_args__ = _rag_doc_table_args("rag_health")


class RagLegalDocument(_RagDocumentMixin, Base):
    __tablename__ = "documents"
    __table_args__ = _rag_doc_table_args("rag_legal")


class RagErpDocument(_RagDocumentMixin, Base):
    """Corpus RAG ERP : textes réglementaires comptables et fiscaux (AUDCIF, CGI, SYSCOHADA…).

    Schéma sensible (déclaré dans SENSITIVE_SCHEMAS) : la politique PII est
    obligatoire à l'ingestion (PIIRedactionPolicy.FISCAL recommandée pour les
    documents contenant des données de tiers comptables).
    """

    __tablename__ = "documents"
    __table_args__ = _rag_doc_table_args("rag_erp")


class RagTenantDocument(_RagDocumentMixin, Base):
    """Corpus RAG **du client** : documents téléversés (règlement intérieur,
    accords, chartes, contrats…), **cloisonnés par tenant** (tag ``tenant:<id>``).

    Contrairement aux corpus de référence (rag_legal/erp/health, en lecture seule
    pour l'app), ce schéma est **inscriptible par l'app** : le client gère ses
    propres documents. Schéma sensible → politique PII obligatoire à l'ingestion.
    """

    __tablename__ = "documents"
    __table_args__ = _rag_doc_table_args("rag_tenant")


class RagCommonsDocument(_RagDocumentMixin, Base):
    """Corpus RAG **du communs** (niveau 3) : savoir promu — anonymisé, partagé,
    validé humainement. **Lecture seule pour l'app** (comme les corpus de
    référence) ; écriture par le rôle d'administration lors de la promotion.
    Consulté par les agents en complément de la loi et des documents du client.
    """

    __tablename__ = "documents"
    __table_args__ = _rag_doc_table_args("rag_commons")


class RagFintechDocument(_RagDocumentMixin, Base):
    """Corpus RAG **réglementaire fintech** : microfinance (COBAC/EMF), LBC-FT
    (CEMAC/GABAC), Mobile Money (BEAC). Textes **publics** (pas de PII) → corpus
    de référence en lecture seule pour l'app. Ancre l'assistant du pôle fintech.
    """

    __tablename__ = "documents"
    __table_args__ = _rag_doc_table_args("rag_fintech")


class RagCyberDocument(_RagDocumentMixin, Base):
    """Corpus RAG **réglementaire/standards cyber** : NIST CSF, OWASP, ANSSI,
    Loi 29-2019 (CG). Textes **publics** (pas de PII) → hors SENSITIVE_SCHEMAS,
    corpus de référence en lecture seule pour l'app. Ancre l'overlay cyber Polaris.
    """

    __tablename__ = "documents"
    __table_args__ = _rag_doc_table_args("rag_cyber")


class RagCodeDocument(_RagDocumentMixin, Base):
    """Corpus RAG du **code DU CLIENT** (assistant code souverain, produit box).
    **Cloisonné par tenant** (tag `tenant:<id>`, source_uri `code://…`).
    Schéma **SENSIBLE** (code propriétaire du client) → dans SENSITIVE_SCHEMAS,
    politique PII obligatoire à l'ingestion. Lecture/écriture par le rôle
    `zolaos_code_agent` (indexation incrémentale du dépôt client).
    """

    __tablename__ = "documents"
    __table_args__ = _rag_doc_table_args("rag_code")


# Lookup pour code générique (pipeline ingest/retrieve qui prend un schéma).
RAG_MODELS: dict[str, type[Base]] = {
    "rag_health": RagHealthDocument,
    "rag_legal": RagLegalDocument,
    "rag_erp": RagErpDocument,
    "rag_tenant": RagTenantDocument,
    "rag_commons": RagCommonsDocument,
    "rag_fintech": RagFintechDocument,
    "rag_cyber": RagCyberDocument,
    "rag_code": RagCodeDocument,
}
