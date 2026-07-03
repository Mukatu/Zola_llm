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
