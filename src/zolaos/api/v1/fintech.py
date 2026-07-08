"""Endpoints Fintech (profil box) — scoring crédit & KYC/AML.

- Calcul « à la volée » (sans persistance) : ``/score``, ``/kyc``, ``/aml``.
- Persistance (FINTECH-3) : dossiers de crédit (``/applications``) et registres
  KYC (``/kyc-records``) — l'évaluation déterministe est figée à la création,
  puis un workflow de décision humaine porte le ``statut``. Multi-tenant.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from zolaos.agents.fintech.amortization import build_schedule
from zolaos.agents.fintech.cohortes import cohortes
from zolaos.agents.fintech.kyc import (
    KycProfile,
    Transaction,
    evaluate_aml,
    evaluate_kyc,
)
from zolaos.agents.fintech.portfolio import portfolio_stats
from zolaos.agents.fintech.scoring import (
    BAREME_DEFAUT,
    CreditRequest,
    CreditScore,
    ScoringBareme,
    score_credit,
)
from zolaos.db.session import get_session
from zolaos.db.store_repo import (
    CreditApplicationRepository,
    KycRecordRepository,
    LoanInstallmentRepository,
)
from zolaos.imports.framework import Column, EntitySpec, build_template, parse_sheet, validate_row

router = APIRouter(prefix="/v1/fintech", tags=["fintech"])

_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

# Colonnes d'admission d'un dossier (le score et la décision sont CALCULÉS à
# l'import, jamais saisis). Sert au modèle .xlsx, au parsing et à la validation.
_INTAKE = EntitySpec(
    entity="credit_applications",
    label="Dossiers de credit",
    model=CreditRequest,
    columns=(
        Column("client", "str", required=True, aliases=("demandeur", "nom", "emprunteur")),
        Column(
            "revenu_mensuel_xaf",
            "decimal",
            required=True,
            help="Revenu mensuel net (XAF)",
            aliases=("revenu", "revenu mensuel", "salaire"),
        ),
        Column(
            "charges_mensuelles_xaf",
            "decimal",
            help="Dettes/loyers mensuels existants (XAF)",
            aliases=("charges", "charges mensuelles", "dettes"),
        ),
        Column(
            "montant_demande_xaf",
            "decimal",
            required=True,
            help="Montant du crédit demandé (XAF)",
            aliases=("montant", "montant demande", "credit demande"),
        ),
        Column("duree_mois", "int", required=True, help="Durée (mois)", aliases=("duree", "nb mois")),
        Column(
            "anciennete_activite_mois",
            "int",
            help="Ancienneté de l'activité (mois)",
            aliases=("anciennete", "anciennete mois"),
        ),
        Column(
            "incidents_paiement",
            "int",
            help="Nb d'incidents passés connus",
            aliases=("incidents", "impayes anterieurs"),
        ),
        Column("epargne_xaf", "decimal", help="Épargne / apport (XAF)", aliases=("epargne", "apport")),
        Column("garanties_xaf", "decimal", help="Valeur des garanties (XAF)", aliases=("garanties", "caution")),
        Column(
            "type_emploi",
            "str",
            enum=("salarie_public", "salarie_prive", "independant", "informel"),
            help="Type d'emploi",
            aliases=("emploi", "statut emploi", "profession"),
        ),
    ),
)


def _application_record(
    tenant_id: str, client: str, dossier: CreditRequest, res: CreditScore, numero: str
) -> dict[str, Any]:
    """Instantané persistable d'un dossier scoré (partagé création/import)."""
    return {
        "tenant_id": tenant_id,
        "numero": numero,
        "client": client,
        "montant_demande_xaf": dossier.montant_demande_xaf,
        "duree_mois": dossier.duree_mois,
        "score": res.score,
        "grade": res.grade,
        "decision": res.decision,
        "statut": "evaluee",
        "taux_endettement_pct": res.taux_endettement_pct,
        "mensualite_xaf": res.mensualite_estimee_xaf,
        "montant_max_xaf": res.montant_max_suggere_xaf,
        "dossier": dossier.model_dump(mode="json"),
        "resultat": res.model_dump(mode="json"),
    }

_STATUTS_CREDIT = {"evaluee", "accordee", "refusee", "decaissee", "cloturee"}
_STATUTS_KYC = {"a_valider", "valide", "refuse"}


# ------------------------------------------------------------- calcul à la volée


class ScoreRequest(BaseModel):
    dossier: CreditRequest
    bareme: ScoringBareme | None = None


@router.post("/score", summary="Scoring de crédit déterministe (aide à la décision)")
def fintech_score(req: ScoreRequest) -> dict[str, Any]:
    return score_credit(req.dossier, req.bareme).model_dump(mode="json")


@router.post("/kyc", summary="Évaluation KYC : complétude, risque, vigilance")
def fintech_kyc(profile: KycProfile) -> dict[str, Any]:
    return evaluate_kyc(profile).model_dump(mode="json")


class AmlRequest(BaseModel):
    transactions: list[Transaction] = Field(default_factory=list)


@router.post("/aml", summary="Surveillance AML : seuils, structuration, espèces")
def fintech_aml(req: AmlRequest) -> dict[str, Any]:
    return evaluate_aml(req.transactions).model_dump(mode="json")


# ------------------------------------------------------------ dossiers de crédit


class ApplicationCreate(BaseModel):
    client: str
    dossier: CreditRequest
    numero: str | None = None
    bareme: ScoringBareme | None = None


class DecisionIn(BaseModel):
    statut: str
    commentaire: str | None = None


@router.post(
    "/applications",
    status_code=status.HTTP_201_CREATED,
    summary="Évaluer et enregistrer un dossier de crédit",
)
async def create_application(
    body: ApplicationCreate,
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    res = score_credit(body.dossier, body.bareme)
    numero = body.numero or f"CR-{int(datetime.now(UTC).timestamp())}"
    rec = await CreditApplicationRepository(session).create(
        _application_record(tenant_id, body.client, body.dossier, res, numero)
    )
    await session.commit()
    return rec.to_dict()


@router.get("/applications", summary="Lister les dossiers de crédit")
async def list_applications(
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    rows = await CreditApplicationRepository(session).list(tenant_id=tenant_id)
    rows.sort(key=lambda r: r.created_at, reverse=True)
    return {"applications": [r.to_dict() for r in rows]}


@router.get("/applications/{app_id}", summary="Lire un dossier de crédit")
async def get_application(
    app_id: str,
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    rec = await CreditApplicationRepository(session).get(app_id, tenant_id=tenant_id)
    if rec is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="application_not_found")
    return rec.to_dict()


@router.post("/applications/{app_id}/decision", summary="Décision/suivi d'un dossier")
async def decide_application(
    app_id: str,
    body: DecisionIn,
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    if body.statut not in _STATUTS_CREDIT:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"statut_invalide (attendu : {sorted(_STATUTS_CREDIT)})",
        )
    rec = await CreditApplicationRepository(session).update(
        app_id, tenant_id=tenant_id, fields={"statut": body.statut, "commentaire": body.commentaire}
    )
    if rec is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="application_not_found")
    await session.commit()
    return rec.to_dict()


@router.delete("/applications/{app_id}", summary="Supprimer un dossier de crédit")
async def delete_application(
    app_id: str,
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    ok = await CreditApplicationRepository(session).delete(app_id, tenant_id=tenant_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="application_not_found")
    await session.commit()
    return {"status": "deleted"}


# --------------------------------------------------- échéancier de remboursement


class DisburseIn(BaseModel):
    date_decaissement: date | None = None
    taux_annuel: Decimal | None = None  # indicatif, défaut = barème


class PayIn(BaseModel):
    montant: Decimal | None = None  # None → solde intégral de l'échéance
    date_paiement: date | None = None


@router.post("/applications/{app_id}/disburse", summary="Décaisser + générer l'échéancier")
async def disburse(
    app_id: str,
    body: DisburseIn,
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    apps = CreditApplicationRepository(session)
    app = await apps.get(app_id, tenant_id=tenant_id)
    if app is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="application_not_found")
    if app.statut != "accordee":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="dossier_non_accorde (décaissement réservé aux dossiers accordés)",
        )
    taux = body.taux_annuel if body.taux_annuel is not None else BAREME_DEFAUT.taux_annuel_indicatif
    debut = body.date_decaissement or datetime.now(UTC).date()
    schedule = build_schedule(app.montant_demande_xaf, taux, app.duree_mois, debut)
    inst_repo = LoanInstallmentRepository(session)
    for e in schedule:
        await inst_repo.create(
            {
                "tenant_id": tenant_id,
                "application_id": app_id,
                "numero": e.numero,
                "date_echeance": e.date_echeance,
                "principal_xaf": e.principal_xaf,
                "interet_xaf": e.interet_xaf,
                "montant_xaf": e.montant_xaf,
                "statut": "a_venir",
            }
        )
    await apps.update(
        app_id, tenant_id=tenant_id, fields={"statut": "decaissee", "date_decaissement": debut}
    )
    await session.commit()
    rows = await inst_repo.list_for_application(app_id, tenant_id=tenant_id)
    return {"statut": "decaissee", "echeances": [r.to_dict() for r in rows]}


@router.get("/applications/{app_id}/schedule", summary="Échéancier d'un prêt")
async def get_schedule(
    app_id: str,
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    rows = await LoanInstallmentRepository(session).list_for_application(
        app_id, tenant_id=tenant_id
    )
    total = sum((r.montant_xaf for r in rows), Decimal("0"))
    paye = sum((r.montant_paye_xaf for r in rows), Decimal("0"))
    return {
        "echeances": [r.to_dict() for r in rows],
        "total_xaf": str(total),
        "paye_xaf": str(paye),
        "reste_xaf": str(total - paye),
    }


@router.post("/installments/{inst_id}/pay", summary="Encaisser une échéance")
async def pay_installment(
    inst_id: str,
    body: PayIn,
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    repo = LoanInstallmentRepository(session)
    inst = await repo.get(inst_id, tenant_id=tenant_id)
    if inst is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="installment_not_found")
    reste = inst.montant_xaf - inst.montant_paye_xaf
    montant = body.montant if body.montant is not None else reste
    if montant <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="montant_invalide"
        )
    nouveau_paye = min(inst.montant_xaf, inst.montant_paye_xaf + montant)
    solde = nouveau_paye >= inst.montant_xaf
    fields: dict[str, Any] = {
        "montant_paye_xaf": nouveau_paye,
        "statut": "paye" if solde else "partiel",
    }
    if solde:
        fields["paye_le"] = body.date_paiement or datetime.now(UTC).date()
    rec = await repo.update(inst_id, tenant_id=tenant_id, fields=fields)
    await session.commit()
    return rec.to_dict()


# --------------------------------------------------------------- registres KYC


@router.post(
    "/kyc-records",
    status_code=status.HTTP_201_CREATED,
    summary="Évaluer et enregistrer un dossier KYC",
)
async def create_kyc_record(
    profile: KycProfile,
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    res = evaluate_kyc(profile)
    rec = await KycRecordRepository(session).create(
        {
            "tenant_id": tenant_id,
            "nom": profile.nom,
            "type_client": profile.type_client,
            "niveau_risque": res.niveau_risque,
            "score_risque": res.score_risque,
            "vigilance": res.vigilance,
            "complet": res.complet,
            "peut_entrer_en_relation": res.peut_entrer_en_relation,
            "pep": profile.pep,
            "statut": "a_valider",
            "profil": profile.model_dump(mode="json"),
            "resultat": res.model_dump(mode="json"),
        }
    )
    await session.commit()
    return rec.to_dict()


@router.get("/kyc-records", summary="Lister les dossiers KYC")
async def list_kyc_records(
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    rows = await KycRecordRepository(session).list(tenant_id=tenant_id)
    rows.sort(key=lambda r: r.created_at, reverse=True)
    return {"kyc_records": [r.to_dict() for r in rows]}


@router.post("/kyc-records/{rec_id}/decision", summary="Décision conformité d'un dossier KYC")
async def decide_kyc_record(
    rec_id: str,
    body: DecisionIn,
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    if body.statut not in _STATUTS_KYC:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"statut_invalide (attendu : {sorted(_STATUTS_KYC)})",
        )
    rec = await KycRecordRepository(session).update(
        rec_id, tenant_id=tenant_id, fields={"statut": body.statut, "commentaire": body.commentaire}
    )
    if rec is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="kyc_record_not_found")
    await session.commit()
    return rec.to_dict()


@router.delete("/kyc-records/{rec_id}", summary="Supprimer un dossier KYC")
async def delete_kyc_record(
    rec_id: str,
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    ok = await KycRecordRepository(session).delete(rec_id, tenant_id=tenant_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="kyc_record_not_found")
    await session.commit()
    return {"status": "deleted"}


# ------------------------------------------------------------ pilotage portefeuille


@router.get("/portfolio", summary="Pilotage du portefeuille de crédit (agrégé)")
async def portfolio(
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    apps = await CreditApplicationRepository(session).list(tenant_id=tenant_id)
    kyc = await KycRecordRepository(session).list(tenant_id=tenant_id)
    installments = await LoanInstallmentRepository(session).list(tenant_id=tenant_id)
    return portfolio_stats(apps, kyc, installments).model_dump(mode="json")


@router.get("/cohortes", summary="Cohortes (millésimes) : performance par mois de décaissement")
async def get_cohortes(
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    apps = await CreditApplicationRepository(session).list(tenant_id=tenant_id)
    installments = await LoanInstallmentRepository(session).list(tenant_id=tenant_id)
    rows = cohortes(apps, installments, datetime.now(UTC).date())
    return {"cohortes": [c.model_dump(mode="json") for c in rows]}


# ------------------------------------------------------- import Excel (classeur)


@router.get("/import/template", summary="Modèle .xlsx d'import des dossiers de crédit")
def import_template() -> Response:
    return Response(
        content=build_template(_INTAKE),
        media_type=_XLSX,
        headers={"Content-Disposition": 'attachment; filename="modele_dossiers_credit.xlsx"'},
    )


@router.post(
    "/import/applications",
    summary="Importer un classeur de dossiers (chaque ligne est scorée ; dry_run pour simuler)",
)
async def import_applications(
    request: Request,
    dry_run: bool = False,
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    content = await request.body()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="empty_file")
    try:
        rows = parse_sheet(content, _INTAKE.label[:31])
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_xlsx") from exc

    scores: list[tuple[str, CreditRequest, CreditScore]] = []
    erreurs: list[dict[str, Any]] = []
    for i, raw in enumerate(rows, start=2):  # ligne 1 = en-têtes
        record, errs = validate_row(_INTAKE, raw)
        if errs or record is None:
            erreurs.append({"ligne": i, "motifs": errs})
            continue
        client = str(record.pop("client"))
        try:
            dossier = CreditRequest(**record)
        except ValidationError as exc:
            erreurs.append({"ligne": i, "motifs": [e["msg"] for e in exc.errors()][:3]})
            continue
        scores.append((client, dossier, score_credit(dossier)))

    apercu = [
        {"client": c, "score": r.score, "grade": r.grade, "decision": r.decision}
        for c, _d, r in scores[:20]
    ]
    if dry_run:
        return {
            "total": len(rows),
            "valides": len(scores),
            "rejetes": len(erreurs),
            "erreurs": erreurs,
            "apercu": apercu,
        }

    repo = CreditApplicationRepository(session)
    base = int(datetime.now(UTC).timestamp())
    for idx, (client, dossier, res) in enumerate(scores):
        await repo.create(_application_record(tenant_id, client, dossier, res, f"CR-{base}-{idx}"))
    await session.commit()
    return {
        "total": len(rows),
        "importes": len(scores),
        "rejetes": len(erreurs),
        "erreurs": erreurs,
        "apercu": apercu,
    }
