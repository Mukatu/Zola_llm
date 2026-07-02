"""Tests RAG ERP — corpus rag_erp (AUDCIF, CGI, SYSCOHADA).

Trois niveaux de tests :
1. Unitaire pur (sans DB) : rag_erp ∈ RAG_MODELS.
2. Unitaire pur (sans DB) : require_policy_for_ingest lève si pii_policy=None.
3. Intégration (avec pgvector/Postgres) : ingest_text puis retrieve renvoie ≥ 1 match.

Les tests 1 et 2 s'exécutent TOUJOURS (pas de dépendance DB/pgvector).
Le test 3 est sauté automatiquement si Postgres est indisponible.
"""

from __future__ import annotations

import asyncio
import os

import pytest

from zolaos.db.models import RAG_MODELS
from zolaos.security.pii import PIIRedactionPolicy, require_policy_for_ingest

# ---------------------------------------------------------------------------
# Détection DB disponible (utilisée par le test d'intégration uniquement)
# ---------------------------------------------------------------------------


def _postgres_disponible() -> bool:
    """Vérifie si Postgres est accessible avec les settings courants.

    Tente une connexion asyncpg rapide (timeout 1 s). Retourne False en cas
    d'échec (DB absente, pgvector non installé, etc.).
    """
    try:
        import asyncpg

        from zolaos.core.settings import get_settings

        settings = get_settings()
        dsn = settings.postgres_dsn_migrations.replace("postgresql+psycopg", "postgresql").replace(
            "postgresql+asyncpg", "postgresql"
        )

        async def _ping() -> bool:
            conn = await asyncio.wait_for(asyncpg.connect(dsn), timeout=1.0)
            await conn.close()
            return True

        return asyncio.run(_ping())
    except Exception:
        return False


_DB_DISPO = _postgres_disponible()


# ---------------------------------------------------------------------------
# 1. Test unitaire — rag_erp doit être enregistré dans RAG_MODELS
# ---------------------------------------------------------------------------


def test_rag_erp_dans_rag_models() -> None:
    """rag_erp doit être un schéma RAG de première classe (aucune DB requise)."""
    assert (
        "rag_erp" in RAG_MODELS
    ), f"rag_erp absent de RAG_MODELS. Schémas enregistrés : {list(RAG_MODELS)}"
    # Le modèle doit posséder les colonnes standard RAG
    model = RAG_MODELS["rag_erp"]
    colonnes = {c.key for c in model.__table__.columns}
    for col_attendue in ("id", "source_uri", "chunk_index", "content", "embedding", "tags"):
        assert col_attendue in colonnes, f"Colonne {col_attendue!r} manquante dans RagErpDocument"
    # Le schéma PostgreSQL déclaré doit être rag_erp
    assert model.__table__.schema == "rag_erp"


# ---------------------------------------------------------------------------
# 2. Test unitaire — schéma sensible : pii_policy=None doit lever ValueError
# ---------------------------------------------------------------------------


def test_require_policy_leve_pour_rag_erp_sans_politique() -> None:
    """require_policy_for_ingest doit rejeter rag_erp si pii_policy est None (aucune DB requise)."""
    with pytest.raises(ValueError, match="sensible"):
        require_policy_for_ingest("rag_erp", None)


def test_require_policy_accepte_policy_none_explicite() -> None:
    """PIIRedactionPolicy.NONE (corpus public) est accepté — c'est un choix conscient."""
    policy = require_policy_for_ingest("rag_erp", PIIRedactionPolicy.NONE)
    assert policy == PIIRedactionPolicy.NONE


def test_require_policy_accepte_policy_fiscal() -> None:
    """PIIRedactionPolicy.FISCAL (tiers hashés) est la politique recommandée pour ERP."""
    policy = require_policy_for_ingest("rag_erp", PIIRedactionPolicy.FISCAL)
    assert policy == PIIRedactionPolicy.FISCAL


# ---------------------------------------------------------------------------
# 3. Test d'intégration — ingest puis retrieve (sauté si DB indisponible)
# ---------------------------------------------------------------------------


class _FakeEmbeddings:
    """Service d'embeddings déterministe (1024d) — évite de charger bge-m3.

    Toute la stack RAG du repo mocke les embeddings dans les tests (cf.
    `test_erp_rh.py`). Ici on injecte un faux service directement (ingest_text et
    retrieve acceptent tous deux `embeddings=`), ce qui exerce le VRAI pgvector
    sur `rag_erp.documents` sans dépendre du modèle lourd.
    """

    _DIM = 1024

    async def aencode(self, texts: list[str]) -> list[list[float]]:
        return [[0.1] * self._DIM for _ in texts]

    async def aencode_one(self, text: str) -> list[float]:
        _ = text
        return [0.1] * self._DIM


@pytest.mark.integration
@pytest.mark.skipif(
    not (_DB_DISPO and os.getenv("ZOLAOS_RUN_RAG_INTEGRATION") == "1"),
    reason=(
        "Intégration RAG lourde : nécessite pgvector ET une stack RAG provisionnée "
        "(rôle d'ingestion avec INSERT sur rag_*, service d'embeddings). "
        "Activer avec ZOLAOS_RUN_RAG_INTEGRATION=1."
    ),
)
@pytest.mark.asyncio
async def test_ingest_puis_retrieve_rag_erp() -> None:
    """Injecte un chunk ERP et vérifie qu'on le retrouve via pgvector (embeddings mockés)."""
    from zolaos.db.session import reset_engine_cache
    from zolaos.rag.ingest import ingest_text
    from zolaos.rag.retrieval import retrieve

    fake = _FakeEmbeddings()
    reset_engine_cache()
    try:
        # Texte fictif AUDCIF — suffisamment long pour être chunké
        texte_erp = (
            "Article 5 — Tenue de la comptabilité. "
            "Toute entité soumise à l'AUDCIF doit tenir une comptabilité régulière "
            "selon le plan comptable SYSCOHADA révisé. "
            "Les livres comptables obligatoires sont le journal général, "
            "le grand-livre et la balance générale des comptes. "
            "Ces documents doivent être conservés pendant dix (10) ans. "
            "Art. 6 — Les états financiers annuels comprennent le bilan, "
            "le compte de résultat et les notes annexes. "
        )
        source = "test://rag_erp/audcif_art5_integration"
        tags = ["country:cg", "module:audcif", "corpus:erp"]

        n_inseres = await ingest_text(
            text=texte_erp,
            source_uri=source,
            schema="rag_erp",
            tags=tags,
            pii_policy=PIIRedactionPolicy.FISCAL,
            embeddings=fake,  # type: ignore[arg-type]
        )
        # Au moins un chunk doit avoir été inséré (ou déjà présent si idempotent)
        assert n_inseres >= 0, "ingest_text a retourné une valeur négative"

        # Recherche par similarité
        matches = await retrieve(
            query="tenue comptabilité SYSCOHADA états financiers",
            schema="rag_erp",
            required_tags=["country:cg"],
            k=5,
            embeddings=fake,  # type: ignore[arg-type]
        )
        assert len(matches) >= 1, "retrieve n'a retourné aucun résultat sur rag_erp après ingestion"
        # Le meilleur match doit contenir du contenu ERP
        contenus = " ".join(m.content for m in matches)
        assert any(
            mot in contenus.lower()
            for mot in ("comptabilité", "syscohada", "audcif", "journal", "bilan")
        ), f"Aucun mot-clé ERP attendu dans les résultats : {contenus[:200]}"
    finally:
        reset_engine_cache()
