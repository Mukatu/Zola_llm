"""Endpoints déterministes BI / Pilotage (FE↔BE) — KPIs cross-métiers.

Profil box. KPIs calculés en code (compute_kpis) à partir des données fournies,
ou agrégés sur le **registre vivant** (`/dashboard`) — cockpit transversal.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from zolaos.agents.bi.agent import BIAgent
from zolaos.agents.bi.echeances import Echeance, prochaines_echeances
from zolaos.agents.bi.kpi import KpiValue, compute_kpis, dashboard_kpis
from zolaos.agents.bi.signals import compute_signals
from zolaos.agents.crm.engine import STAGE_PROBABILITY
from zolaos.agents.erp.secretariat import Mandat, mandats_a_renouveler
from zolaos.agents.erp.treasury import CompteTresorerie, FluxTresorerie, position_tresorerie
from zolaos.api.dependencies import get_router_client
from zolaos.connectors.models import BankTransaction, Employee, Invoice
from zolaos.core.settings import Settings, get_settings
from zolaos.db.session import get_session
from zolaos.db.store_repo import (
    BankAccountRepository,
    BudgetLineRepository,
    CashFlowRepository,
    EmployeeRepository,
    EngagementRepository,
    InvoiceRepository,
    MandateRepository,
    OpportunityRepository,
    PayslipRepository,
    ProjectRepository,
    StockRepository,
)
from zolaos.llm.base import LLMClient

router = APIRouter(prefix="/v1/bi", tags=["bi"])

_ZERO = Decimal("0")
_OPEN_STAGES = ("prospection", "qualification", "proposition", "negociation")


class BiRequest(BaseModel):
    invoices: list[Invoice] = Field(default_factory=list)
    transactions: list[BankTransaction] = Field(default_factory=list)
    employees: list[Employee] = Field(default_factory=list)
    periode: str | None = None


@router.post("/kpis", summary="KPIs déterministes cross-métiers (corps de requête)")
def bi_kpis(req: BiRequest) -> dict[str, Any]:
    kpis = compute_kpis(
        invoices=req.invoices or None,
        transactions=req.transactions or None,
        employees=req.employees or None,
        periode=req.periode,
    )
    return {"kpis": [k.model_dump(mode="json") for k in kpis]}


async def _aggregate_kpis(
    session: AsyncSession, tenant_id: str, periode: str | None
) -> list[KpiValue]:
    """Agrège les KPIs transversaux sur le registre vivant (déterministe)."""
    invoices = await InvoiceRepository(session).list(tenant_id=tenant_id)
    accounts = await BankAccountRepository(session).list(tenant_id=tenant_id)
    flows = await CashFlowRepository(session).list(tenant_id=tenant_id)
    stock = await StockRepository(session).list(tenant_id=tenant_id)
    opps = await OpportunityRepository(session).list(tenant_id=tenant_id)
    engagements = await EngagementRepository(session).list(tenant_id=tenant_id)
    employees = await EmployeeRepository(session).list(tenant_id=tenant_id)

    # Finance / commercial : agrégats factures (sommes directes sur le store).
    ca_ht = sum((i.montant_ht_xaf for i in invoices if i.sens == "vente"), _ZERO)
    ca_ttc = sum((i.montant_ttc_xaf for i in invoices if i.sens == "vente"), _ZERO)
    achats_ht = sum((i.montant_ht_xaf for i in invoices if i.sens == "achat"), _ZERO)
    enc_clients = sum(
        (i.montant_ttc_xaf for i in invoices if i.sens == "vente" and not i.payee), _ZERO
    )
    encours_fournisseurs = sum(
        (i.montant_ttc_xaf for i in invoices if i.sens == "achat" and not i.payee), _ZERO
    )
    dso = (enc_clients / ca_ttc * Decimal("30")).quantize(Decimal("1")) if ca_ttc > 0 else _ZERO

    # Trésorerie : position réalisée consolidée.
    comptes = [
        CompteTresorerie(
            code=a.code,
            libelle=a.libelle,
            type=a.type,
            devise=a.devise,
            solde_initial_xaf=a.solde_initial_xaf,
        )
        for a in accounts
    ]
    flux = [
        FluxTresorerie(
            compte_code=f.compte_code, sens=f.sens, montant_xaf=f.montant_xaf, statut=f.statut
        )
        for f in flows
    ]
    position = position_tresorerie(comptes, flux).total_realise_xaf

    # Stock : valorisation totale (PMP).
    valeur_stock = sum((s.quantite_actuelle * s.pmp_xaf for s in stock), _ZERO)

    # Commercial : pipeline pondéré (encours ouvert × probabilité d'étape).
    pipeline_pondere = sum(
        (
            o.montant_xaf
            * (
                o.probabilite
                if o.probabilite is not None
                else STAGE_PROBABILITY.get(o.etape, _ZERO)
            )
            for o in opps
            if o.etape in _OPEN_STAGES
        ),
        _ZERO,
    )

    # Achats : engagé (hors annulés).
    engage = sum(
        (
            e.montant_xaf
            for e in engagements
            if "annul" not in (e.statut_ebda + e.statut_bc).lower()
        ),
        _ZERO,
    )

    # RH : effectif actif + masse salariale. Si des bulletins sont historisés, on
    # prend la masse **réelle** de la dernière période (brut + coût employeur
    # chargé) ; sinon on retombe sur les salaires de base des actifs.
    actifs = [e for e in employees if e.statut == "actif"]
    payslips = await PayslipRepository(session).list(tenant_id=tenant_id)
    cout_employeur: Decimal | None = None
    if payslips:
        derniere = max((p.periode for p in payslips if p.periode), default="")
        du_mois = [p for p in payslips if p.periode == derniere]
        masse = sum((p.brut_xaf for p in du_mois), _ZERO)
        cout_employeur = sum((p.cout_employeur_xaf for p in du_mois), _ZERO)
    else:
        masse = sum((e.salaire_base_xaf for e in actifs), _ZERO)

    # Projets (bailleurs) : exécution budgétaire, si des projets sont suivis.
    projects = await ProjectRepository(session).list(tenant_id=tenant_id)
    realise_projets: Decimal | None = None
    taux_execution_projets: Decimal | None = None
    if projects:
        lignes = await BudgetLineRepository(session).list(tenant_id=tenant_id)
        realise_projets = sum((line.montant_realise for line in lignes), _ZERO)
        budget_total = sum((p.budget_total for p in projects), _ZERO)
        taux_execution_projets = (
            (realise_projets / budget_total * Decimal("100")).quantize(Decimal("0.1"))
            if budget_total > 0
            else _ZERO
        )

    return dashboard_kpis(
        ca_ht=ca_ht,
        marge_brute_xaf=ca_ht - achats_ht,
        encours_clients_xaf=enc_clients,
        encours_fournisseurs_xaf=encours_fournisseurs,
        dso=dso,
        position_tresorerie_xaf=position,
        valeur_stock_xaf=valeur_stock,
        pipeline_pondere_xaf=pipeline_pondere,
        engage_achats_xaf=engage,
        effectif_actif=len(actifs),
        masse_salariale_xaf=masse,
        periode=periode,
        cout_employeur_xaf=cout_employeur,
        realise_projets_xaf=realise_projets,
        taux_execution_projets=taux_execution_projets,
    )


@router.get("/dashboard", summary="Cockpit transversal agrégé sur le registre vivant")
async def bi_dashboard(
    tenant_id: str = "local",
    periode: str | None = None,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    kpis = await _aggregate_kpis(session, tenant_id, periode)
    return {"kpis": [k.model_dump(mode="json") for k in kpis]}


async def _mandate_echeances(session: AsyncSession, tenant_id: str) -> list[Echeance]:
    """Renouvellements de mandats sociaux à venir, en échéances de cockpit."""
    rows = await MandateRepository(session).list(tenant_id=tenant_id)
    mandats: list[Mandat] = []
    for r in rows:
        if r.statut != "actif":
            continue
        try:
            mandats.append(
                Mandat(
                    id_externe=r.id,
                    titulaire=r.titulaire,
                    fonction=r.fonction,  # type: ignore[arg-type]
                    date_nomination=r.date_nomination,
                    duree_annees=r.duree_annees,
                    country=r.country,
                )
            )
        except ValueError:
            continue  # donnée mandat non conforme : on l'ignore plutôt que planter
    return [
        Echeance(
            code=f"mandat-{a.reference[:8]}",
            libelle=a.libelle,
            periodicite="mandat",
            date_limite=a.date_cible,
            jours_restants=a.jours_restants,
            note="Renouvellement de mandat social — vérifiez les statuts et l'organe compétent.",
        )
        for a in mandats_a_renouveler(mandats, horizon_jours=120)
    ]


@router.get("/cockpit", summary="Cockpit v2 : KPIs + signaux + échéances (déterministe)")
async def bi_cockpit(
    tenant_id: str = "local",
    periode: str | None = None,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Cockpit décisionnel **déterministe** (sans LLM) : chiffres, signaux dérivés
    et rappels d'échéances (obligations fiscales + renouvellements de mandats).
    Le brief narré est servi séparément par ``/brief``."""
    kpis = await _aggregate_kpis(session, tenant_id, periode)
    signals = compute_signals(kpis)
    echeances = [*prochaines_echeances(), *await _mandate_echeances(session, tenant_id)]
    echeances.sort(key=lambda e: e.date_limite)
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "kpis": [k.model_dump(mode="json") for k in kpis],
        "signals": [s.model_dump(mode="json") for s in signals],
        "echeances": [e.model_dump(mode="json") for e in echeances],
    }


class BriefRequest(BaseModel):
    tenant_id: str = "local"
    periode: str | None = None


@router.post("/brief", summary="Brief de pilotage narré (LLM) à partir des KPIs+signaux")
async def bi_brief(
    req: BriefRequest,
    client: LLMClient = Depends(get_router_client),
    settings: Settings = Depends(get_settings),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Synthèse narrative des KPIs et signaux (le LLM narre, ne recalcule pas)."""
    kpis = await _aggregate_kpis(session, req.tenant_id, req.periode)
    signals = compute_signals(kpis)
    apercu = "\n".join(f"- [{s.niveau}] {s.titre} : {s.detail}" for s in signals)
    brief = await BIAgent(client, settings).synthesize(
        kpis, periode=req.periode or "période courante"
    )
    return {"brief": brief, "signals_apercu": apercu}


class AskRequest(BaseModel):
    question: str
    tenant_id: str = "local"
    periode: str | None = None


@router.post("/ask", summary="Question en langage naturel sur les KPIs du cockpit")
async def bi_ask(
    req: AskRequest,
    client: LLMClient = Depends(get_router_client),
    settings: Settings = Depends(get_settings),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    kpis = await _aggregate_kpis(session, req.tenant_id, req.periode)
    answer = await BIAgent(client, settings).answer(req.question, kpis)
    return {"answer": answer}
