"""Système de référence léger — Factures (CRUD) + clôture continue.

Profil box. Persistance des factures (`store_invoices`) + endpoint de
**réconciliation temps réel** : à chaque lot de mouvements, on relettre le
registre stocké (clôture continue). Multi-tenant via `tenant_id` (défaut local).
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import date
from decimal import Decimal
from io import BytesIO
from typing import Any

import openpyxl
from fastapi import APIRouter, Depends, HTTPException, Response, status
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
from zolaos.agents.erp.engagements import (
    Engagement,
    PilotageBudgetaire,
    detect_alertes,
    engagement_stats,
    pilotage_budgetaire,
)
from zolaos.agents.erp.inventory import (
    SEUIL_VALIDATION_DEFAUT_XAF,
    ArticleStock,
    PilotageStock,
    StockInsuffisant,
    appliquer_mouvement,
    estimer_valeur_mouvement,
    pilotage_stock,
    requiert_double_validation,
)
from zolaos.agents.erp.reconciliation import reconcilier
from zolaos.agents.erp.supply import StockItem, alertes_rupture, analyser_reappro
from zolaos.agents.erp.treasury import (
    SEUIL_DECAISSEMENT_DEFAUT_XAF,
    CompteTresorerie,
    FluxRapprochable,
    FluxTresorerie,
    LigneReleve,
    position_tresorerie,
    rapprocher,
)
from zolaos.connectors.models import BankTransaction, Invoice, JournalEntry, JournalLine
from zolaos.db.session import get_session
from zolaos.db.store_repo import (
    BankAccountRepository,
    CashFlowRepository,
    EngagementRepository,
    InvoiceRepository,
    JournalRepository,
    PurchaseBudgetRepository,
    PurchaseOrderRepository,
    StockMoveRepository,
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


# ---------------------------------------------------------------- mouvements de stock (STOCK-1)


class StockMoveIn(BaseModel):
    reference: str
    type: str = "entree"  # entree | sortie | ajustement | transfert
    sku: str
    quantite: Decimal = Decimal("0")
    cout_unitaire_xaf: Decimal | None = None
    emplacement: str | None = None
    emplacement_dest: str | None = None
    lot: str | None = None
    date_peremption: date | None = None
    motif: str = ""
    date_mouvement: date
    country: str = "cg"


@router.post(
    "/stock-moves", status_code=status.HTTP_201_CREATED, summary="Créer un mouvement (brouillon)"
)
async def create_stock_move(
    body: StockMoveIn,
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    rec = await StockMoveRepository(session).create({**body.model_dump(), "tenant_id": tenant_id})
    await session.commit()
    return rec.to_dict()


@router.get("/stock-moves", summary="Lister les mouvements de stock")
async def list_stock_moves(
    tenant_id: str = "local",
    sku: str | None = None,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    rows = await StockMoveRepository(session).list(tenant_id=tenant_id, sku=sku)
    return {"moves": [r.to_dict() for r in rows]}


@router.post(
    "/stock-moves/{move_id}/validate",
    summary="Valider un mouvement (workflow à seuil : N1 puis N2 au-delà du seuil)",
)
async def validate_stock_move(
    move_id: str,
    tenant_id: str = "local",
    seuil_xaf: Decimal = SEUIL_VALIDATION_DEFAUT_XAF,
    autoriser_negatif: bool = False,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    moves = StockMoveRepository(session)
    move = await moves.get(move_id, tenant_id=tenant_id)
    if move is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="move_not_found")
    if move.statut == "valide":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="deja_valide")

    items = StockRepository(session)
    item = await items.get_by_sku(move.sku, tenant_id=tenant_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="article_inconnu")

    estimee = estimer_valeur_mouvement(
        type=move.type,
        quantite=move.quantite,
        pmp_actuel=item.pmp_xaf,
        cout_unitaire=move.cout_unitaire_xaf,
    )
    # Gouvernance : 1er palier (N1) si au-dessus du seuil et encore en brouillon.
    if move.statut == "brouillon" and requiert_double_validation(estimee, seuil_xaf):
        move.statut = "valide_n1"
        move.valeur_xaf = estimee  # aperçu (non appliqué)
        await session.flush()
        await session.commit()
        return {"move": move.to_dict(), "applique": False, "requiert_n2": True}

    # Application réelle : brouillon sous le seuil, ou N1 → N2 (2e validation).
    try:
        res = appliquer_mouvement(
            type=move.type,
            quantite=move.quantite,
            quantite_actuelle=item.quantite_actuelle,
            pmp_actuel=item.pmp_xaf,
            cout_unitaire=move.cout_unitaire_xaf,
            autoriser_negatif=autoriser_negatif,
        )
    except StockInsuffisant as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="stock_insuffisant"
        ) from exc

    item.quantite_actuelle = res.nouvelle_quantite
    item.pmp_xaf = res.nouveau_pmp_xaf
    move.valeur_xaf = res.valeur_mouvement_xaf
    move.statut = "valide"
    await session.flush()
    await session.commit()
    return {"move": move.to_dict(), "article": item.to_dict(), "applique": True}


@router.delete("/stock-moves/{move_id}", summary="Supprimer un mouvement (brouillon uniquement)")
async def delete_stock_move(
    move_id: str,
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    moves = StockMoveRepository(session)
    move = await moves.get(move_id, tenant_id=tenant_id)
    if move is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="move_not_found")
    if move.statut == "valide":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="mouvement_valide")
    await moves.delete(move_id, tenant_id=tenant_id)
    await session.commit()
    return {"deleted": move_id}


# ---------------------------------------------------------------- inventaire physique (STOCK-3)


class InventaireLigne(BaseModel):
    sku: str
    quantite_comptee: Decimal


class InventaireIn(BaseModel):
    comptages: list[InventaireLigne] = Field(default_factory=list)
    date_inventaire: date | None = None


@router.post("/stock/inventory", summary="Inventaire physique : écarts → ajustements (brouillon)")
async def stock_inventory(
    body: InventaireIn,
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Compare le compté au théorique ; crée un **ajustement brouillon** par écart
    (à valider ensuite via le workflow). Ne modifie pas directement le stock."""
    items = StockRepository(session)
    moves = StockMoveRepository(session)
    jour = body.date_inventaire or date.today()
    resultats: list[dict[str, Any]] = []
    for c in body.comptages:
        item = await items.get_by_sku(c.sku, tenant_id=tenant_id)
        if item is None:
            resultats.append({"sku": c.sku, "erreur": "article_inconnu"})
            continue
        ecart = c.quantite_comptee - item.quantite_actuelle
        move_id = None
        if ecart != 0:
            rec = await moves.create(
                {
                    "tenant_id": tenant_id,
                    "reference": f"INV-{jour.isoformat()}-{c.sku}",
                    "type": "ajustement",
                    "sku": c.sku,
                    "quantite": ecart,
                    "motif": "Inventaire physique",
                    "date_mouvement": jour,
                }
            )
            move_id = rec.id
        resultats.append(
            {
                "sku": c.sku,
                "theorique": str(item.quantite_actuelle),
                "comptee": str(c.quantite_comptee),
                "ecart": str(ecart),
                "ajustement_id": move_id,
            }
        )
    await session.commit()
    nb_ecarts = sum(1 for r in resultats if r.get("ajustement_id"))
    return {"date_inventaire": jour.isoformat(), "nb_ecarts": nb_ecarts, "resultats": resultats}


@router.get("/stock/peremption", summary="Alertes de péremption (lots proches/expirés)")
async def stock_peremption(
    tenant_id: str = "local",
    horizon_jours: int = 30,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    rows = await StockMoveRepository(session).list(tenant_id=tenant_id)
    jour = date.today()
    alertes: list[dict[str, Any]] = []
    for m in rows:
        if m.type != "entree" or m.statut != "valide" or m.date_peremption is None:
            continue
        jours = (m.date_peremption - jour).days
        if jours <= horizon_jours:
            alertes.append(
                {
                    "sku": m.sku,
                    "lot": m.lot,
                    "quantite": str(m.quantite),
                    "date_peremption": m.date_peremption.isoformat(),
                    "jours_restants": jours,
                    "niveau": "expire" if jours < 0 else "proche",
                }
            )
    alertes.sort(key=lambda a: a["jours_restants"])
    return {"horizon_jours": horizon_jours, "alertes": alertes}


# ---------------------------------------------------------------- pilotage stock (STOCK-4)


async def _articles_stock(session: AsyncSession, tenant_id: str) -> list[ArticleStock]:
    rows = await StockRepository(session).list(tenant_id=tenant_id)
    return [
        ArticleStock(
            sku=r.sku,
            libelle=r.libelle,
            quantite_actuelle=r.quantite_actuelle,
            conso_moyenne_jour=r.conso_moyenne_jour,
            stock_securite=r.stock_securite,
            pmp_xaf=r.pmp_xaf,
        )
        for r in rows
    ]


def build_pilotage_stock_xlsx(p: PilotageStock) -> bytes:
    """Classeur de pilotage stock : synthèse + détail par article (ABC, couverture)."""
    wb = openpyxl.Workbook()
    syn = wb.active
    syn.title = "Synthèse"
    syn.append(["Pilotage des stocks"])
    syn.append(["Articles", p.nb_articles])
    syn.append(["Valorisation totale (XAF)", float(p.valorisation_totale_xaf)])
    syn.append(["Ruptures", p.nb_rupture])
    syn.append(["Sous stock de sécurité", p.nb_sous_securite])
    syn.append(["Taux de rupture (%)", float(p.taux_rupture_pct)])
    syn.append(
        [
            "Couverture moyenne (j)",
            float(p.couverture_moyenne_jours) if p.couverture_moyenne_jours is not None else "",
        ]
    )
    syn.append(["Articles dormants", p.dormant_nb])
    syn.append(["Valeur dormante (XAF)", float(p.dormant_valeur_xaf)])
    syn.append(
        [
            "ABC (A/B/C)",
            f"{p.repartition_abc['A']}/{p.repartition_abc['B']}/{p.repartition_abc['C']}",
        ]
    )

    det = wb.create_sheet("Par article")
    det.append(
        [
            "SKU",
            "Libellé",
            "Quantité",
            "Valeur stock XAF",
            "Couverture j",
            "Rotation/an",
            "Classe ABC",
        ]
    )
    for a in p.par_article:
        det.append(
            [
                a.sku,
                a.libelle,
                float(a.quantite),
                float(a.valeur_stock_xaf),
                float(a.couverture_jours) if a.couverture_jours is not None else "",
                float(a.rotation_annuelle) if a.rotation_annuelle is not None else "",
                a.classe_abc,
            ]
        )
    bio = BytesIO()
    wb.save(bio)
    return bio.getvalue()


@router.get("/stock/pilotage", summary="Pilotage stock : valorisation, rotation, rupture, ABC")
async def stock_pilotage(
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    p = pilotage_stock(await _articles_stock(session, tenant_id))
    return {"pilotage": asdict(p)}


@router.get("/stock/pilotage/export", summary="Exporter le pilotage stock (.xlsx)")
async def export_stock_pilotage(
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> Response:
    p = pilotage_stock(await _articles_stock(session, tenant_id))
    return Response(
        content=build_pilotage_stock_xlsx(p),
        media_type=_XLSX_MEDIA,
        headers={"Content-Disposition": 'attachment; filename="pilotage_stock.xlsx"'},
    )


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


class ReceiptLigneStock(BaseModel):
    sku: str
    quantite: Decimal = Decimal("0")
    cout_unitaire_xaf: Decimal | None = None


class ReceiptIn(BaseModel):
    # Lignes optionnelles : génèrent des entrées de stock (brouillon) à la réception.
    entrees: list[ReceiptLigneStock] = Field(default_factory=list)


@router.post(
    "/purchase-orders/{po_id}/receipt",
    summary="Réceptionner un BC → facture d'achat (+ entrées de stock optionnelles)",
)
async def receipt_po(
    po_id: str,
    body: ReceiptIn | None = None,
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
    # Boucle Achats → Stock : entrées de stock (brouillon) à valider ensuite.
    entrees_stock: list[dict[str, Any]] = []
    if body is not None and body.entrees:
        moves = StockMoveRepository(session)
        for i, e in enumerate(body.entrees, start=1):
            mv = await moves.create(
                {
                    "tenant_id": tenant_id,
                    "reference": f"BC-{rec.numero}-{i}",
                    "type": "entree",
                    "sku": e.sku,
                    "quantite": e.quantite,
                    "cout_unitaire_xaf": e.cout_unitaire_xaf,
                    "motif": f"Réception BC {rec.numero}",
                    "date_mouvement": rec.date_emission,
                }
            )
            entrees_stock.append(mv.to_dict())
    await session.commit()
    return {
        "purchase_order": rec.to_dict(),
        "invoice": inv.to_dict(),
        "entrees_stock": entrees_stock,
    }


# ---------------------------------------------------------------- Engagements (Achats v2)


class EngagementIn(BaseModel):
    numero_eb: str
    numero_da: str | None = None
    numero_bc: str | None = None
    date_eb: date | None = None
    date_da: date | None = None
    date_bc: date | None = None
    direction: str | None = None
    service: str | None = None
    demandeur: str | None = None
    acheteur: str | None = None
    fournisseur: str | None = None
    description_besoin: str = ""
    description_da: str = ""
    description_bc: str = ""
    estimation_xaf: Decimal = Decimal("0")
    montant_xaf: Decimal = Decimal("0")
    statut_ebda: str = ""
    statut_bc: str = ""
    country: str = "cg"


class EngagementPatch(BaseModel):
    numero_da: str | None = None
    numero_bc: str | None = None
    date_da: date | None = None
    date_bc: date | None = None
    acheteur: str | None = None
    fournisseur: str | None = None
    description_da: str | None = None
    description_bc: str | None = None
    estimation_xaf: Decimal | None = None
    montant_xaf: Decimal | None = None
    statut_ebda: str | None = None
    statut_bc: str | None = None


def _engagement_of(rec: Any) -> Engagement:
    return Engagement(
        numero_eb=rec.numero_eb,
        numero_da=rec.numero_da,
        numero_bc=rec.numero_bc,
        date_eb=rec.date_eb,
        date_da=rec.date_da,
        date_bc=rec.date_bc,
        direction=rec.direction,
        service=rec.service,
        demandeur=rec.demandeur,
        acheteur=rec.acheteur,
        fournisseur=rec.fournisseur,
        estimation_xaf=rec.estimation_xaf,
        montant_xaf=rec.montant_xaf,
        statut_ebda=rec.statut_ebda,
        statut_bc=rec.statut_bc,
    )


@router.post("/engagements", status_code=status.HTTP_201_CREATED, summary="Créer un engagement")
async def create_engagement(
    body: EngagementIn,
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    rec = await EngagementRepository(session).create({**body.model_dump(), "tenant_id": tenant_id})
    await session.commit()
    return rec.to_dict()


@router.get("/engagements", summary="Lister les engagements (chaîne EB→DA→BC)")
async def list_engagements(
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    rows = await EngagementRepository(session).list(tenant_id=tenant_id)
    return {"engagements": [r.to_dict() for r in rows]}


@router.get(
    "/engagements/stats", summary="Indicateurs d'engagement (transformation, écarts, funnel)"
)
async def engagements_stats(
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    rows = await EngagementRepository(session).list(tenant_id=tenant_id)
    engagements = [_engagement_of(r) for r in rows]
    stats = engagement_stats(engagements)
    alertes = detect_alertes(engagements)
    return {"stats": asdict(stats), "alertes": [asdict(a) for a in alertes]}


@router.patch("/engagements/{engagement_id}", summary="Mettre à jour un engagement")
async def patch_engagement(
    engagement_id: str,
    body: EngagementPatch,
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    rec = await EngagementRepository(session).update(
        engagement_id, tenant_id=tenant_id, fields=body.model_dump(exclude_none=True)
    )
    if rec is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="engagement_not_found")
    await session.commit()
    return rec.to_dict()


@router.delete("/engagements/{engagement_id}", summary="Supprimer un engagement")
async def delete_engagement(
    engagement_id: str,
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    ok = await EngagementRepository(session).delete(engagement_id, tenant_id=tenant_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="engagement_not_found")
    await session.commit()
    return {"deleted": engagement_id}


# ---------------------------------------------------------------- Pilotage budgétaire (CDG)


class PurchaseBudgetIn(BaseModel):
    direction: str
    exercice: str
    budget_xaf: Decimal = Decimal("0")


@router.post(
    "/purchase-budgets", status_code=status.HTTP_201_CREATED, summary="Définir un budget achats"
)
async def set_purchase_budget(
    body: PurchaseBudgetIn,
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Upsert : un seul budget par (direction, exercice)."""
    rec = await PurchaseBudgetRepository(session).upsert(
        tenant_id=tenant_id,
        direction=body.direction,
        exercice=body.exercice,
        budget_xaf=body.budget_xaf,
    )
    await session.commit()
    return rec.to_dict()


@router.get("/purchase-budgets", summary="Lister les budgets achats")
async def list_purchase_budgets(
    tenant_id: str = "local",
    exercice: str | None = None,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    rows = await PurchaseBudgetRepository(session).list(tenant_id=tenant_id)
    if exercice is not None:
        rows = [r for r in rows if r.exercice == exercice]
    return {"budgets": [r.to_dict() for r in rows]}


@router.delete("/purchase-budgets/{budget_id}", summary="Supprimer un budget achats")
async def delete_purchase_budget(
    budget_id: str,
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    ok = await PurchaseBudgetRepository(session).delete(budget_id, tenant_id=tenant_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="budget_not_found")
    await session.commit()
    return {"deleted": budget_id}


_XLSX_MEDIA = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def build_pilotage_xlsx(pilotage: PilotageBudgetaire, exercice: str | None) -> bytes:
    """Classeur CDG : synthèse + engagé/budget par direction + mensuel + fournisseurs."""
    wb = openpyxl.Workbook()

    syn = wb.active
    syn.title = "Synthèse"
    syn.append(["Pilotage des achats (engagé vs budget)"])
    syn.append(["Exercice", exercice or "tous"])
    syn.append([])
    syn.append(["Budget total (XAF)", float(pilotage.budget_total_xaf)])
    syn.append(["Engagé total (XAF)", float(pilotage.engage_total_xaf)])
    syn.append(["Reste (XAF)", float(pilotage.reste_total_xaf)])
    syn.append(["Consommation (%)", float(pilotage.consommation_pct)])

    dirs = wb.create_sheet("Par direction")
    dirs.append(
        ["Direction", "Budget XAF", "Engagé XAF", "Reste XAF", "Consommation %", "Niveau", "Nb"]
    )
    for d in pilotage.par_direction:
        dirs.append(
            [
                d.direction,
                float(d.budget_xaf),
                float(d.engage_xaf),
                float(d.reste_xaf),
                float(d.consommation_pct),
                d.niveau,
                d.nb,
            ]
        )

    mois = wb.create_sheet("Par mois")
    mois.append(["Mois", "Engagé XAF"])
    for s in pilotage.serie_mensuelle:
        mois.append([s.mois, float(s.engage_xaf)])

    four = wb.create_sheet("Top fournisseurs")
    four.append(["Fournisseur", "Engagé XAF", "Nb"])
    for f in pilotage.top_fournisseurs:
        four.append([f.fournisseur, float(f.engage_xaf), f.nb])

    bio = BytesIO()
    wb.save(bio)
    return bio.getvalue()


async def _compute_pilotage(
    session: AsyncSession,
    *,
    tenant_id: str,
    exercice: str | None,
    date_debut: date | None,
    date_fin: date | None,
) -> PilotageBudgetaire:
    eng_rows = await EngagementRepository(session).list(tenant_id=tenant_id)
    budget_rows = await PurchaseBudgetRepository(session).list(tenant_id=tenant_id)

    def _ref(r: Any) -> date | None:
        return r.date_bc or r.date_da or r.date_eb

    def _garde(r: Any) -> bool:
        d = _ref(r)
        if exercice is not None and (d is None or d.strftime("%Y") != exercice):
            return False
        if date_debut is not None and (d is None or d < date_debut):
            return False
        if date_fin is not None and (d is None or d > date_fin):
            return False
        return True

    engagements = [_engagement_of(r) for r in eng_rows if _garde(r)]
    budget_par_direction: dict[str, Decimal] = {}
    for b in budget_rows:
        if exercice is None or b.exercice == exercice:
            budget_par_direction[b.direction] = (
                budget_par_direction.get(b.direction, Decimal("0")) + b.budget_xaf
            )
    return pilotage_budgetaire(engagements, budget_par_direction)


@router.get("/engagements/pilotage", summary="Pilotage CDG : engagé vs budget par direction")
async def engagements_pilotage(
    tenant_id: str = "local",
    exercice: str | None = None,
    date_debut: date | None = None,
    date_fin: date | None = None,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    pilotage = await _compute_pilotage(
        session, tenant_id=tenant_id, exercice=exercice, date_debut=date_debut, date_fin=date_fin
    )
    return {"exercice": exercice, "pilotage": asdict(pilotage)}


@router.get("/engagements/pilotage/export", summary="Exporter le pilotage CDG (.xlsx)")
async def export_pilotage(
    tenant_id: str = "local",
    exercice: str | None = None,
    date_debut: date | None = None,
    date_fin: date | None = None,
    session: AsyncSession = Depends(get_session),
) -> Response:
    pilotage = await _compute_pilotage(
        session, tenant_id=tenant_id, exercice=exercice, date_debut=date_debut, date_fin=date_fin
    )
    content = build_pilotage_xlsx(pilotage, exercice)
    nom = f"pilotage_achats_{exercice or 'tous'}"
    return Response(
        content=content,
        media_type=_XLSX_MEDIA,
        headers={"Content-Disposition": f'attachment; filename="{nom}.xlsx"'},
    )


# ---------------------------------------------------------------- Trésorerie (TRESO-1)


class BankAccountIn(BaseModel):
    code: str
    libelle: str
    banque: str = ""
    type: str = "banque"  # banque | caisse | mobile_money
    devise: str = "XAF"
    iban: str | None = None
    solde_initial_xaf: Decimal = Decimal("0")
    country: str = "cg"


class BankAccountPatch(BaseModel):
    libelle: str | None = None
    banque: str | None = None
    type: str | None = None
    iban: str | None = None
    solde_initial_xaf: Decimal | None = None


class CashFlowIn(BaseModel):
    reference: str
    compte_code: str
    sens: str = "encaissement"  # encaissement | decaissement
    montant_xaf: Decimal = Decimal("0")
    date_operation: date
    date_prevue: date | None = None
    statut: str = "realise"  # prevu | realise
    categorie: str = ""
    tiers: str = ""
    libelle: str = ""
    mode: str = "virement"
    invoice_id: str | None = None
    country: str = "cg"


# ----- comptes -----


@router.post("/bank-accounts", status_code=status.HTTP_201_CREATED, summary="Créer un compte")
async def create_bank_account(
    body: BankAccountIn,
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    rec = await BankAccountRepository(session).create({**body.model_dump(), "tenant_id": tenant_id})
    await session.commit()
    return rec.to_dict()


@router.get("/bank-accounts", summary="Lister les comptes de trésorerie")
async def list_bank_accounts(
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    rows = await BankAccountRepository(session).list(tenant_id=tenant_id)
    return {"accounts": [r.to_dict() for r in rows]}


@router.patch("/bank-accounts/{account_id}", summary="Mettre à jour un compte")
async def patch_bank_account(
    account_id: str,
    body: BankAccountPatch,
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    rec = await BankAccountRepository(session).update(
        account_id, tenant_id=tenant_id, fields=body.model_dump(exclude_none=True)
    )
    if rec is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="account_not_found")
    await session.commit()
    return rec.to_dict()


@router.delete("/bank-accounts/{account_id}", summary="Supprimer un compte")
async def delete_bank_account(
    account_id: str,
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    ok = await BankAccountRepository(session).delete(account_id, tenant_id=tenant_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="account_not_found")
    await session.commit()
    return {"deleted": account_id}


# ----- flux -----


@router.post("/cash-flows", status_code=status.HTTP_201_CREATED, summary="Créer un flux")
async def create_cash_flow(
    body: CashFlowIn,
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    rec = await CashFlowRepository(session).create({**body.model_dump(), "tenant_id": tenant_id})
    await session.commit()
    return rec.to_dict()


@router.get("/cash-flows", summary="Lister les flux de trésorerie")
async def list_cash_flows(
    tenant_id: str = "local",
    compte_code: str | None = None,
    statut: str | None = None,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    rows = await CashFlowRepository(session).list(
        tenant_id=tenant_id, compte_code=compte_code, statut=statut
    )
    return {"flows": [r.to_dict() for r in rows]}


@router.delete("/cash-flows/{flow_id}", summary="Supprimer un flux")
async def delete_cash_flow(
    flow_id: str,
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    ok = await CashFlowRepository(session).delete(flow_id, tenant_id=tenant_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="flow_not_found")
    await session.commit()
    return {"deleted": flow_id}


@router.get("/treasury/position", summary="Position de trésorerie (réalisée et projetée)")
async def treasury_position(
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    accounts = await BankAccountRepository(session).list(tenant_id=tenant_id)
    flows = await CashFlowRepository(session).list(tenant_id=tenant_id)
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
    return {"position": asdict(position_tresorerie(comptes, flux))}


# ----- gouvernance : validation des décaissements (TRESO-3) -----


@router.post(
    "/cash-flows/{flow_id}/approve",
    summary="Approuver un décaissement (workflow à seuil : N1 puis N2)",
)
async def approve_cash_flow(
    flow_id: str,
    tenant_id: str = "local",
    seuil_xaf: Decimal = SEUIL_DECAISSEMENT_DEFAUT_XAF,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    flows = CashFlowRepository(session)
    flow = await flows.get(flow_id, tenant_id=tenant_id)
    if flow is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="flow_not_found")
    if flow.sens != "decaissement":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="seuls_decaissements"
        )
    if flow.statut == "realise":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="deja_execute")

    # 1er palier (N1) si au-dessus du seuil et pas encore validé une fois.
    if flow.niveau_validation == "" and flow.montant_xaf > seuil_xaf:
        flow.niveau_validation = "n1"
        await session.flush()
        await session.commit()
        return {"flow": flow.to_dict(), "execute": False, "requiert_n2": True}

    # Exécution : sous le seuil, ou 2e validation (N2).
    flow.niveau_validation = "validee"
    flow.statut = "realise"
    await session.flush()
    await session.commit()
    return {"flow": flow.to_dict(), "execute": True}


# ----- rapprochement bancaire (TRESO-3) -----


class ReleveLigneIn(BaseModel):
    date: date
    montant_xaf: Decimal
    sens: str  # encaissement | decaissement
    libelle: str = ""


class ReconcileTresoIn(BaseModel):
    releve: list[ReleveLigneIn] = Field(default_factory=list)
    compte_code: str | None = None
    fenetre_jours: int = Field(default=5, ge=0, le=60)


@router.post("/treasury/reconcile", summary="Rapprochement bancaire (relevé vs flux réalisés)")
async def treasury_reconcile(
    body: ReconcileTresoIn,
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    repo = CashFlowRepository(session)
    rows = await repo.list(tenant_id=tenant_id, compte_code=body.compte_code, statut="realise")
    candidats = [r for r in rows if not r.rapproche]
    flux = [
        FluxRapprochable(
            id=r.id,
            compte_code=r.compte_code,
            sens=r.sens,
            montant_xaf=r.montant_xaf,
            date_operation=r.date_operation,
        )
        for r in candidats
    ]
    releve = [
        LigneReleve(date=x.date, montant_xaf=x.montant_xaf, sens=x.sens, libelle=x.libelle)
        for x in body.releve
    ]
    res = rapprocher(flux, releve, fenetre_jours=body.fenetre_jours)
    # marque les flux appariés comme rapprochés
    appariés = {r.flux_id for r in res.rapprochements}
    for r in candidats:
        if r.id in appariés:
            r.rapproche = True
    await session.flush()
    await session.commit()
    return {
        "rapprochements": [asdict(r) for r in res.rapprochements],
        "flux_non_rapproches": res.flux_non_rapproches,
        "releve_non_rapproche": res.releve_non_rapproche,
        "taux_rapprochement_pct": str(res.taux_rapprochement_pct),
    }
