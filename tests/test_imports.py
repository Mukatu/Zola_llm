"""Tests du framework Import/Export Excel (pur + round-trip endpoint SQLite)."""

from __future__ import annotations

from io import BytesIO
from typing import Any

import openpyxl
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from zolaos.api.main import create_app
from zolaos.core.settings import Settings
from zolaos.db.session import get_session
from zolaos.db.store_models import StoreBase
from zolaos.imports.framework import build_template, parse_sheet, validate_row
from zolaos.imports.registry import REGISTRY

_EMP_COLS = [
    "matricule",
    "nom_complet",
    "genre",
    "date_naissance",
    "date_embauche",
    "poste",
    "departement",
    "manager_matricule",
    "categorie",
    "code_emploi",
    "salaire_base_xaf",
    "quotite",
    "statut",
]


def _emp_xlsx(rows: list[dict[str, Any]]) -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Employés"
    ws.append(_EMP_COLS)
    for r in rows:
        ws.append([r.get(c, "") for c in _EMP_COLS])
    bio = BytesIO()
    wb.save(bio)
    return bio.getvalue()


def test_validate_row() -> None:
    spec = REGISTRY["employees"]
    ok, errs = validate_row(
        spec, {"matricule": "E1", "nom_complet": "Awa", "date_embauche": "2024-01-01"}
    )
    assert errs == []
    assert ok is not None and ok["matricule"] == "E1"

    _, errs2 = validate_row(spec, {"nom_complet": "X"})  # matricule + date_embauche manquants
    assert any("matricule" in e for e in errs2)

    _, errs3 = validate_row(
        spec, {"matricule": "E1", "nom_complet": "X", "date_embauche": "2024-01-01", "genre": "Z"}
    )
    assert any("genre" in e for e in errs3)


def test_template_and_parse_roundtrip() -> None:
    data = build_template(REGISTRY["employees"])
    wb = openpyxl.load_workbook(BytesIO(data))
    assert "Dictionnaire" in wb.sheetnames
    parsed = parse_sheet(
        _emp_xlsx([{"matricule": "E1", "nom_complet": "Awa", "date_embauche": "2024-01-01"}])
    )
    assert parsed[0]["matricule"] == "E1"


def _settings() -> Settings:
    return Settings(
        POSTGRES_PASSWORD_APP="x", POSTGRES_PASSWORD_MIGRATIONS="x", JWT_SECRET="x" * 32
    )


async def _client(tmp_path):  # type: ignore[no-untyped-def]
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/imp.db")
    async with engine.begin() as conn:
        await conn.run_sync(StoreBase.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def _override():
        async with factory() as s:
            yield s

    app = create_app(settings=_settings())
    app.dependency_overrides[get_session] = _override
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_import_dry_run_then_commit_idempotent(tmp_path) -> None:  # type: ignore[no-untyped-def]
    async with await _client(tmp_path) as ac:
        # modèle téléchargeable
        r = await ac.get("/v1/erp/import/template/employees")
        assert r.status_code == 200
        assert "spreadsheetml" in r.headers["content-type"]

        xlsx = _emp_xlsx(
            [
                {
                    "matricule": "E1",
                    "nom_complet": "Awa",
                    "date_embauche": "2024-01-01",
                    "salaire_base_xaf": "500000",
                },
                {"nom_complet": "SansMatricule"},  # rejetée
            ]
        )

        # dry-run : 1 valide, 1 erreur, rien d'importé
        r = await ac.post("/v1/erp/import/employees?dry_run=true", content=xlsx)
        body = r.json()
        assert body["valides"] == 1
        assert len(body["erreurs"]) == 1
        assert (await ac.get("/v1/erp/employees")).json()["employees"] == []

        # import réel
        r = await ac.post("/v1/erp/import/employees", content=xlsx)
        assert r.json()["importes"] == 1
        assert len((await ac.get("/v1/erp/employees")).json()["employees"]) == 1

        # ré-import → upsert (mise à jour, pas de doublon)
        r = await ac.post("/v1/erp/import/employees", content=xlsx)
        assert r.json()["mis_a_jour"] == 1
        assert len((await ac.get("/v1/erp/employees")).json()["employees"]) == 1
