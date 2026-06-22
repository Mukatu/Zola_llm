"""Achats / Procurement — module ERP (addendum pilotage opérationnel, OPS-2).

Transparence et lutte contre la surfacturation. **Déterministe d'abord** :
scoring fournisseurs, comparaison de devis et contrôle de conformité sont
calculés **en code** ; le LLM **rédige** (contrats OHADA) et **synthétise**.
RAG ciblé : offres reçues + droit commercial OHADA (ancrage des contrats).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from pydantic import BaseModel, Field

from zolaos.agents._prompts import load_prompt
from zolaos.core.logging import get_logger
from zolaos.core.metrics import AGENT_INVOCATIONS_TOTAL
from zolaos.core.settings import Settings
from zolaos.llm.base import GenerationOptions, LLMClient, Message

_log = get_logger("zolaos.agents.erp.achats")
_ZERO = Decimal("0")

# Pièces de conformité attendues d'un prestataire (contexte OHADA / CG).
DOCS_REQUIS: tuple[str, ...] = ("rccm", "niu", "attestation_fiscale")


# ============================================================ modèles

class Supplier(BaseModel):
    model_config = {"extra": "forbid"}

    id_externe: str
    nom: str
    secteur: str | None = None
    note_qualite: Decimal = Field(default=_ZERO, ge=0, le=5, description="Historique 0-5")
    delai_moyen_jours: int = Field(default=0, ge=0)
    documents_conformite: list[str] = Field(default_factory=list)
    actif: bool = True
    country: str = Field(default="cg", pattern=r"^[a-z]{2}$")


class OffreFournisseur(BaseModel):
    """Devis reçu d'un fournisseur (procurement)."""

    model_config = {"extra": "forbid"}

    id_externe: str
    fournisseur: str
    objet: str
    montant_ht_xaf: Decimal = Field(..., ge=0)
    montant_ttc_xaf: Decimal = Field(..., ge=0)
    delai_livraison_jours: int = Field(default=0, ge=0)
    country: str = Field(default="cg", pattern=r"^[a-z]{2}$")


@dataclass(frozen=True)
class SupplierScore:
    id_externe: str
    nom: str
    score: int                 # 0-100
    grade: str                 # A | B | C | D
    raisons: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ComparatifLigne:
    offre_id: str
    fournisseur: str
    montant_ttc_xaf: Decimal
    delai_livraison_jours: int
    score: int                 # 0-100 (mieux = plus haut)
    rang: int


# ============================================================ conformité (pur)

def verifier_conformite(supplier: Supplier) -> list[str]:
    """Pièces de conformité manquantes (déterministe)."""
    presents = {d.lower() for d in supplier.documents_conformite}
    return [d for d in DOCS_REQUIS if d not in presents]


# ============================================================ scoring fournisseur (pur)

@dataclass(frozen=True)
class ScoringWeights:
    qualite: Decimal = Decimal("0.45")
    conformite: Decimal = Decimal("0.35")
    delai: Decimal = Decimal("0.20")
    delai_reference_jours: int = 30


def score_fournisseur(supplier: Supplier, *, weights: ScoringWeights | None = None) -> SupplierScore:
    w = weights or ScoringWeights()
    qualite_s = supplier.note_qualite / Decimal("5")
    conformite_s = Decimal(len(DOCS_REQUIS) - len(verifier_conformite(supplier))) / Decimal(len(DOCS_REQUIS))
    delai_s = max(_ZERO, Decimal("1") - Decimal(supplier.delai_moyen_jours) / Decimal(w.delai_reference_jours))
    score01 = w.qualite * qualite_s + w.conformite * conformite_s + w.delai * delai_s
    score = int((score01 * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    grade = "A" if score >= 75 else "B" if score >= 50 else "C" if score >= 25 else "D"
    raisons = [
        f"qualité={qualite_s.quantize(Decimal('0.01'))}",
        f"conformité={conformite_s.quantize(Decimal('0.01'))}",
        f"délai={delai_s.quantize(Decimal('0.01'))}",
    ]
    return SupplierScore(id_externe=supplier.id_externe, nom=supplier.nom, score=score, grade=grade, raisons=raisons)


# ============================================================ comparaison d'offres (pur)

def _normalize_lower_better(value: Decimal, lo: Decimal, hi: Decimal) -> Decimal:
    """1 = meilleur (le plus bas), 0 = pire (le plus haut)."""
    if hi <= lo:
        return Decimal("1")
    return (hi - value) / (hi - lo)


@dataclass(frozen=True)
class ComparatifPoids:
    prix: Decimal = Decimal("0.6")
    delai: Decimal = Decimal("0.4")


def comparer_offres(
    offres: list[OffreFournisseur], *, poids: ComparatifPoids | None = None
) -> list[ComparatifLigne]:
    """Classe les offres (prix + délai). Déterministe. Mieux = score plus haut."""
    if not offres:
        return []
    w = poids or ComparatifPoids()
    prix = [o.montant_ttc_xaf for o in offres]
    delais = [Decimal(o.delai_livraison_jours) for o in offres]
    pmin, pmax = min(prix), max(prix)
    dmin, dmax = min(delais), max(delais)

    scored: list[tuple[OffreFournisseur, int]] = []
    for o in offres:
        prix_s = _normalize_lower_better(o.montant_ttc_xaf, pmin, pmax)
        delai_s = _normalize_lower_better(Decimal(o.delai_livraison_jours), dmin, dmax)
        score = int(((w.prix * prix_s + w.delai * delai_s) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        scored.append((o, score))

    scored.sort(key=lambda t: t[1], reverse=True)
    return [
        ComparatifLigne(
            offre_id=o.id_externe, fournisseur=o.fournisseur, montant_ttc_xaf=o.montant_ttc_xaf,
            delai_livraison_jours=o.delai_livraison_jours, score=score, rang=i + 1,
        )
        for i, (o, score) in enumerate(scored)
    ]


# ============================================================ agent

class AchatsAgent:
    """Agent Achats : scoring/comparaison/conformité (déterministe) + contrats (LLM)."""

    name = "erp.achats"
    prompt_file = "erp/achats.md"

    def __init__(self, client: LLMClient, settings: Settings) -> None:
        self._client = client
        self._settings = settings

    # -- déterministe --
    def scorer_fournisseurs(self, suppliers: list[Supplier]) -> list[SupplierScore]:
        return sorted((score_fournisseur(s) for s in suppliers), key=lambda x: x.score, reverse=True)

    def comparer(self, offres: list[OffreFournisseur]) -> list[ComparatifLigne]:
        return comparer_offres(offres)

    def conformite(self, supplier: Supplier) -> list[str]:
        return verifier_conformite(supplier)

    # -- génératif --
    async def rediger_contrat(self, *, fournisseur: str, objet: str, montant_xaf: str, conditions: str = "") -> str:
        """Rédige un contrat de fourniture/prestation ancré sur le droit commercial OHADA."""
        cond = f"Conditions particulières : {conditions}\n" if conditions else ""
        user_msg = (
            f"Rédige un contrat de fourniture/prestation (droit commercial OHADA), français.\n"
            f"Fournisseur : {fournisseur}\nObjet : {objet}\nMontant : {montant_xaf} XAF\n{cond}"
            "Clauses usuelles (objet, prix, délais, pénalités, résiliation, litiges OHADA). "
            "N'invente pas de montant non fourni ; signale à faire valider par un juriste."
        )
        return await self._generate(user_msg, "rediger_contrat", max_tokens=1500)

    async def synthese_comparatif(self, comparatif: list[ComparatifLigne]) -> str:
        lignes = "\n".join(
            f"- Rang {c.rang} : {c.fournisseur} — {c.montant_ttc_xaf} XAF, {c.delai_livraison_jours} j (score {c.score})"
            for c in comparatif
        )
        user_msg = (
            f"--- Comparatif d'offres (déjà calculé) ---\n{lignes}\n\n"
            "Rédige une recommandation d'achat à partir de CE classement uniquement "
            "(meilleur rapport prix/délai, points de vigilance). N'invente aucun chiffre."
        )
        return await self._generate(user_msg, "synthese_comparatif")

    async def _generate(self, user_msg: str, op: str, *, max_tokens: int = 900) -> str:
        start = time.perf_counter()
        outcome = "error"
        try:
            result = await self._client.generate(
                [
                    Message(role="system", content=load_prompt("erp", "achats.md")),
                    Message(role="user", content=user_msg),
                ],
                model=self._settings.LLM_MODEL_BRIGADE,
                options=GenerationOptions(temperature=0.2, max_tokens=max_tokens),
            )
            outcome = "ok"
            _log.info("achats_agent." + op, duration_seconds=time.perf_counter() - start)
            return result.content
        finally:
            AGENT_INVOCATIONS_TOTAL.labels(agent=self.name, outcome=outcome).inc()
