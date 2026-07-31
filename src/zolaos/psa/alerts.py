"""Alertes marge & sous-facturation — le moteur détecte, l'IA narre (PSA).

**Déterministe** : à partir de l'économie d'une mission (honoraires/coût/marge) et
de son **encours non facturé** (temps approuvé facturable sans facture), on émet des
alertes typées, bornées par des seuils gouvernables (`PSA_*`). Aucune approximation.

**Narration** (optionnelle) : l'IA n'intervient QUE pour reformuler/prioriser ces
alertes en une courte note de pilotage — elle ne cite que les chiffres fournis, n'en
invente ni n'en recalcule aucun (doctrine « le moteur calcule, le LLM narre »).
Hors-RAG, servi localement. Ne lève jamais côté narration : `unavailable` si le LLM
échoue, `empty` s'il n'y a aucune alerte.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from zolaos.core.logging import get_logger
from zolaos.llm.base import GenerationOptions, Message
from zolaos.llm.factory import make_router_client

_log = get_logger("zolaos.psa.alerts")

_SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}

# Types d'alerte (stables — repris côté front / audit).
MARGE_NEGATIVE = "marge_negative"
MARGE_FAIBLE = "marge_faible"
SOUS_FACTURATION = "sous_facturation"


@dataclass
class Thresholds:
    """Seuils de détection (proviennent des réglages `PSA_*`, gouvernables)."""

    margin_low_pct: int = 20
    wip_alert_xaf: int = 500_000
    min_honoraires_xaf: int = 100_000


@dataclass
class Alert:
    """Une alerte typée, avec son message déterministe et ses chiffres."""

    type: str
    severity: str  # high | medium | low
    mission_id: str
    offre: str | None
    message: str
    impact: int  # magnitude (XAF) pour le tri secondaire
    metrics: dict[str, int | None] = field(default_factory=dict)


def scan_mission(
    *,
    mission_id: str,
    offre: str | None,
    econ: dict[str, Any],
    unbilled_wip: int,
    thresholds: Thresholds,
) -> list[Alert]:
    """Alertes d'une mission à partir de son économie + encours non facturé."""
    honoraires = int(econ.get("honoraires") or 0)
    cost = int(econ.get("cost") or 0)
    margin = int(econ.get("margin") or 0)
    margin_pct = econ.get("margin_pct")
    econ_metrics: dict[str, int | None] = {
        "honoraires": honoraires,
        "cost": cost,
        "margin": margin,
        "margin_pct": margin_pct,
    }
    alerts: list[Alert] = []

    # 1) Marge négative : la mission coûte plus qu'elle ne facture — priorité haute.
    if honoraires > 0 and margin < 0:
        alerts.append(
            Alert(
                type=MARGE_NEGATIVE,
                severity="high",
                mission_id=mission_id,
                offre=offre,
                message=f"Marge négative : {margin} XAF (honoraires {honoraires}, coût {cost}).",
                impact=abs(margin),
                metrics=econ_metrics,
            )
        )
    # 2) Marge faible : positive mais sous le seuil, sur une mission non naissante.
    elif (
        margin_pct is not None
        and 0 <= margin_pct < thresholds.margin_low_pct
        and honoraires >= thresholds.min_honoraires_xaf
    ):
        alerts.append(
            Alert(
                type=MARGE_FAIBLE,
                severity="medium",
                mission_id=mission_id,
                offre=offre,
                message=f"Marge faible : {margin_pct}% (seuil {thresholds.margin_low_pct}%).",
                impact=honoraires,
                metrics=econ_metrics,
            )
        )

    # 3) Sous-facturation : encours approuvé non facturé au-delà du seuil.
    if unbilled_wip >= thresholds.wip_alert_xaf:
        severity = "high" if unbilled_wip >= 2 * thresholds.wip_alert_xaf else "medium"
        alerts.append(
            Alert(
                type=SOUS_FACTURATION,
                severity=severity,
                mission_id=mission_id,
                offre=offre,
                message=(
                    f"Encours non facturé : {unbilled_wip} XAF approuvés, prêts à facturer."
                ),
                impact=unbilled_wip,
                metrics={"unbilled_wip": unbilled_wip},
            )
        )
    return alerts


def scan_alerts(
    missions: list[dict[str, Any]], *, thresholds: Thresholds | None = None
) -> list[Alert]:
    """Balaye toutes les missions et renvoie les alertes, plus graves d'abord.

    `missions` : dicts `{mission_id, offre, econ, unbilled_wip}`. Tri : sévérité
    (high→low) puis impact (XAF) décroissant."""
    thresholds = thresholds or Thresholds()
    out: list[Alert] = []
    for m in missions:
        out.extend(
            scan_mission(
                mission_id=str(m["mission_id"]),
                offre=m.get("offre"),
                econ=m.get("econ") or {},
                unbilled_wip=int(m.get("unbilled_wip") or 0),
                thresholds=thresholds,
            )
        )
    out.sort(key=lambda a: (_SEVERITY_ORDER.get(a.severity, 9), -a.impact))
    return out


# ---------------------------------------------------------------------------
# Narration IA (optionnelle) — reformule/priorise, n'invente aucun chiffre
# ---------------------------------------------------------------------------
_NARRATION_SYSTEM_PROMPT = (
    "Tu es contrôleur de gestion d'un cabinet de conseil. On te fournit une liste "
    "d'ALERTES déjà calculées (marge, sous-facturation) avec leurs chiffres exacts. "
    "Rédige une courte NOTE DE PILOTAGE en français : une synthèse (1–2 phrases) puis "
    "les ACTIONS PRIORITAIRES (puces). Règle absolue : n'utilise QUE les chiffres "
    "fournis, n'en invente aucun, ne recalcule rien, n'ajoute aucune mission. Traite "
    "d'abord les alertes de sévérité « high ». Sois concret, sobre et bref."
)


@dataclass
class NarrationOutcome:
    """Résultat de la narration d'alertes."""

    status: str  # generated | unavailable | empty
    brief: str = ""


def build_narration_prompt(alerts: list[Alert]) -> str:
    """Formate les alertes (chiffres inclus) en message pour le LLM."""
    lines = [
        f"- [{a.severity}] {a.type} — mission « {a.offre or 'sans objet'} » : {a.message}"
        for a in alerts
    ]
    return (
        "Alertes à synthétiser (n'utilise que ces chiffres) :\n"
        + "\n".join(lines)
        + "\n\nRédige la note de pilotage."
    )


async def narrate_alerts(settings: Any, alerts: list[Alert]) -> NarrationOutcome:
    """Reformule les alertes en note de pilotage (LLM local). Ne lève jamais.

    `empty` si aucune alerte (pas d'appel LLM), `unavailable` si le LLM échoue."""
    if not alerts:
        return NarrationOutcome(
            "empty", brief="Aucune alerte : marges et facturation sous contrôle."
        )
    client = make_router_client(settings)
    prompt = build_narration_prompt(alerts)
    try:
        result = await client.generate(
            [
                Message(role="system", content=_NARRATION_SYSTEM_PROMPT),
                Message(role="user", content=prompt),
            ],
            model=settings.LLM_MODEL_BRIGADE,
            options=GenerationOptions(temperature=0.2, max_tokens=600),
        )
    except Exception as exc:  # LLM local indisponible
        _log.warning("alerts.narrate_unavailable", error=str(exc))
        return NarrationOutcome("unavailable")
    return NarrationOutcome("generated", brief=result.content.strip())
