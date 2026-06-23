"""SIRH — endpoints Core HR & pilotage (registres + tableau de bord + échéancier).

Profil box. CRUD des registres (employés, contrats, absences) + indicateurs
**déterministes** (`rh_pilotage`) sur les données stockées. Multi-tenant.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import date
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from zolaos.agents.erp.rh_pilotage import (
    AbsenceHR,
    ContractHR,
    EmployeeHR,
    dashboard,
    echeancier,
    registre,
)
from zolaos.db.session import get_session
from zolaos.db.store_repo import AbsenceRepository, ContractRepository, EmployeeRepository

router = APIRouter(prefix="/v1/erp", tags=["sirh"])


# ----------------------------------------------------------------- schémas


class EmployeeIn(BaseModel):
    matricule: str
    nom_complet: str
    genre: str = "NC"
    date_naissance: date | None = None
    date_embauche: date
    poste: str = ""
    departement: str = ""
    manager_matricule: str | None = None
    categorie: str | None = None
    code_emploi: str | None = None
    salaire_base_xaf: Decimal = Decimal("0")
    quotite: Decimal = Decimal("1")
    statut: str = "actif"
    date_sortie: date | None = None
    motif_sortie: str | None = None
    country: str = "cg"


class EmployeePatch(BaseModel):
    poste: str | None = None
    departement: str | None = None
    manager_matricule: str | None = None
    code_emploi: str | None = None
    salaire_base_xaf: Decimal | None = None
    quotite: Decimal | None = None
    statut: str | None = None
    date_sortie: date | None = None
    motif_sortie: str | None = None


class ContractIn(BaseModel):
    employee_matricule: str
    type: str = "CDI"
    date_debut: date
    date_fin: date | None = None
    fin_periode_essai: date | None = None
    statut: str = "actif"


class AbsenceIn(BaseModel):
    employee_matricule: str
    type: str = "conge_paye"
    date_debut: date
    date_fin: date
    jours: Decimal = Decimal("0")
    statut: str = "valide"


# ----------------------------------------------------------------- helpers


def _to_emp_hr(r: Any) -> EmployeeHR:
    return EmployeeHR(
        matricule=r.matricule,
        nom_complet=r.nom_complet,
        genre=r.genre,
        date_naissance=r.date_naissance,
        date_embauche=r.date_embauche,
        poste=r.poste,
        departement=r.departement,
        manager_matricule=r.manager_matricule,
        categorie=r.categorie,
        salaire_base_xaf=r.salaire_base_xaf,
        quotite=r.quotite,
        statut=r.statut,
        date_sortie=r.date_sortie,
    )


def _to_contract_hr(r: Any) -> ContractHR:
    return ContractHR(
        employee_matricule=r.employee_matricule,
        type=r.type,
        date_debut=r.date_debut,
        date_fin=r.date_fin,
        fin_periode_essai=r.fin_periode_essai,
    )


def _to_absence_hr(r: Any) -> AbsenceHR:
    return AbsenceHR(
        employee_matricule=r.employee_matricule,
        type=r.type,
        date_debut=r.date_debut,
        date_fin=r.date_fin,
        jours=r.jours,
    )


# ----------------------------------------------------------------- employés


@router.post("/employees", status_code=status.HTTP_201_CREATED, summary="Créer un employé")
async def create_employee(
    body: EmployeeIn,
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    rec = await EmployeeRepository(session).create({**body.model_dump(), "tenant_id": tenant_id})
    await session.commit()
    return rec.to_dict()


@router.get("/employees", summary="Lister les employés")
async def list_employees(
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    rows = await EmployeeRepository(session).list(tenant_id=tenant_id)
    return {"employees": [r.to_dict() for r in rows]}


@router.patch("/employees/{emp_id}", summary="Mettre à jour un employé")
async def patch_employee(
    emp_id: str,
    body: EmployeePatch,
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    rec = await EmployeeRepository(session).update(
        emp_id, tenant_id=tenant_id, fields=body.model_dump(exclude_none=True)
    )
    if rec is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="employee_not_found")
    await session.commit()
    return rec.to_dict()


@router.delete("/employees/{emp_id}", summary="Supprimer un employé")
async def delete_employee(
    emp_id: str,
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    ok = await EmployeeRepository(session).delete(emp_id, tenant_id=tenant_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="employee_not_found")
    await session.commit()
    return {"deleted": emp_id}


# ----------------------------------------------------------------- contrats / absences


@router.post("/contracts", status_code=status.HTTP_201_CREATED, summary="Créer un contrat")
async def create_contract(
    body: ContractIn,
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    rec = await ContractRepository(session).create({**body.model_dump(), "tenant_id": tenant_id})
    await session.commit()
    return rec.to_dict()


@router.get("/contracts", summary="Lister les contrats")
async def list_contracts(
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    rows = await ContractRepository(session).list(tenant_id=tenant_id)
    return {"contracts": [r.to_dict() for r in rows]}


@router.post("/absences", status_code=status.HTTP_201_CREATED, summary="Créer une absence")
async def create_absence(
    body: AbsenceIn,
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    rec = await AbsenceRepository(session).create({**body.model_dump(), "tenant_id": tenant_id})
    await session.commit()
    return rec.to_dict()


@router.get("/absences", summary="Lister les absences")
async def list_absences(
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    rows = await AbsenceRepository(session).list(tenant_id=tenant_id)
    return {"absences": [r.to_dict() for r in rows]}


# ----------------------------------------------------------------- pilotage


@router.get("/hr/dashboard", summary="Tableau de bord RH (indicateurs déterministes)")
async def hr_dashboard(
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    emps = [_to_emp_hr(r) for r in await EmployeeRepository(session).list(tenant_id=tenant_id)]
    cons = [_to_contract_hr(r) for r in await ContractRepository(session).list(tenant_id=tenant_id)]
    abs_ = [_to_absence_hr(r) for r in await AbsenceRepository(session).list(tenant_id=tenant_id)]
    return asdict(dashboard(emps, cons, abs_))


@router.get("/hr/echeancier", summary="Échéancier RH (essai/CDD/anniversaires)")
async def hr_echeancier(
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    emps = [_to_emp_hr(r) for r in await EmployeeRepository(session).list(tenant_id=tenant_id)]
    cons = [_to_contract_hr(r) for r in await ContractRepository(session).list(tenant_id=tenant_id)]
    return {"echeances": [asdict(e) for e in echeancier(emps, cons)]}


@router.get("/hr/registre", summary="Registre unique du personnel (export légal)")
async def hr_registre(
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    emps = [_to_emp_hr(r) for r in await EmployeeRepository(session).list(tenant_id=tenant_id)]
    return {"registre": registre(emps)}
