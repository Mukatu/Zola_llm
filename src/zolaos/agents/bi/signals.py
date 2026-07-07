"""Signaux de pilotage — détection **déterministe** d'alertes et signaux faibles.

Les signaux sont dérivés des KPIs déjà calculés (données du client) : aucun
chiffre n'est inventé, aucune règle légale n'est affirmée. Le LLM narre ensuite
ces signaux (cf. `agent.py`) mais ne les produit pas.

Seuils paramétrables (constantes) : à ajuster par métier sans toucher au code
appelant.
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel

from zolaos.agents.bi.kpi import KpiValue

_ZERO = Decimal("0")

# Seuils par défaut (paramétrables).
SEUIL_MARGE_FAIBLE = Decimal("0.15")  # marge brute / CA en deçà → attention
SEUIL_DSO_ATTENTION = Decimal("60")  # jours
SEUIL_DSO_ALERTE = Decimal("90")  # jours


class Signal(BaseModel):
    """Un signal de pilotage détecté (fait dérivé des KPIs)."""

    code: str
    niveau: str  # info | attention | alerte
    domaine: str
    titre: str
    detail: str
    kpi_code: str | None = None


def _index(kpis: list[KpiValue]) -> dict[str, Decimal]:
    return {k.code: k.valeur for k in kpis}


def _fmt(v: Decimal) -> str:
    return f"{v:,.0f}".replace(",", " ")


def compute_signals(kpis: list[KpiValue]) -> list[Signal]:
    """Dérive les signaux (alertes/attentions) des KPIs — déterministe."""
    v = _index(kpis)
    out: list[Signal] = []

    tresorerie = v.get("position_tresorerie")
    if tresorerie is not None and tresorerie < 0:
        out.append(
            Signal(
                code="tresorerie_negative",
                niveau="alerte",
                domaine="finance",
                titre="Trésorerie négative",
                detail=f"Position consolidée : {_fmt(tresorerie)} XAF. Risque de tension immédiate.",
                kpi_code="position_tresorerie",
            )
        )

    ca = v.get("ca_ht", _ZERO)
    marge = v.get("marge_brute")
    if marge is not None and marge < 0:
        out.append(
            Signal(
                code="marge_negative",
                niveau="alerte",
                domaine="commercial",
                titre="Marge brute négative",
                detail=f"Marge brute : {_fmt(marge)} XAF. Les achats dépassent le chiffre d'affaires.",
                kpi_code="marge_brute",
            )
        )
    elif marge is not None and ca > 0 and marge / ca < SEUIL_MARGE_FAIBLE:
        taux = (marge / ca * Decimal("100")).quantize(Decimal("1"))
        out.append(
            Signal(
                code="marge_faible",
                niveau="attention",
                domaine="commercial",
                titre=f"Marge brute faible ({taux} %)",
                detail=f"Sous le seuil de {int(SEUIL_MARGE_FAIBLE * 100)} %. Revoir prix ou coûts d'achat.",
                kpi_code="marge_brute",
            )
        )

    dso = v.get("dso")
    if dso is not None and dso >= SEUIL_DSO_ALERTE:
        out.append(
            Signal(
                code="dso_alerte",
                niveau="alerte",
                domaine="finance",
                titre=f"Encaissements très lents (DSO {dso} j)",
                detail="Relancer les clients : le délai d'encaissement pèse sur la trésorerie.",
                kpi_code="dso",
            )
        )
    elif dso is not None and dso >= SEUIL_DSO_ATTENTION:
        out.append(
            Signal(
                code="dso_attention",
                niveau="attention",
                domaine="finance",
                titre=f"Délai d'encaissement élevé (DSO {dso} j)",
                detail="Surveiller les relances clients.",
                kpi_code="dso",
            )
        )

    enc_clients = v.get("encours_clients")
    if (
        enc_clients is not None
        and tresorerie is not None
        and tresorerie > 0
        and enc_clients > tresorerie
    ):
        out.append(
            Signal(
                code="encours_sup_tresorerie",
                niveau="attention",
                domaine="finance",
                titre="Encours clients supérieur à la trésorerie",
                detail=(
                    f"Encours {_fmt(enc_clients)} XAF > trésorerie {_fmt(tresorerie)} XAF : "
                    "l'activité est financée par le crédit client."
                ),
                kpi_code="encours_clients",
            )
        )

    enc_fourn = v.get("encours_fournisseurs")
    if (
        enc_fourn is not None
        and tresorerie is not None
        and tresorerie > 0
        and enc_fourn > tresorerie
    ):
        out.append(
            Signal(
                code="dettes_sup_tresorerie",
                niveau="attention",
                domaine="achats",
                titre="Dettes fournisseurs supérieures à la trésorerie",
                detail=f"À régler {_fmt(enc_fourn)} XAF pour {_fmt(tresorerie)} XAF disponibles.",
                kpi_code="encours_fournisseurs",
            )
        )

    if not out:
        out.append(
            Signal(
                code="ras",
                niveau="info",
                domaine="finance",
                titre="Aucun signal critique",
                detail="Les indicateurs disponibles ne déclenchent aucune alerte.",
            )
        )
    return out
