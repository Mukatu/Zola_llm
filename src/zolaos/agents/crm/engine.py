"""Moteur déterministe CRM / Commercial (addendum §3.2, CRM-1).

Pipeline, scoring de leads, détection des relances, conversion devis→facture.
**Aucun LLM** : chiffres et scores calculés en code (le `CrmAgent` ne fait que
rédiger/narrer par-dessus).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from zolaos.agents.crm.models import Opportunity, Quote
from zolaos.connectors.models import Invoice

_ZERO = Decimal("0")

OPEN_STAGES = ("prospection", "qualification", "proposition", "negociation")
STAGE_PROBABILITY: dict[str, Decimal] = {
    "prospection": Decimal("0.10"),
    "qualification": Decimal("0.30"),
    "proposition": Decimal("0.60"),
    "negociation": Decimal("0.80"),
    "gagnee": Decimal("1.00"),
    "perdue": Decimal("0.00"),
}
SOURCE_WEIGHT: dict[str, Decimal] = {
    "referral": Decimal("1.0"),
    "salon": Decimal("0.7"),
    "web": Decimal("0.6"),
    "appel": Decimal("0.5"),
    "autre": Decimal("0.4"),
}


def _xaf(v: Decimal) -> Decimal:
    return v.quantize(Decimal("1"), rounding=ROUND_HALF_UP)


def _prob(opp: Opportunity) -> Decimal:
    return (
        opp.probabilite if opp.probabilite is not None else STAGE_PROBABILITY.get(opp.etape, _ZERO)
    )


# ----------------------------------------------------------------- pipeline


@dataclass(frozen=True)
class PipelineStats:
    nb_open: int
    total_open_xaf: Decimal
    weighted_open_xaf: Decimal
    win_rate_pct: Decimal
    par_etape_xaf: dict[str, Decimal]


def pipeline_stats(opportunities: list[Opportunity]) -> PipelineStats:
    open_opps = [o for o in opportunities if o.etape in OPEN_STAGES]
    total_open = sum((o.montant_xaf for o in open_opps), _ZERO)
    weighted = sum((o.montant_xaf * _prob(o) for o in open_opps), _ZERO)
    gagnees = sum(1 for o in opportunities if o.etape == "gagnee")
    perdues = sum(1 for o in opportunities if o.etape == "perdue")
    closed = gagnees + perdues
    win_rate = (
        (Decimal(gagnees) / Decimal(closed) * 100).quantize(Decimal("0.1")) if closed else _ZERO
    )
    par_etape: dict[str, Decimal] = defaultdict(lambda: _ZERO)
    for o in open_opps:
        par_etape[o.etape] += o.montant_xaf
    return PipelineStats(
        nb_open=len(open_opps),
        total_open_xaf=_xaf(total_open),
        weighted_open_xaf=_xaf(weighted),
        win_rate_pct=win_rate,
        par_etape_xaf={k: _xaf(v) for k, v in par_etape.items()},
    )


# ----------------------------------------------------------------- scoring


@dataclass(frozen=True)
class LeadScoringWeights:
    stage: Decimal = Decimal("0.40")
    recency: Decimal = Decimal("0.25")
    montant: Decimal = Decimal("0.20")
    source: Decimal = Decimal("0.15")
    montant_reference_xaf: Decimal = Decimal("10000000")  # plafond de normalisation


@dataclass(frozen=True)
class LeadScore:
    score: int  # 0-100
    grade: str  # A | B | C | D
    raisons: list[str] = field(default_factory=list)


def _recency_score(derniere: date | None, as_of: date) -> Decimal:
    if derniere is None:
        return Decimal("0.3")
    j = (as_of - derniere).days
    if j <= 7:
        return Decimal("1.0")
    if j <= 30:
        return Decimal("0.7")
    if j <= 90:
        return Decimal("0.4")
    return Decimal("0.1")


def score_lead(
    opp: Opportunity, *, weights: LeadScoringWeights | None = None, as_of: date | None = None
) -> LeadScore:
    """Score déterministe 0-100 d'une opportunité (étape, récence, montant, source)."""
    w = weights or LeadScoringWeights()
    as_of = as_of or date.today()

    stage_s = STAGE_PROBABILITY.get(opp.etape, _ZERO)
    recency_s = _recency_score(opp.derniere_interaction, as_of)
    montant_s = (
        min(Decimal("1"), opp.montant_xaf / w.montant_reference_xaf)
        if w.montant_reference_xaf > 0
        else _ZERO
    )
    # source portée par l'opportunité non disponible ici → neutre (0.4) ; affiné via Customer en CRM-2
    source_s = SOURCE_WEIGHT["autre"]

    score01 = (
        w.stage * stage_s + w.recency * recency_s + w.montant * montant_s + w.source * source_s
    )
    score = int((score01 * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    grade = "A" if score >= 75 else "B" if score >= 50 else "C" if score >= 25 else "D"
    raisons = [
        f"étape={opp.etape} ({stage_s})",
        f"récence={recency_s}",
        f"montant={montant_s.quantize(Decimal('0.01'))}",
    ]
    return LeadScore(score=score, grade=grade, raisons=raisons)


# ----------------------------------------------------------------- relances


@dataclass(frozen=True)
class RelanceItem:
    type: str  # devis_expire | devis_relance | opportunite
    reference: str
    libelle: str
    priorite: str  # high | medium | low


def detect_relances(
    quotes: list[Quote],
    opportunities: list[Opportunity],
    *,
    as_of: date | None = None,
    seuil_jours: int = 14,
) -> list[RelanceItem]:
    as_of = as_of or date.today()
    out: list[RelanceItem] = []

    for q in quotes:
        if q.statut != "envoye":
            continue
        if q.date_validite is not None and q.date_validite < as_of:
            out.append(
                RelanceItem(
                    "devis_expire", q.id_externe, f"Devis {q.numero} expiré sans réponse", "high"
                )
            )
        elif (as_of - q.date_emission).days >= seuil_jours:
            out.append(
                RelanceItem(
                    "devis_relance",
                    q.id_externe,
                    f"Devis {q.numero} envoyé sans réponse depuis {seuil_jours}+ j",
                    "medium",
                )
            )

    for o in opportunities:
        if o.etape not in OPEN_STAGES or o.derniere_interaction is None:
            continue
        jours = (as_of - o.derniere_interaction).days
        if jours >= seuil_jours:
            prio = "high" if o.montant_xaf >= Decimal("5000000") else "medium"
            out.append(
                RelanceItem(
                    "opportunite",
                    o.id_externe,
                    f"Opportunité '{o.libelle}' sans contact depuis {jours} j",
                    prio,
                )
            )

    return out


# ----------------------------------------------------------------- devis→facture


def quote_to_invoice(quote: Quote) -> Invoice:
    """Convertit un devis **accepté** en facture canonique (branche la Compta)."""
    if quote.statut != "accepte":
        raise ValueError(
            f"Devis {quote.numero} non accepté (statut={quote.statut}) — conversion refusée."
        )
    return Invoice(
        id_externe=quote.id_externe,
        numero=quote.numero,
        sens="vente",
        tiers=quote.client,
        date_emission=quote.date_emission,
        montant_ht_xaf=quote.montant_ht_xaf,
        montant_ttc_xaf=quote.montant_ttc_xaf,
        payee=False,
        country=quote.country,
    )
