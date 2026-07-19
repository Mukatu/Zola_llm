"""Preuve que `RAGAgent._format_context` labellise distinctement les extraits
issus du corpus TENANT (documents internes du client) pour qu'ils ne soient
jamais confondus avec le droit applicable — cf. incident pilote « préavis de
licenciement secteur bancaire » où le Règlement Intérieur (RI-2024, cadres
uniquement) avait contaminé la réponse sur la loi.
"""

from __future__ import annotations

from zolaos.agents.rag_agent import RAGAgent
from zolaos.rag.retrieval import Match


def _match(
    *,
    source_id: str,
    source_uri: str,
    tags: list[str],
    content: str = "Texte de l'extrait.",
    sim: float = 0.8,
) -> Match:
    return Match(
        content=content,
        score=1.0 - sim,
        source_uri=source_uri,
        source_id=source_id,
        chunk_index=0,
        tags=tags,
        extra_metadata={},
    )


def _legal_match() -> Match:
    """Extrait du corpus de référence (loi) : ni tag ni source_uri tenant."""
    return _match(
        source_id="code_travail_art_45",
        source_uri="https://officiel.example/code_travail.pdf",
        tags=["country:cg", "legal:ohada"],
        content="Le préavis de licenciement est fixé selon l'ancienneté du salarié.",
    )


def _tenant_match_by_tag() -> Match:
    """Extrait tenant identifié par son tag `tenant:<id>`."""
    return _match(
        source_id="RI-2024",
        source_uri="https://storage.example/uploads/ri-2024.pdf",
        tags=["country:cg", "tenant:acme-bank"],
        content="Le préavis d'un cadre est de 3 mois.",
    )


def _tenant_match_by_source_uri() -> Match:
    """Extrait tenant identifié uniquement via son `source_uri` tenant://…

    Reproduit le chemin MissionClient (Cortex → Box) où seul `source_uri` est
    garanti disponible pour distinguer l'origine, cf. `_do_retrieve`.
    """
    return _match(
        source_id=None,
        source_uri="tenant://acme-bank/rh/reglement_interieur/ri-2024.pdf",
        tags=["country:cg"],
        content="Le préavis d'un cadre est de 3 mois.",
    )


def test_is_tenant_match_detects_tag_and_source_uri() -> None:
    assert RAGAgent._is_tenant_match(_tenant_match_by_tag()) is True
    assert RAGAgent._is_tenant_match(_tenant_match_by_source_uri()) is True
    assert RAGAgent._is_tenant_match(_legal_match()) is False


def test_format_context_labels_tenant_extract_and_spares_legal_one() -> None:
    matches = [_legal_match(), _tenant_match_by_tag()]

    context = RAGAgent._format_context(matches)

    label = "[RÈGLE INTERNE DE L'ENTREPRISE — non légale, à ne pas confondre avec la loi]"
    # Le label n'apparaît qu'une fois : uniquement devant l'extrait tenant.
    assert context.count(label) == 1

    # L'extrait légal [1] n'est PAS labellisé « règle interne ».
    legal_block = context.split("[1]", 1)[1].split("[2]", 1)[0]
    assert label not in legal_block

    # L'extrait tenant [2] est labellisé.
    tenant_block = context.split("[2]", 1)[1]
    assert label in tenant_block


def test_format_context_labels_tenant_extract_detected_via_source_uri() -> None:
    context = RAGAgent._format_context([_tenant_match_by_source_uri()])
    assert "[RÈGLE INTERNE DE L'ENTREPRISE" in context


def test_format_context_numbering_stays_contiguous_regardless_of_origin() -> None:
    """La numérotation [1], [2]… reste continue — pas de renumérotation ni
    d'exclusion des extraits tenant, seule la présentation change."""
    matches = [_legal_match(), _tenant_match_by_tag(), _legal_match()]
    context = RAGAgent._format_context(matches)
    assert "[1]" in context
    assert "[2]" in context
    assert "[3]" in context


def test_format_context_no_tenant_matches_unchanged() -> None:
    """Rétro-compatibilité : sans extrait tenant, aucun marqueur n'apparaît."""
    context = RAGAgent._format_context([_legal_match()])
    assert "RÈGLE INTERNE" not in context


def test_format_context_empty_matches_unchanged() -> None:
    context = RAGAgent._format_context([])
    assert context == "--- Textes de référence ---\n(aucun extrait disponible)"
