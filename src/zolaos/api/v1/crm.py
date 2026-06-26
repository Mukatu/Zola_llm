"""CRM / Commercial — moteurs déterministes + **système de référence léger** (P2b).

Profil box. Deux niveaux :
- **Sans mémoire** : `POST /analyze` calcule pipeline/scoring/relances sur un corps
  de requête (rétro-compatible).
- **Registre vivant** (P2b) : CRUD `customers | opportunities | quotes | interactions`
  persistés (`store_*`) ; `GET /analyze`, `GET /forecast` tournent **sur le store** ;
  `POST /quotes/{id}/convert` matérialise une **facture** (branche la clôture continue).

Aucun LLM : tous les chiffres/scores sont calculés en code.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from zolaos.agents.crm.engine import detect_relances, pipeline_stats, quote_to_invoice, score_lead
from zolaos.agents.crm.models import Opportunity, Quote, QuoteLine
from zolaos.db.session import get_session
from zolaos.db.store_repo import (
    CustomerRepository,
    InteractionRepository,
    InvoiceRepository,
    OpportunityRepository,
    QuoteRepository,
)

router = APIRouter(prefix="/v1/crm", tags=["crm"])

_ZERO = Decimal("0")
OPEN_STAGES = ("prospection", "qualification", "proposition", "negociation")
STAGE_PROBABILITY: dict[str, Decimal] = {
    "prospection": Decimal("0.10"),
    "qualification": Decimal("0.30"),
    "proposition": Decimal("0.60"),
    "negociation": Decimal("0.80"),
}


# ----------------------------------------------------------------- sans mémoire (rétro-compat)


class CrmRequest(BaseModel):
    opportunities: list[Opportunity] = Field(default_factory=list)
    quotes: list[Quote] = Field(default_factory=list)


@router.post("/analyze", summary="Pipeline + scoring + relances (corps de requête, sans mémoire)")
def crm_analyze(req: CrmRequest) -> dict[str, Any]:
    stats = pipeline_stats(req.opportunities)
    scores = {o.id_externe: asdict(score_lead(o)) for o in req.opportunities}
    relances = [asdict(r) for r in detect_relances(req.quotes, req.opportunities)]
    return {"pipeline": asdict(stats), "scores": scores, "relances": relances}


# ----------------------------------------------------------------- schémas (store)


class CustomerIn(BaseModel):
    id_externe: str
    nom: str
    type: str = "prospect"
    email: str | None = None
    telephone: str | None = None
    secteur: str | None = None
    source: str = "autre"
    date_creation: date | None = None
    derniere_interaction: date | None = None
    country: str = "cg"


class CustomerPatch(BaseModel):
    nom: str | None = None
    type: str | None = None
    email: str | None = None
    telephone: str | None = None
    secteur: str | None = None
    source: str | None = None
    derniere_interaction: date | None = None


class OpportunityIn(BaseModel):
    id_externe: str
    client: str
    libelle: str
    montant_xaf: Decimal = Decimal("0")
    etape: str = "prospection"
    probabilite: Decimal | None = None
    date_creation: date | None = None
    date_cloture_prevue: date | None = None
    derniere_interaction: date | None = None
    country: str = "cg"


class OpportunityPatch(BaseModel):
    client: str | None = None
    libelle: str | None = None
    montant_xaf: Decimal | None = None
    etape: str | None = None
    probabilite: Decimal | None = None
    date_cloture_prevue: date | None = None
    derniere_interaction: date | None = None


class StageIn(BaseModel):
    etape: str


class QuoteLineIn(BaseModel):
    libelle: str
    montant_ht_xaf: Decimal = Decimal("0")


class QuoteIn(BaseModel):
    id_externe: str
    numero: str
    client: str
    date_emission: date
    date_validite: date | None = None
    statut: str = "brouillon"
    lignes: list[QuoteLineIn] = Field(default_factory=list)
    montant_ht_xaf: Decimal = Decimal("0")
    montant_ttc_xaf: Decimal = Decimal("0")
    country: str = "cg"


class QuotePatch(BaseModel):
    statut: str | None = None
    date_validite: date | None = None
    montant_ht_xaf: Decimal | None = None
    montant_ttc_xaf: Decimal | None = None


class InteractionIn(BaseModel):
    customer_id: str | None = None
    opportunity_id: str | None = None
    type: str = "note"
    date: date
    resume: str = ""


# ----------------------------------------------------------------- CRUD clients


@router.post("/customers", status_code=status.HTTP_201_CREATED, summary="Créer un client/prospect")
async def create_customer(
    body: CustomerIn, tenant_id: str = "local", session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    rec = await CustomerRepository(session).create({**body.model_dump(), "tenant_id": tenant_id})
    await session.commit()
    return rec.to_dict()


@router.get("/customers", summary="Lister les clients/prospects")
async def list_customers(
    tenant_id: str = "local", session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    rows = await CustomerRepository(session).list(tenant_id=tenant_id)
    return {"customers": [r.to_dict() for r in rows]}


@router.patch("/customers/{customer_id}", summary="Mettre à jour un client")
async def patch_customer(
    customer_id: str,
    body: CustomerPatch,
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    rec = await CustomerRepository(session).update(
        customer_id, tenant_id=tenant_id, fields=body.model_dump(exclude_none=True)
    )
    if rec is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="customer_not_found")
    await session.commit()
    return rec.to_dict()


@router.delete("/customers/{customer_id}", summary="Supprimer un client")
async def delete_customer(
    customer_id: str, tenant_id: str = "local", session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    ok = await CustomerRepository(session).delete(customer_id, tenant_id=tenant_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="customer_not_found")
    await session.commit()
    return {"deleted": customer_id}


# ----------------------------------------------------------------- CRUD opportunités


@router.post("/opportunities", status_code=status.HTTP_201_CREATED, summary="Créer une opportunité")
async def create_opportunity(
    body: OpportunityIn, tenant_id: str = "local", session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    rec = await OpportunityRepository(session).create({**body.model_dump(), "tenant_id": tenant_id})
    await session.commit()
    return rec.to_dict()


@router.get("/opportunities", summary="Lister les opportunités")
async def list_opportunities(
    tenant_id: str = "local", session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    rows = await OpportunityRepository(session).list(tenant_id=tenant_id)
    return {"opportunities": [r.to_dict() for r in rows]}


@router.patch("/opportunities/{opp_id}", summary="Mettre à jour une opportunité")
async def patch_opportunity(
    opp_id: str,
    body: OpportunityPatch,
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    rec = await OpportunityRepository(session).update(
        opp_id, tenant_id=tenant_id, fields=body.model_dump(exclude_none=True)
    )
    if rec is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="opportunity_not_found")
    await session.commit()
    return rec.to_dict()


@router.patch("/opportunities/{opp_id}/stage", summary="Déplacer dans le pipeline (kanban)")
async def move_stage(
    opp_id: str,
    body: StageIn,
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    rec = await OpportunityRepository(session).update(
        opp_id, tenant_id=tenant_id, fields={"etape": body.etape}
    )
    if rec is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="opportunity_not_found")
    await session.commit()
    return rec.to_dict()


@router.delete("/opportunities/{opp_id}", summary="Supprimer une opportunité")
async def delete_opportunity(
    opp_id: str, tenant_id: str = "local", session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    ok = await OpportunityRepository(session).delete(opp_id, tenant_id=tenant_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="opportunity_not_found")
    await session.commit()
    return {"deleted": opp_id}


# ----------------------------------------------------------------- CRUD devis


@router.post("/quotes", status_code=status.HTTP_201_CREATED, summary="Créer un devis")
async def create_quote(
    body: QuoteIn, tenant_id: str = "local", session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    data = body.model_dump()
    data["lignes"] = [
        {"libelle": x["libelle"], "montant_ht_xaf": str(x["montant_ht_xaf"])}
        for x in data["lignes"]
    ]
    rec = await QuoteRepository(session).create({**data, "tenant_id": tenant_id})
    await session.commit()
    return rec.to_dict()


@router.get("/quotes", summary="Lister les devis")
async def list_quotes(
    tenant_id: str = "local", session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    rows = await QuoteRepository(session).list(tenant_id=tenant_id)
    return {"quotes": [r.to_dict() for r in rows]}


@router.patch("/quotes/{quote_id}", summary="Mettre à jour un devis")
async def patch_quote(
    quote_id: str,
    body: QuotePatch,
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    rec = await QuoteRepository(session).update(
        quote_id, tenant_id=tenant_id, fields=body.model_dump(exclude_none=True)
    )
    if rec is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="quote_not_found")
    await session.commit()
    return rec.to_dict()


@router.delete("/quotes/{quote_id}", summary="Supprimer un devis")
async def delete_quote(
    quote_id: str, tenant_id: str = "local", session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    ok = await QuoteRepository(session).delete(quote_id, tenant_id=tenant_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="quote_not_found")
    await session.commit()
    return {"deleted": quote_id}


@router.post("/quotes/{quote_id}/convert", summary="Convertir un devis accepté en facture")
async def convert_quote(
    quote_id: str, tenant_id: str = "local", session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    quotes = QuoteRepository(session)
    rec = await quotes.get(quote_id, tenant_id=tenant_id)
    if rec is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="quote_not_found")
    if rec.invoice_id is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="deja_converti")
    try:
        invoice = quote_to_invoice(_to_quote(rec))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="devis_non_accepte"
        ) from exc
    inv = await InvoiceRepository(session).create(
        {
            "tenant_id": tenant_id,
            "numero": invoice.numero,
            "sens": "vente",
            "tiers": invoice.tiers,
            "date_emission": invoice.date_emission,
            "montant_ht_xaf": invoice.montant_ht_xaf,
            "montant_ttc_xaf": invoice.montant_ttc_xaf,
            "payee": False,
            "country": invoice.country,
        }
    )
    await quotes.update(quote_id, tenant_id=tenant_id, fields={"invoice_id": inv.id})
    await session.commit()
    return {"quote": rec.to_dict(), "invoice": inv.to_dict()}


# ----------------------------------------------------------------- interactions (journal)


@router.post(
    "/interactions", status_code=status.HTTP_201_CREATED, summary="Journaliser une interaction"
)
async def create_interaction(
    body: InteractionIn, tenant_id: str = "local", session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    repo = InteractionRepository(session)
    rec = await repo.create({**body.model_dump(), "tenant_id": tenant_id})
    # propage « dernière interaction » sur le client/l'opportunité (champ de confort)
    if body.customer_id:
        await CustomerRepository(session).update(
            body.customer_id, tenant_id=tenant_id, fields={"derniere_interaction": body.date}
        )
    if body.opportunity_id:
        await OpportunityRepository(session).update(
            body.opportunity_id, tenant_id=tenant_id, fields={"derniere_interaction": body.date}
        )
    await session.commit()
    return rec.to_dict()


@router.get("/interactions", summary="Lister les interactions (filtrable)")
async def list_interactions(
    tenant_id: str = "local",
    customer_id: str | None = None,
    opportunity_id: str | None = None,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    rows = await InteractionRepository(session).list(
        tenant_id=tenant_id, customer_id=customer_id, opportunity_id=opportunity_id
    )
    return {"interactions": [r.to_dict() for r in rows]}


@router.delete("/interactions/{interaction_id}", summary="Supprimer une interaction")
async def delete_interaction(
    interaction_id: str, tenant_id: str = "local", session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    ok = await InteractionRepository(session).delete(interaction_id, tenant_id=tenant_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="interaction_not_found")
    await session.commit()
    return {"deleted": interaction_id}


# ----------------------------------------------------------------- analyse / prévision (store)


def _to_opportunity(rec: Any, derniere: date | None) -> Opportunity:
    return Opportunity(
        id_externe=rec.id_externe,
        client=rec.client,
        libelle=rec.libelle,
        montant_xaf=rec.montant_xaf,
        etape=rec.etape,
        probabilite=rec.probabilite,
        date_creation=rec.date_creation,
        date_cloture_prevue=rec.date_cloture_prevue,
        derniere_interaction=derniere,
        country=rec.country,
    )


def _to_quote(rec: Any) -> Quote:
    return Quote(
        id_externe=rec.id_externe,
        numero=rec.numero,
        client=rec.client,
        date_emission=rec.date_emission,
        date_validite=rec.date_validite,
        statut=rec.statut,
        lignes=[
            QuoteLine(libelle=x["libelle"], montant_ht_xaf=Decimal(str(x["montant_ht_xaf"])))
            for x in rec.lignes
        ],
        montant_ht_xaf=rec.montant_ht_xaf,
        montant_ttc_xaf=rec.montant_ttc_xaf,
        country=rec.country,
    )


@router.get("/analyze", summary="Pipeline + scoring + relances (sur le registre vivant)")
async def crm_analyze_store(
    tenant_id: str = "local", session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    opp_rows = await OpportunityRepository(session).list(tenant_id=tenant_id)
    quote_rows = await QuoteRepository(session).list(tenant_id=tenant_id)
    cust_rows = await CustomerRepository(session).list(tenant_id=tenant_id)
    inter_rows = await InteractionRepository(session).list(tenant_id=tenant_id)

    # dernière interaction réelle par opportunité (journal) — sinon champ stocké
    last_inter: dict[str, date] = {}
    for it in inter_rows:
        if it.opportunity_id and it.date:
            prev = last_inter.get(it.opportunity_id)
            if prev is None or it.date > prev:
                last_inter[it.opportunity_id] = it.date

    # source du client (par id_externe ET par nom) → raffine le scoring
    source_by: dict[str, str] = {}
    for c in cust_rows:
        source_by[c.id_externe] = c.source
        source_by[c.nom] = c.source

    opps = [_to_opportunity(r, last_inter.get(r.id) or r.derniere_interaction) for r in opp_rows]
    quotes = [_to_quote(r) for r in quote_rows]

    stats = pipeline_stats(opps)
    scores = {
        rec.id: asdict(score_lead(opp, source=source_by.get(rec.client)))
        for rec, opp in zip(opp_rows, opps, strict=True)
    }
    relances = [asdict(r) for r in detect_relances(quotes, opps)]
    return {"pipeline": asdict(stats), "scores": scores, "relances": relances}


@router.get("/forecast", summary="Prévision commerciale (encours pondéré par mois de clôture)")
async def crm_forecast(
    tenant_id: str = "local", session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    rows = await OpportunityRepository(session).list(tenant_id=tenant_id)
    par_mois: dict[str, dict[str, Decimal]] = {}
    sans_date_weighted = _ZERO
    for r in rows:
        if r.etape not in OPEN_STAGES:
            continue
        prob = r.probabilite if r.probabilite is not None else STAGE_PROBABILITY.get(r.etape, _ZERO)
        weighted = (r.montant_xaf * prob).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        if r.date_cloture_prevue is None:
            sans_date_weighted += weighted
            continue
        mois = r.date_cloture_prevue.strftime("%Y-%m")
        bucket = par_mois.setdefault(mois, {"brut": _ZERO, "pondere": _ZERO})
        bucket["brut"] += r.montant_xaf
        bucket["pondere"] += weighted
    prevision = [
        {
            "mois": mois,
            "brut_xaf": str(v["brut"].quantize(Decimal("1"), rounding=ROUND_HALF_UP)),
            "pondere_xaf": str(v["pondere"]),
        }
        for mois, v in sorted(par_mois.items())
    ]
    total_pondere = sum((v["pondere"] for v in par_mois.values()), _ZERO) + sans_date_weighted
    return {
        "prevision": prevision,
        "sans_date_pondere_xaf": str(sans_date_weighted),
        "total_pondere_xaf": str(total_pondere),
    }
