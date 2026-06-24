"""Import/Export Excel — alimentation des tables `store_*` (sans ERP).

Profil box. Génère des modèles .xlsx, valide un upload (dry-run, rapport ligne
par ligne) et importe (upsert par clé naturelle). Upload = corps brut (octets).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from zolaos.db.session import get_session
from zolaos.imports.framework import (
    EntitySpec,
    build_export,
    build_template,
    parse_sheet,
    validate_row,
)
from zolaos.imports.registry import REGISTRY

router = APIRouter(prefix="/v1/erp", tags=["import"])

_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _spec(entity: str) -> EntitySpec:
    spec = REGISTRY.get(entity)
    if spec is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="entity_not_found")
    return spec


def _attachment(entity: str, suffixe: str) -> dict[str, str]:
    return {"Content-Disposition": f'attachment; filename="{suffixe}_{entity}.xlsx"'}


@router.get("/import/entities", summary="Catalogue des entités importables")
def import_entities() -> dict[str, Any]:
    return {
        "entities": [
            {
                "entity": s.entity,
                "label": s.label,
                "natural_key": list(s.natural_key),
                "columns": [
                    {
                        "name": c.name,
                        "kind": c.kind,
                        "required": c.required,
                        "enum": list(c.enum) if c.enum else None,
                    }
                    for c in s.columns
                ],
            }
            for s in REGISTRY.values()
        ]
    }


@router.get("/import/template/{entity}", summary="Télécharger le modèle .xlsx")
def import_template(entity: str) -> Response:
    spec = _spec(entity)
    return Response(
        content=build_template(spec), media_type=_XLSX, headers=_attachment(entity, "modele")
    )


@router.post("/import/{entity}", summary="Importer (dry_run=true pour simuler)")
async def import_entity(
    entity: str,
    request: Request,
    dry_run: bool = False,
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    spec = _spec(entity)
    content = await request.body()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="empty_file")
    try:
        rows = parse_sheet(content, spec.label[:31])
    except Exception as exc:  # fichier illisible → 400 propre
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_xlsx") from exc

    valides: list[dict[str, Any]] = []
    erreurs: list[dict[str, Any]] = []
    for i, raw in enumerate(rows, start=2):  # ligne 1 = en-têtes
        record, errs = validate_row(spec, raw)
        if errs:
            erreurs.append({"ligne": i, "motifs": errs})
        elif record is not None:
            valides.append(record)

    if dry_run:
        return {"total": len(rows), "valides": len(valides), "erreurs": erreurs}

    importes = 0
    mis_a_jour = 0
    for record in valides:
        existing = None
        if spec.natural_key:
            stmt = select(spec.model).where(spec.model.tenant_id == tenant_id)
            for key in spec.natural_key:
                stmt = stmt.where(getattr(spec.model, key) == record[key])
            existing = (await session.scalars(stmt)).first()
        if existing is not None:
            for k, v in record.items():
                setattr(existing, k, v)
            mis_a_jour += 1
        else:
            session.add(spec.model(tenant_id=tenant_id, **record))
            importes += 1
    await session.commit()
    return {
        "total": len(rows),
        "importes": importes,
        "mis_a_jour": mis_a_jour,
        "rejetes": len(erreurs),
        "erreurs": erreurs,
    }


@router.get("/export/{entity}", summary="Exporter les données existantes (.xlsx)")
async def export_entity(
    entity: str,
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> Response:
    spec = _spec(entity)
    stmt = select(spec.model).where(spec.model.tenant_id == tenant_id)
    rows = [r.to_dict() for r in await session.scalars(stmt)]
    return Response(
        content=build_export(spec, rows), media_type=_XLSX, headers=_attachment(entity, "export")
    )
