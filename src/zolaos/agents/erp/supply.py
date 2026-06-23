"""Supply Chain & Stocks — module ERP (addendum Pilotage opérationnel, OPS-1).

Gestion des stocks et réapprovisionnement, **déterministe d'abord** : point de
commande, jours avant rupture, suggestions de réappro et alertes sont calculés
**en code** (aucun LLM). Le `SupplyChainAgent` n'utilise le LLM que pour
**rédiger** (bons de commande, bordereaux) et **narrer** l'analyse.

⚠️ Pas de forecasting ML : « jours avant rupture » = estimation **déterministe**
(stock / consommation moyenne), pas une prédiction. La prévision ML est une
brique dédiée ultérieure.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal
from typing import Literal

from pydantic import BaseModel, Field

from zolaos.agents._prompts import load_prompt
from zolaos.core.logging import get_logger
from zolaos.core.metrics import AGENT_INVOCATIONS_TOTAL
from zolaos.core.settings import Settings
from zolaos.llm.base import GenerationOptions, LLMClient, Message

_log = get_logger("zolaos.agents.erp.supply")
_ZERO = Decimal("0")

Urgence = Literal["high", "medium", "low"]


# ============================================================ modèles


class StockItem(BaseModel):
    model_config = {"extra": "forbid"}

    sku: str
    libelle: str
    quantite_actuelle: Decimal = Field(..., ge=0)
    unite: str = "unité"
    conso_moyenne_jour: Decimal = Field(default=_ZERO, ge=0)
    delai_appro_jours: int = Field(default=0, ge=0)
    stock_securite: Decimal = Field(default=_ZERO, ge=0)
    seuil_reappro: Decimal | None = Field(default=None, ge=0)
    quantite_reappro: Decimal | None = Field(default=None, ge=0)
    perissable: bool = False
    country: str = Field(default="cg", pattern=r"^[a-z]{2}$")


class BonCommandeLigne(BaseModel):
    model_config = {"extra": "forbid"}

    sku: str
    libelle: str
    quantite: Decimal = Field(..., gt=0)


class BonCommande(BaseModel):
    model_config = {"extra": "forbid"}

    reference: str
    fournisseur: str | None = None
    date_emission: date
    lignes: list[BonCommandeLigne] = Field(default_factory=list)
    country: str = Field(default="cg", pattern=r"^[a-z]{2}$")


@dataclass(frozen=True)
class ReapproSuggestion:
    sku: str
    libelle: str
    quantite_actuelle: Decimal
    point_de_commande: Decimal
    quantite_a_commander: Decimal
    jours_avant_rupture: Decimal | None
    urgence: Urgence


# ============================================================ moteur (pur)


def _ceil(v: Decimal) -> Decimal:
    return v.quantize(Decimal("1"), rounding=ROUND_CEILING)


def point_de_commande(item: StockItem) -> Decimal:
    """Seuil explicite s'il existe, sinon conso × délai + stock de sécurité."""
    if item.seuil_reappro is not None:
        return item.seuil_reappro
    return _ceil(item.conso_moyenne_jour * Decimal(item.delai_appro_jours) + item.stock_securite)


def jours_avant_rupture(item: StockItem) -> Decimal | None:
    """Estimation déterministe (stock / conso). None si pas de consommation."""
    if item.conso_moyenne_jour <= 0:
        return None
    return (item.quantite_actuelle / item.conso_moyenne_jour).quantize(
        Decimal("0.1"), rounding=ROUND_HALF_UP
    )


def quantite_a_commander(item: StockItem, point: Decimal) -> Decimal:
    """Quantité explicite si fournie, sinon ramène le stock à ~2× le point de commande."""
    if item.quantite_reappro is not None:
        return item.quantite_reappro
    return max(_ZERO, _ceil(point * 2 - item.quantite_actuelle))


def analyser_reappro(items: list[StockItem]) -> list[ReapproSuggestion]:
    """Articles dont le stock est au/ sous le point de commande."""
    out: list[ReapproSuggestion] = []
    for it in items:
        point = point_de_commande(it)
        if it.quantite_actuelle > point:
            continue
        jr = jours_avant_rupture(it)
        # Urgence haute si l'article sera en rupture AVANT d'être réapprovisionné.
        urgence: Urgence = (
            "high" if (jr is not None and jr <= Decimal(it.delai_appro_jours)) else "medium"
        )
        out.append(
            ReapproSuggestion(
                sku=it.sku,
                libelle=it.libelle,
                quantite_actuelle=it.quantite_actuelle,
                point_de_commande=point,
                quantite_a_commander=quantite_a_commander(it, point),
                jours_avant_rupture=jr,
                urgence=urgence,
            )
        )
    return out


def alertes_rupture(items: list[StockItem], *, horizon_jours: int = 30) -> list[ReapproSuggestion]:
    """Articles dont la rupture est estimée dans l'horizon donné."""
    out: list[ReapproSuggestion] = []
    for it in items:
        jr = jours_avant_rupture(it)
        if jr is not None and jr <= Decimal(horizon_jours):
            point = point_de_commande(it)
            urgence: Urgence = "high" if jr <= Decimal(it.delai_appro_jours) else "medium"
            out.append(
                ReapproSuggestion(
                    sku=it.sku,
                    libelle=it.libelle,
                    quantite_actuelle=it.quantite_actuelle,
                    point_de_commande=point,
                    quantite_a_commander=quantite_a_commander(it, point),
                    jours_avant_rupture=jr,
                    urgence=urgence,
                )
            )
    return out


def generer_bon_commande(
    suggestions: list[ReapproSuggestion],
    *,
    fournisseur: str | None = None,
    reference: str | None = None,
    as_of: date | None = None,
) -> BonCommande:
    """Construit un bon de commande (déterministe) à partir des suggestions."""
    as_of = as_of or date.today()
    lignes = [
        BonCommandeLigne(sku=s.sku, libelle=s.libelle, quantite=s.quantite_a_commander)
        for s in suggestions
        if s.quantite_a_commander > 0
    ]
    return BonCommande(
        reference=reference or f"BC-{as_of.isoformat()}",
        fournisseur=fournisseur,
        date_emission=as_of,
        lignes=lignes,
    )


# ============================================================ agent


class SupplyChainAgent:
    """Agent Supply Chain : analyse déterministe + rédaction générative."""

    name = "erp.supply_chain"
    prompt_file = "erp/supply_chain.md"

    def __init__(self, client: LLMClient, settings: Settings) -> None:
        self._client = client
        self._settings = settings

    # -- déterministe --
    def analyser(self, items: list[StockItem], *, horizon_jours: int = 30) -> dict:  # type: ignore[type-arg]
        return {
            "suggestions": analyser_reappro(items),
            "alertes": alertes_rupture(items, horizon_jours=horizon_jours),
        }

    def bon_commande(
        self, suggestions: list[ReapproSuggestion], *, fournisseur: str | None = None
    ) -> BonCommande:
        return generer_bon_commande(suggestions, fournisseur=fournisseur)

    # -- génératif --
    async def rediger_bon_commande(self, bon: BonCommande) -> str:
        """Rédige le texte formel d'un bon de commande (le LLM ne calcule pas les quantités)."""
        lignes = "\n".join(f"- {l.libelle} (SKU {l.sku}) : {l.quantite}" for l in bon.lignes)
        user_msg = (
            f"Rédige un bon de commande professionnel (français).\n"
            f"Référence : {bon.reference}\nFournisseur : {bon.fournisseur or 'à préciser'}\n"
            f"Date : {bon.date_emission}\nLignes (quantités déjà calculées) :\n{lignes}\n"
            "N'invente aucune quantité ; reprends celles fournies."
        )
        return await self._generate(user_msg, "rediger_bon_commande")

    async def synthese_stocks(self, analyse: dict) -> str:  # type: ignore[type-arg]
        sug = analyse["suggestions"]
        al = analyse["alertes"]
        lignes = "\n".join(
            f"- [{s.urgence}] {s.libelle} : stock {s.quantite_actuelle}, point {s.point_de_commande}, "
            f"à commander {s.quantite_a_commander}, rupture ~{s.jours_avant_rupture} j"
            for s in sug
        )
        user_msg = (
            f"--- Analyse de stock (déjà calculée) ---\n"
            f"À réapprovisionner : {len(sug)} | Alertes rupture : {len(al)}\n{lignes}\n\n"
            "Rédige une synthèse d'approvisionnement : priorités, risques de rupture, "
            "recommandations. N'invente aucun chiffre."
        )
        return await self._generate(user_msg, "synthese_stocks")

    async def _generate(self, user_msg: str, op: str) -> str:
        start = time.perf_counter()
        outcome = "error"
        try:
            result = await self._client.generate(
                [
                    Message(role="system", content=load_prompt("erp", "supply_chain.md")),
                    Message(role="user", content=user_msg),
                ],
                model=self._settings.LLM_MODEL_BRIGADE,
                options=GenerationOptions(temperature=0.2, max_tokens=900),
            )
            outcome = "ok"
            _log.info("supply_agent." + op, duration_seconds=time.perf_counter() - start)
            return result.content
        finally:
            AGENT_INVOCATIONS_TOTAL.labels(agent=self.name, outcome=outcome).inc()
