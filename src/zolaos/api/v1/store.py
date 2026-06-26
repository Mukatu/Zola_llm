"""Système de référence léger — Factures (CRUD) + clôture continue.

Profil box. Persistance des factures (`store_invoices`) + endpoint de
**réconciliation temps réel** : à chaque lot de mouvements, on relettre le
registre stocké (clôture continue). Multi-tenant via `tenant_id` (défaut local).
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import date
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from zolaos.agents.erp.achats import (
    OffreFournisseur,
    Supplier,
    comparer_offres,
    score_fournisseur,
    verifier_conformite,
)
from zolaos.agents.erp.compta import ChartOfAccounts, JournalValidator
from zolaos.agents.erp.reconciliation import reconcilier
from zolaos.agents.erp.supply import StockItem, alertes_rupture, analyser_reappro
from zolaos.connectors.models import BankTransaction, Invoice, JournalEntry, JournalLine
from zolaos.db.session import get_session
from zolaos.db.store_repo import (
    InvoiceRepository,
    JournalRepository,
    PurchaseOrderRepository,
    StockRepository,
    SupplierRepository,
)

router = APIRouter(prefix="/v1/erp", tags=["store"])


# ---------------------------------------------------------------- schémas


class InvoiceIn(BaseModel):
    numero: str
    sens: str = "vente"
    tiers: str
    date_emission: date
    date_echeance: date | None = None
    montant_ht_xaf: Decimal = Decimal("0")
    montant_tva_xaf: Decimal | None = None
    montant_ttc_xaf: Decimal = Decimal("0")
    devise: str = "XAF"
    payee: bool = False
    country: str = "cg"


class InvoicePatch(BaseModel):
    tiers: str | None = None
    date_echeance: date | None = None
    montant_ttc_xaf: Decimal | None = None
    payee: bool | None = None


class ReconcileIn(BaseModel):
    transactions: list[BankTransaction] = Field(default_factory=list)
    fenetre_jours: int = Field(default=5, ge=0, le=60)


# ---------------------------------------------------------------- CRUD factures


@router.post("/invoices", status_code=status.HTTP_201_CREATED, summary="Créer une facture")
async def create_invoice(
    body: InvoiceIn,
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    rec = await InvoiceRepository(session).create({**body.model_dump(), "tenant_id": tenant_id})
    await session.commit()
    return rec.to_dict()


@router.get("/invoices", summary="Lister les factures")
async def list_invoices(
    tenant_id: str = "local",
    sens: str | None = None,
    payee: bool | None = None,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    rows = await InvoiceRepository(session).list(tenant_id=tenant_id, sens=sens, payee=payee)
    return {"invoices": [r.to_dict() for r in rows]}


@router.get("/invoices/{invoice_id}", summary="Lire une facture")
async def get_invoice(
    invoice_id: str,
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    rec = await InvoiceRepository(session).get(invoice_id, tenant_id=tenant_id)
    if rec is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="invoice_not_found")
    return rec.to_dict()


@router.patch("/invoices/{invoice_id}", summary="Mettre à jour une facture")
async def patch_invoice(
    invoice_id: str,
    body: InvoicePatch,
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    rec = await InvoiceRepository(session).update(
        invoice_id, tenant_id=tenant_id, fields=body.model_dump(exclude_none=True)
    )
    if rec is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="invoice_not_found")
    await session.commit()
    return rec.to_dict()


@router.post("/invoices/{invoice_id}/pay", summary="Marquer payée")
async def pay_invoice(
    invoice_id: str,
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    rec = await InvoiceRepository(session).mark_paid(invoice_id, tenant_id=tenant_id)
    if rec is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="invoice_not_found")
    await session.commit()
    return rec.to_dict()


@router.delete("/invoices/{invoice_id}", summary="Supprimer une facture")
async def delete_invoice(
    invoice_id: str,
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    ok = await InvoiceRepository(session).delete(invoice_id, tenant_id=tenant_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="invoice_not_found")
    await session.commit()
    return {"deleted": invoice_id}


# ---------------------------------------------------------------- clôture continue


@router.post("/reconcile", summary="Réconciliation temps réel (clôture continue)")
async def reconcile(
    body: ReconcileIn,
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    rows = await InvoiceRepository(session).list(tenant_id=tenant_id, sens="vente", payee=False)
    invoices = [
        Invoice(
            id_externe=r.id,
            numero=r.numero,
            sens="vente",
            tiers=r.tiers,
            date_emission=r.date_emission,
            montant_ht_xaf=r.montant_ht_xaf,
            montant_ttc_xaf=r.montant_ttc_xaf,
            payee=r.payee,
            country=r.country,
        )
        for r in rows
    ]
    report = reconcilier(invoices, body.transactions, fenetre_jours=body.fenetre_jours)
    return {
        "rapprochements": [asdict(x) for x in report.rapprochements],
        "factures_en_attente": [asdict(x) for x in report.factures_en_attente],
        "mouvements_non_rapproches": report.mouvements_non_rapproches,
        "cloture": asdict(report.cloture) if report.cloture else None,
    }


# ---------------------------------------------------------------- écritures comptables


class JournalLineIn(BaseModel):
    compte: str
    libelle: str
    debit_xaf: Decimal = Decimal("0")
    credit_xaf: Decimal = Decimal("0")


class JournalEntryIn(BaseModel):
    date_ecriture: date
    journal: str = "OD"
    libelle: str
    reference: str | None = None
    lignes: list[JournalLineIn] = Field(min_length=1)
    country: str = "cg"
    allow_unbalanced: bool = False


@router.post("/journal", status_code=status.HTTP_201_CREATED, summary="Enregistrer une écriture")
async def create_entry(
    body: JournalEntryIn,
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    entry = JournalEntry(
        date_ecriture=body.date_ecriture,
        journal=body.journal,
        libelle=body.libelle,
        reference=body.reference,
        country=body.country,
        lignes=[JournalLine(**ligne.model_dump()) for ligne in body.lignes],
    )
    report = JournalValidator(ChartOfAccounts.load(body.country)).validate(entry)
    if not report.ok and not body.allow_unbalanced:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "ecriture_invalide", "errors": report.errors},
        )
    lignes_json = [
        {
            "compte": ligne.compte,
            "libelle": ligne.libelle,
            "debit_xaf": str(ligne.debit_xaf),
            "credit_xaf": str(ligne.credit_xaf),
        }
        for ligne in body.lignes
    ]
    rec = await JournalRepository(session).create(
        {
            "tenant_id": tenant_id,
            "date_ecriture": body.date_ecriture,
            "journal": body.journal,
            "libelle": body.libelle,
            "reference": body.reference,
            "lignes": lignes_json,
            "total_debit_xaf": report.total_debit_xaf,
            "total_credit_xaf": report.total_credit_xaf,
            "equilibre": report.ok,
            "country": body.country,
        }
    )
    await session.commit()
    return {**rec.to_dict(), "validation": asdict(report)}


@router.get("/journal", summary="Lister les écritures")
async def list_entries(
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    rows = await JournalRepository(session).list(tenant_id=tenant_id)
    return {"entries": [r.to_dict() for r in rows]}


@router.get("/journal/balance", summary="Balance vivante des comptes (clôture continue)")
async def trial_balance(
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    rows = await JournalRepository(session).list(tenant_id=tenant_id)
    agg: dict[str, dict[str, Decimal]] = {}
    for entry in rows:
        for ligne in entry.lignes:
            acc = agg.setdefault(ligne["compte"], {"debit": Decimal("0"), "credit": Decimal("0")})
            acc["debit"] += Decimal(ligne["debit_xaf"])
            acc["credit"] += Decimal(ligne["credit_xaf"])
    comptes = [
        {
            "compte": compte,
            "debit_xaf": str(v["debit"]),
            "credit_xaf": str(v["credit"]),
            "solde_xaf": str(v["debit"] - v["credit"]),
        }
        for compte, v in sorted(agg.items())
    ]
    total_debit = sum((v["debit"] for v in agg.values()), Decimal("0"))
    total_credit = sum((v["credit"] for v in agg.values()), Decimal("0"))
    return {
        "comptes": comptes,
        "total_debit_xaf": str(total_debit),
        "total_credit_xaf": str(total_credit),
        "equilibre": total_debit == total_credit,
    }


@router.delete("/journal/{entry_id}", summary="Supprimer une écriture")
async def delete_entry(
    entry_id: str,
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    ok = await JournalRepository(session).delete(entry_id, tenant_id=tenant_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="entry_not_found")
    await session.commit()
    return {"deleted": entry_id}


# ---------------------------------------------------------------- stocks


class StockItemIn(BaseModel):
    sku: str
    libelle: str
    quantite_actuelle: Decimal = Decimal("0")
    unite: str = "unité"
    conso_moyenne_jour: Decimal = Decimal("0")
    delai_appro_jours: int = 0
    stock_securite: Decimal = Decimal("0")
    country: str = "cg"


class StockPatch(BaseModel):
    quantite_actuelle: Decimal | None = None
    conso_moyenne_jour: Decimal | None = None
    delai_appro_jours: int | None = None
    stock_securite: Decimal | None = None


@router.post("/stock", status_code=status.HTTP_201_CREATED, summary="Créer un article de stock")
async def create_stock(
    body: StockItemIn,
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    rec = await StockRepository(session).create({**body.model_dump(), "tenant_id": tenant_id})
    await session.commit()
    return rec.to_dict()


@router.get("/stock", summary="Lister les articles de stock")
async def list_stock(
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    rows = await StockRepository(session).list(tenant_id=tenant_id)
    return {"items": [r.to_dict() for r in rows]}


@router.patch("/stock/{item_id}", summary="Mettre à jour un article")
async def patch_stock(
    item_id: str,
    body: StockPatch,
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    rec = await StockRepository(session).update(
        item_id, tenant_id=tenant_id, fields=body.model_dump(exclude_none=True)
    )
    if rec is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="item_not_found")
    await session.commit()
    return rec.to_dict()


@router.delete("/stock/{item_id}", summary="Supprimer un article")
async def delete_stock(
    item_id: str,
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    ok = await StockRepository(session).delete(item_id, tenant_id=tenant_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="item_not_found")
    await session.commit()
    return {"deleted": item_id}


@router.post("/stock/analyze", summary="Réappro + alertes rupture sur le stock stocké")
async def analyze_stock(
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    rows = await StockRepository(session).list(tenant_id=tenant_id)
    items = [
        StockItem(
            sku=r.sku,
            libelle=r.libelle,
            quantite_actuelle=r.quantite_actuelle,
            unite=r.unite,
            conso_moyenne_jour=r.conso_moyenne_jour,
            delai_appro_jours=r.delai_appro_jours,
            stock_securite=r.stock_securite,
            country=r.country,
        )
        for r in rows
    ]
    return {
        "suggestions": [asdict(s) for s in analyser_reappro(items)],
        "alertes": [asdict(a) for a in alertes_rupture(items, horizon_jours=30)],
    }


# ---------------------------------------------------------------- Achats (P2c)


class SupplierIn(BaseModel):
    id_externe: str
    nom: str
    secteur: str | None = None
    note_qualite: Decimal = Field(default=Decimal("0"), ge=0, le=5)
    delai_moyen_jours: int = Field(default=0, ge=0)
    documents_conformite: list[str] = Field(default_factory=list)
    actif: bool = True
    country: str = "cg"


class SupplierPatch(BaseModel):
    nom: str | None = None
    secteur: str | None = None
    note_qualite: Decimal | None = None
    delai_moyen_jours: int | None = None
    documents_conformite: list[str] | None = None
    actif: bool | None = None


class PurchaseOrderLineIn(BaseModel):
    libelle: str
    montant_ht_xaf: Decimal = Decimal("0")


class PurchaseOrderIn(BaseModel):
    id_externe: str
    numero: str
    fournisseur: str
    objet: str = ""
    date_emission: date
    statut: str = "brouillon"
    lignes: list[PurchaseOrderLineIn] = Field(default_factory=list)
    montant_ht_xaf: Decimal = Decimal("0")
    montant_ttc_xaf: Decimal = Decimal("0")
    delai_livraison_jours: int = Field(default=0, ge=0)
    country: str = "cg"


class PurchaseOrderPatch(BaseModel):
    objet: str | None = None
    statut: str | None = None
    montant_ht_xaf: Decimal | None = None
    montant_ttc_xaf: Decimal | None = None
    delai_livraison_jours: int | None = None


def _supplier_of(rec: Any) -> Supplier:
    return Supplier(
        id_externe=rec.id_externe,
        nom=rec.nom,
        secteur=rec.secteur,
        note_qualite=rec.note_qualite,
        delai_moyen_jours=rec.delai_moyen_jours,
        documents_conformite=list(rec.documents_conformite or []),
        actif=rec.actif,
        country=rec.country,
    )


# ----- CRUD fournisseurs -----


@router.post("/suppliers", status_code=status.HTTP_201_CREATED, summary="Créer un fournisseur")
async def create_supplier(
    body: SupplierIn,
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    rec = await SupplierRepository(session).create({**body.model_dump(), "tenant_id": tenant_id})
    await session.commit()
    return rec.to_dict()


@router.get("/suppliers", summary="Lister les fournisseurs")
async def list_suppliers(
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    rows = await SupplierRepository(session).list(tenant_id=tenant_id)
    return {"suppliers": [r.to_dict() for r in rows]}


@router.get("/suppliers/scores", summary="Scoring + conformité des fournisseurs (sur le store)")
async def suppliers_scores(
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    rows = await SupplierRepository(session).list(tenant_id=tenant_id)
    scores = []
    for r in rows:
        sup = _supplier_of(r)
        scores.append(
            {
                "id": r.id,
                **asdict(score_fournisseur(sup)),
                "conformite_manquante": verifier_conformite(sup),
            }
        )
    scores.sort(key=lambda s: s["score"], reverse=True)
    return {"scores": scores}


@router.patch("/suppliers/{supplier_id}", summary="Mettre à jour un fournisseur")
async def patch_supplier(
    supplier_id: str,
    body: SupplierPatch,
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    rec = await SupplierRepository(session).update(
        supplier_id, tenant_id=tenant_id, fields=body.model_dump(exclude_none=True)
    )
    if rec is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="supplier_not_found")
    await session.commit()
    return rec.to_dict()


@router.delete("/suppliers/{supplier_id}", summary="Supprimer un fournisseur")
async def delete_supplier(
    supplier_id: str,
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    ok = await SupplierRepository(session).delete(supplier_id, tenant_id=tenant_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="supplier_not_found")
    await session.commit()
    return {"deleted": supplier_id}


# ----- CRUD bons de commande -----


@router.post(
    "/purchase-orders", status_code=status.HTTP_201_CREATED, summary="Créer un bon de commande"
)
async def create_po(
    body: PurchaseOrderIn,
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    data = body.model_dump()
    data["lignes"] = [
        {"libelle": x["libelle"], "montant_ht_xaf": str(x["montant_ht_xaf"])}
        for x in data["lignes"]
    ]
    rec = await PurchaseOrderRepository(session).create({**data, "tenant_id": tenant_id})
    await session.commit()
    return rec.to_dict()


@router.get("/purchase-orders", summary="Lister les bons de commande")
async def list_pos(
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    rows = await PurchaseOrderRepository(session).list(tenant_id=tenant_id)
    return {"purchase_orders": [r.to_dict() for r in rows]}


@router.get("/purchase-orders/compare", summary="Comparatif des BC (prix/délai, sur le store)")
async def compare_pos(
    tenant_id: str = "local",
    objet: str | None = None,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    rows = await PurchaseOrderRepository(session).list(tenant_id=tenant_id)
    offres = [
        OffreFournisseur(
            id_externe=r.id_externe,
            fournisseur=r.fournisseur,
            objet=r.objet,
            montant_ht_xaf=r.montant_ht_xaf,
            montant_ttc_xaf=r.montant_ttc_xaf,
            delai_livraison_jours=r.delai_livraison_jours,
            country=r.country,
        )
        for r in rows
        if objet is None or r.objet == objet
    ]
    return {"classement": [asdict(c) for c in comparer_offres(offres)]}


@router.patch("/purchase-orders/{po_id}", summary="Mettre à jour un bon de commande")
async def patch_po(
    po_id: str,
    body: PurchaseOrderPatch,
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    rec = await PurchaseOrderRepository(session).update(
        po_id, tenant_id=tenant_id, fields=body.model_dump(exclude_none=True)
    )
    if rec is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="po_not_found")
    await session.commit()
    return rec.to_dict()


@router.delete("/purchase-orders/{po_id}", summary="Supprimer un bon de commande")
async def delete_po(
    po_id: str,
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    ok = await PurchaseOrderRepository(session).delete(po_id, tenant_id=tenant_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="po_not_found")
    await session.commit()
    return {"deleted": po_id}


@router.post(
    "/purchase-orders/{po_id}/receipt", summary="Réceptionner un BC → facture d'achat (clôture)"
)
async def receipt_po(
    po_id: str,
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    pos = PurchaseOrderRepository(session)
    rec = await pos.get(po_id, tenant_id=tenant_id)
    if rec is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="po_not_found")
    if rec.invoice_id is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="deja_receptionne")
    if rec.statut == "brouillon":
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="bon_non_emis")
    inv = await InvoiceRepository(session).create(
        {
            "tenant_id": tenant_id,
            "numero": rec.numero,
            "sens": "achat",
            "tiers": rec.fournisseur,
            "date_emission": rec.date_emission,
            "montant_ht_xaf": rec.montant_ht_xaf,
            "montant_ttc_xaf": rec.montant_ttc_xaf,
            "payee": False,
            "country": rec.country,
        }
    )
    await pos.update(
        po_id, tenant_id=tenant_id, fields={"invoice_id": inv.id, "statut": "receptionne"}
    )
    await session.commit()
    return {"purchase_order": rec.to_dict(), "invoice": inv.to_dict()}
