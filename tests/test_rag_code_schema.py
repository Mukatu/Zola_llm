"""rag_code : câblage minimal du schéma RAG (corpus code du client, sensible).

Corpus du **code DU CLIENT** (assistant code souverain, produit box),
cloisonné par tenant. À la différence de rag_cyber (public), rag_code est
**SENSIBLE** (code propriétaire du client) → doit figurer dans
SENSITIVE_SCHEMAS. Même patron de test que le câblage rag_cyber
(cf. tests/test_rag_cyber_schema.py).
"""

from __future__ import annotations


def test_rag_code_wiring() -> None:
    from zolaos.db.models import RAG_MODELS, RagCodeDocument
    from zolaos.security.pii import SENSITIVE_SCHEMAS

    assert "rag_code" in RAG_MODELS
    assert RAG_MODELS["rag_code"] is RagCodeDocument
    assert "rag_code" in SENSITIVE_SCHEMAS
