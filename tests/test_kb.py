"""Bibliothèque documentaire — logique de filtrage / étiquetage (sans DB)."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from zolaos.api.v1.kb import KbSearchIn, _model, _required_tags, _titre


def test_required_tags() -> None:
    assert _required_tags("cg", None, None, None) == ["country:cg"]
    assert _required_tags("cg", "ohada", None, "AUDCIF") == [
        "country:cg",
        "module:ohada",
        "acte:AUDCIF",
    ]
    assert "secteur:banque" in _required_tags("cg", "travail_cg", "banque", None)


def test_titre_fallback() -> None:
    assert _titre({"titre": "Article 5"}, "x") == "Article 5"
    assert _titre({"acte_nom": "AUDCIF"}, "x") == "AUDCIF"
    assert _titre({}, "src-1") == "src-1"
    assert _titre(None, None) is None


def test_model_unknown_schema_raises_404() -> None:
    with pytest.raises(HTTPException) as exc:
        _model("rag_inexistant")
    assert exc.value.status_code == 404


def test_kb_search_schema_alias() -> None:
    body = KbSearchIn(q="tva", schema="rag_erp")  # 'schema' est un alias de schema_rag
    assert body.schema_rag == "rag_erp"
    assert body.k == 8


def test_rag_tenant_registered_and_sensitive() -> None:
    from zolaos.db.models import RAG_MODELS
    from zolaos.security.pii import SENSITIVE_SCHEMAS

    assert "rag_tenant" in RAG_MODELS
    assert "rag_tenant" in SENSITIVE_SCHEMAS  # PII obligatoire à l'ingestion


def test_kb_upload_defaults() -> None:
    from zolaos.api.v1.kb import KbUploadIn

    b = KbUploadIn(
        filename="ri.pdf",
        content_b64="eA==",
        module="travail_cg",
        doctype="reglement_interieur",
    )
    # Le tenant n'est plus dans le corps : il est dérivé de l'auth (current_tenant).
    assert not hasattr(b, "tenant_id")
    assert b.pii == "none"


async def test_current_tenant_derives_from_principal() -> None:
    import uuid

    from zolaos.api.auth import Principal, current_tenant

    p = Principal(
        user_id=uuid.uuid4(), email="a@b.c", tenant_id="acme", country="cg", auth_method="jwt"
    )
    assert await current_tenant(p) == "acme"

    anon = Principal(
        user_id=uuid.uuid4(), email="a@b.c", tenant_id=None, country="cg", auth_method="jwt"
    )
    assert await current_tenant(anon) == "local"


def test_tenant_filter_read_scoping() -> None:
    import uuid

    from fastapi import HTTPException

    from zolaos.api.auth import Principal
    from zolaos.api.v1.kb import _tenant_filter

    # Corpus de référence : consultable sans compte (aucun filtre tenant).
    assert _tenant_filter("rag_legal", None) is None

    # Corpus privé sans identité → 401.
    with pytest.raises(HTTPException) as exc:
        _tenant_filter("rag_tenant", None)
    assert exc.value.status_code == 401

    # Corpus privé avec identité → borné à son tenant.
    p = Principal(
        user_id=uuid.uuid4(), email="a@b.c", tenant_id="acme", country="cg", auth_method="jwt"
    )
    assert _tenant_filter("rag_tenant", p) == "acme"
