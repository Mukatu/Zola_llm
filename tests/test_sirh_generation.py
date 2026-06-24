"""Tests SIRH-2b — fusion de contrats (pur) + documents/génération (SQLite)."""

from __future__ import annotations

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from zolaos.agents.erp.rh_generation import compose_prompt, merge_template
from zolaos.api.main import create_app
from zolaos.core.settings import Settings
from zolaos.db.session import get_session
from zolaos.db.store_models import StoreBase


def test_merge_template_en_masse() -> None:
    template = "Contrat {{type}} de {{nom}} — {{salaire}} XAF"
    rows = [
        {"type": "CDI", "nom": "Awa", "salaire": "500000"},
        {"type": "CDD", "nom": "Paul", "salaire": "300000"},
    ]
    out = merge_template(template, rows)
    assert out[0] == "Contrat CDI de Awa — 500000 XAF"
    assert out[1] == "Contrat CDD de Paul — 300000 XAF"


def test_compose_prompt_fiche_poste() -> None:
    ctx = {
        "intitule": "Comptable",
        "mission": "Tenir la comptabilité",
        "activites": ["Saisie", "Rapprochement"],
        "kpis": ["Délai de clôture"],
        "competences": [{"intitule": "SYSCOHADA", "niveau_requis": 3}],
    }
    p = compose_prompt("fiche_poste", context=ctx)
    assert "fiche de poste" in p.lower()
    assert "Comptable" in p
    assert "SYSCOHADA" in p


def _settings() -> Settings:
    return Settings(
        POSTGRES_PASSWORD_APP="x", POSTGRES_PASSWORD_MIGRATIONS="x", JWT_SECRET="x" * 32
    )


async def _client(tmp_path):  # type: ignore[no-untyped-def]
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/gen.db")
    async with engine.begin() as conn:
        await conn.run_sync(StoreBase.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def _override():
        async with factory() as s:
            yield s

    app = create_app(settings=_settings())
    app.dependency_overrides[get_session] = _override
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_documents_and_mass_contracts(tmp_path) -> None:  # type: ignore[no-untyped-def]
    async with await _client(tmp_path) as ac:
        # document CRUD
        r = await ac.post(
            "/v1/erp/documents",
            json={"type": "fiche_poste", "titre": "Fiche comptable", "contenu": "..."},
        )
        assert r.status_code == 201, r.text
        r = await ac.get("/v1/erp/documents", params={"type": "fiche_poste"})
        assert len(r.json()["documents"]) == 1

        # employés → contrats en masse
        for mat, nom in [("E1", "Awa"), ("E2", "Paul")]:
            await ac.post(
                "/v1/erp/employees",
                json={
                    "matricule": mat,
                    "nom_complet": nom,
                    "date_embauche": "2026-01-01",
                    "poste": "Comptable",
                    "salaire_base_xaf": "400000",
                },
            )
        r = await ac.post(
            "/v1/erp/hr/contracts/generate",
            json={"matricules": ["E1", "E2"], "type_contrat": "CDD"},
        )
        contrats = r.json()["contrats"]
        assert len(contrats) == 2
        assert "Awa" in contrats[0]["contenu"]
        assert "CDD" in contrats[0]["contenu"]
