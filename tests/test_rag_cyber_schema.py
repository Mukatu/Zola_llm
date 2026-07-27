"""rag_cyber : câblage minimal du schéma RAG (corpus public standards cyber).

Corpus **public** (NIST CSF, OWASP, ANSSI, Loi 29-2019 CG) — hors PII, hors
SENSITIVE_SCHEMAS. Même patron de test que le câblage rag_fintech
(cf. tests/test_fintech.py::test_rag_fintech_wiring).
"""

from __future__ import annotations


def test_rag_cyber_wiring() -> None:
    from zolaos.db.models import RAG_MODELS, RagCyberDocument
    from zolaos.security.pii import SENSITIVE_SCHEMAS

    assert "rag_cyber" in RAG_MODELS
    assert RAG_MODELS["rag_cyber"] is RagCyberDocument
    assert "rag_cyber" not in SENSITIVE_SCHEMAS
