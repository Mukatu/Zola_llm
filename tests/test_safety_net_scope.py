"""Filet de rattrapage à DEUX ÉTAGES — portée du balayage inter-domaines.

Régression protégée : le filet SUR-RATTRAPAIT. Il balayait TOUS les corpus
publics et prenait le meilleur par similarité — mais bge-m3 comprime les
similarités (~0.5 pour tout texte français), donc il ancrait sur un corpus
TANGENTIEL. Cas réel : « mentions obligatoires des statuts d'une SARL OHADA »
(routé legal) → le corpus ohada échoue → le filet citait de la LBC-FT CEMAC
(rag_fintech). Citer de la LBC-FT pour du droit des sociétés est pire qu'une
abstention.

Design corrigé, deux étages :
  1. Étage 1 (domaine d'origine) : balaie d'abord le seul schéma « maison » du
     pôle routé, au seuil normal de l'agent (min_confidence = 0.5). Prioritaire.
  2. Étage 2 (inter-domaines) : SEULEMENT si l'étage 1 échoue, balaie les autres
     schémas avec une BARRE PLUS HAUTE (0.60) — bloque les matches tangentiels
     faibles, laisse passer une vraie erreur de routage à match fort.

Les similarités des `Match` sont contrôlées (mock de `retrieve_multi`) pour
prouver chaque branche sans dépendre du corpus réel.
"""

from __future__ import annotations

import pytest

from zolaos.agents import rag_agent as rag_agent_mod
from zolaos.agents.router import Pole, RouteDecision
from zolaos.core import orchestrator as orch_mod
from zolaos.core.orchestrator import Orchestrator
from zolaos.core.settings import Settings
from zolaos.llm.base import GenerationResult, LLMClient
from zolaos.rag.retrieval import Match

pytestmark = pytest.mark.asyncio


class _FakeClient(LLMClient):
    """Modèle factice : renvoie un texte fixe quand (et seulement si) on l'appelle."""

    provider = "fake"

    async def generate(self, messages, *, model, options=None):  # type: ignore[no-untyped-def]
        _ = messages, model, options
        return GenerationResult(content="Réponse ancrée [1].", model="fake", provider=self.provider)

    async def stream(self, messages, *, model, options=None):  # type: ignore[no-untyped-def]
        _ = messages, model, options
        yield "Réponse ancrée [1]."

    async def health(self) -> bool:
        return True


def _settings() -> Settings:
    return Settings(
        APP_ENV="dev",
        POSTGRES_PASSWORD_APP="x",
        POSTGRES_PASSWORD_MIGRATIONS="x",
        JWT_SECRET="x" * 32,
    )


def _orchestrator(decision: RouteDecision, monkeypatch) -> Orchestrator:
    orch = Orchestrator.from_clients(
        router_client=_FakeClient(),
        core_client=_FakeClient(),
        settings=_settings(),
    )

    async def fake_classify(_query: str) -> RouteDecision:
        return decision

    monkeypatch.setattr(orch._router, "classify", fake_classify)

    # Le retrieve DIRECT des agents (agent du pôle routé + union communs/tenant
    # des agents génériques) ne trouve rien : on force ainsi le passage par le
    # filet, et on empêche tout accès à la vraie base pendant le test.
    async def empty_retrieve(*, query, schema, required_tags, k):  # type: ignore[no-untyped-def]
        _ = query, schema, required_tags, k
        return []

    monkeypatch.setattr(rag_agent_mod, "retrieve", empty_retrieve)
    return orch


def _match(source_id: str, sim: float) -> Match:
    """Match RAG factice de similarité `sim` (score = 1 - sim)."""
    return Match(
        content=f"Texte réglementaire {source_id} — disposition pertinente.",
        score=1.0 - sim,
        source_uri=f"https://officiel.example/{source_id}.pdf",
        source_id=source_id,
        chunk_index=0,
        tags=["country:cg"],
        extra_metadata={},
    )


def _mock_multi(monkeypatch, mapping: dict[str, list[Match]]) -> dict[str, bool]:
    """Mocke `retrieve_multi` pour renvoyer `mapping`. Retourne un témoin d'appel."""
    called = {"multi": False}

    async def multi(*, query, schemas, required_tags, k):  # type: ignore[no-untyped-def]
        _ = query, schemas, required_tags, k
        called["multi"] = True
        return mapping

    monkeypatch.setattr(orch_mod, "retrieve_multi", multi)
    return called


# --------------------------------------------------------------------------- #
# Étage 1 prioritaire : le schéma maison gagne, même si un autre est plus haut. #
# --------------------------------------------------------------------------- #


async def test_stage1_home_schema_wins_over_higher_cross_domain(monkeypatch) -> None:
    """Le cas OHADA : routé legal, le corpus maison (rag_legal) passe le seuil →
    on l'ancre, MÊME si rag_fintech affiche une similarité brute plus élevée.
    Preuve : plus jamais de citation fintech pour du droit des sociétés."""
    _mock_multi(
        monkeypatch,
        {
            "rag_legal": [_match("ohada_auscoop_art68", sim=0.55)],  # maison, passe 0.5
            "rag_fintech": [_match("cemac_lbcft_2016", sim=0.70)],  # tangentiel, plus HAUT
        },
    )
    decision = RouteDecision(pole=Pole.LEGAL, module="ohada", confidence=0.9, complexity="simple")
    result = await _orchestrator(decision, monkeypatch).handle(
        "mentions obligatoires des statuts d'une SARL OHADA"
    )

    resp = result.responses[0]
    assert resp.grounding == "sourced"
    assert resp.rag_schema == "rag_legal"  # domaine d'origine, prioritaire
    assert resp.rag_schema != "rag_fintech"  # la sur-rattrape est morte


# --------------------------------------------------------------------------- #
# Étage 2 : seulement si étage 1 échoue, et seulement sur match FORT.          #
# --------------------------------------------------------------------------- #


async def test_stage2_rescues_true_misroute_when_home_fails(monkeypatch) -> None:
    """Le cas TVA : routé à tort vers fintech, le corpus maison (rag_fintech)
    est sous le seuil → étage 1 échoue → étage 2 retrouve le corpus fiscal
    (rag_legal) à match fort (0.69 > barre 0.60) et rattrape."""
    _mock_multi(
        monkeypatch,
        {
            "rag_fintech": [_match("cemac_paiement_2018", sim=0.45)],  # maison, < 0.5 → échoue
            "rag_legal": [_match("recueil_fiscal_lf2023", sim=0.69)],  # fort, inter-domaine
        },
    )
    decision = RouteDecision(pole=Pole.FINTECH, module=None, confidence=0.9, complexity="simple")
    result = await _orchestrator(decision, monkeypatch).handle("taux de la TVA au Congo")

    resp = result.responses[0]
    assert resp.grounding == "sourced"
    assert resp.rag_schema == "rag_legal"  # rattrapage inter-domaines réussi


async def test_stage2_blocks_weak_tangential_match(monkeypatch) -> None:
    """Étage 1 sans schéma maison disponible + seul un match inter-domaine FAIBLE
    (0.55 < barre 0.60) → l'étage 2 le bloque. Abstention plutôt que citer un
    corpus tangentiel. Ici pôle grc (maison rag_legal absente du résultat)."""
    _mock_multi(
        monkeypatch,
        {"rag_fintech": [_match("cemac_lbcft_2016", sim=0.55)]},  # tangentiel, sous la barre
    )
    decision = RouteDecision(pole=Pole.GRC, module=None, confidence=0.9, complexity="simple")
    result = await _orchestrator(decision, monkeypatch).handle(
        "question de droit des sociétés mal routée"
    )

    # grc n'a pas d'agent RAG (non réglementé) → repli brigade, non sourcé.
    resp = result.responses[0]
    assert resp.grounding == "unsourced"
    assert resp.rag_schema is None
    assert resp.citations == ()


async def test_stage2_only_runs_after_stage1_fails(monkeypatch) -> None:
    """Quand l'étage 1 (maison) réussit, l'étage 2 ne prend jamais la main : un
    match inter-domaine plus fort ET au-dessus de la barre est ignoré."""
    _mock_multi(
        monkeypatch,
        {
            "rag_health": [_match("lnme_cg_2016", sim=0.52)],  # maison santé, passe 0.5
            "rag_legal": [_match("recueil_fiscal", sim=0.80)],  # plus fort + > barre, mais ignoré
        },
    )
    decision = RouteDecision(pole=Pole.HEALTH, module=None, confidence=0.9, complexity="simple")
    result = await _orchestrator(decision, monkeypatch).handle("posologie d'un médicament")

    resp = result.responses[0]
    assert resp.grounding == "sourced"
    assert resp.rag_schema == "rag_health"  # étage 1 a tranché, étage 2 muet


async def test_stage2_at_bar_exactly_passes(monkeypatch) -> None:
    """La barre est inclusive (>=) : un match pile à 0.60 rattrape, prouvant que
    la constante configurable est bien le point de bascule."""
    _mock_multi(
        monkeypatch,
        {"rag_legal": [_match("recueil_fiscal", sim=0.60)]},  # pile à la barre
    )
    decision = RouteDecision(pole=Pole.FINTECH, module=None, confidence=0.9, complexity="simple")
    result = await _orchestrator(decision, monkeypatch).handle("taux de la TVA au Congo")

    resp = result.responses[0]
    assert resp.grounding == "sourced"
    assert resp.rag_schema == "rag_legal"


async def test_no_home_pole_skips_to_stage2(monkeypatch) -> None:
    """Un pôle sans schéma maison (cyber) va directement à l'étage 2 : un match
    fort inter-domaine rattrape quand même."""
    _mock_multi(
        monkeypatch,
        {"rag_legal": [_match("recueil_fiscal", sim=0.72)]},
    )
    decision = RouteDecision(pole=Pole.CYBER, module=None, confidence=0.9, complexity="simple")
    result = await _orchestrator(decision, monkeypatch).handle("question réglementaire")

    resp = result.responses[0]
    assert resp.grounding == "sourced"
    assert resp.rag_schema == "rag_legal"
