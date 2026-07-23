"""Tests Projets ONG — CRUD projets/lignes budgétaires + suivi d'exécution + ventilation."""

from __future__ import annotations

from contextlib import asynccontextmanager

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from zolaos.api.main import create_app
from zolaos.core.settings import Settings
from zolaos.db.session import get_session
from zolaos.db.store_models import StoreBase


def _settings() -> Settings:
    return Settings(
        POSTGRES_PASSWORD_APP="x", POSTGRES_PASSWORD_MIGRATIONS="x", JWT_SECRET="x" * 32
    )


@asynccontextmanager
async def _client(tmp_path):  # type: ignore[no-untyped-def]
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/projets.db")
    async with engine.begin() as conn:
        await conn.run_sync(StoreBase.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def _override():
        async with factory() as s:
            yield s

    app = create_app(settings=_settings())
    app.dependency_overrides[get_session] = _override
    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    try:
        yield client
    finally:
        await client.aclose()
        await engine.dispose()


async def test_project_crud(tmp_path) -> None:  # type: ignore[no-untyped-def]
    async with _client(tmp_path) as ac:
        created = (
            await ac.post(
                "/v1/erp/projects",
                json={
                    "intitule": "Accès à l'eau potable",
                    "bailleur": "Union Européenne",
                    "budget_total": "50000000",
                },
            )
        ).json()
        assert created["statut"] == "en_cours"
        assert created["devise"] == "XAF"
        project_id = created["id"]

        listed = (await ac.get("/v1/erp/projects")).json()["projects"]
        assert any(p["id"] == project_id for p in listed)

        patched = (
            await ac.patch(f"/v1/erp/projects/{project_id}", json={"statut": "suspendu"})
        ).json()
        assert patched["statut"] == "suspendu"

        deleted = await ac.delete(f"/v1/erp/projects/{project_id}")
        assert deleted.status_code == 200

        after = await ac.patch(f"/v1/erp/projects/{project_id}", json={"statut": "clos"})
        assert after.status_code == 404


async def test_budget_line_crud_with_project_filter(tmp_path) -> None:  # type: ignore[no-untyped-def]
    async with _client(tmp_path) as ac:
        p1 = (
            await ac.post(
                "/v1/erp/projects", json={"intitule": "Projet A", "bailleur": "Bailleur X"}
            )
        ).json()
        p2 = (
            await ac.post(
                "/v1/erp/projects", json={"intitule": "Projet B", "bailleur": "Bailleur X"}
            )
        ).json()

        l1 = (
            await ac.post(
                "/v1/erp/budget-lines",
                json={
                    "project_id": p1["id"],
                    "rubrique": "Salaires",
                    "montant_prevu": "1000",
                },
            )
        ).json()
        await ac.post(
            "/v1/erp/budget-lines",
            json={
                "project_id": p2["id"],
                "rubrique": "Équipement",
                "montant_prevu": "2000",
            },
        )

        only_p1 = (await ac.get(f"/v1/erp/budget-lines?project_id={p1['id']}")).json()[
            "budget_lines"
        ]
        assert len(only_p1) == 1
        assert only_p1[0]["rubrique"] == "Salaires"

        patched = (
            await ac.patch(f"/v1/erp/budget-lines/{l1['id']}", json={"montant_realise": "500"})
        ).json()
        assert patched["montant_realise"] == "500"

        deleted = await ac.delete(f"/v1/erp/budget-lines/{l1['id']}")
        assert deleted.status_code == 200
        remaining = await ac.delete(f"/v1/erp/budget-lines/{l1['id']}")
        assert remaining.status_code == 404


async def test_project_suivi(tmp_path) -> None:  # type: ignore[no-untyped-def]
    async with _client(tmp_path) as ac:
        project = (
            await ac.post(
                "/v1/erp/projects",
                json={
                    "intitule": "Renforcement sanitaire",
                    "bailleur": "PNUD",
                    "budget_total": "10000",
                },
            )
        ).json()
        pid = project["id"]

        # Rubrique en dépassement : réalisé > prévu.
        await ac.post(
            "/v1/erp/budget-lines",
            json={
                "project_id": pid,
                "rubrique": "Salaires",
                "montant_prevu": "1000",
                "montant_engage": "1000",
                "montant_realise": "1200",
                "eligible": True,
            },
        )
        # Rubrique sous contrôle.
        await ac.post(
            "/v1/erp/budget-lines",
            json={
                "project_id": pid,
                "rubrique": "Équipement",
                "montant_prevu": "2000",
                "montant_engage": "1500",
                "montant_realise": "1000",
                "eligible": False,
            },
        )

        suivi = (await ac.get(f"/v1/erp/projects/{pid}/suivi")).json()
        par_rubrique = {r["rubrique"]: r for r in suivi["par_rubrique"]}

        salaires = par_rubrique["Salaires"]
        assert salaires["prevu"] == "1000.00"
        assert salaires["realise"] == "1200.00"
        assert salaires["depassement"] is True
        assert salaires["taux_execution"] == 1.2
        assert salaires["taux_engagement"] == 1.0

        equipement = par_rubrique["Équipement"]
        assert equipement["depassement"] is False
        assert equipement["taux_execution"] == 0.5

        totaux = suivi["totaux"]
        assert totaux["budget_total"] == "10000.00"
        assert totaux["total_prevu"] == "3000.00"
        assert totaux["total_engage"] == "2500.00"
        assert totaux["total_realise"] == "2200.00"
        assert totaux["taux_global"] == round(2200 / 3000, 4)
        assert totaux["reste_a_realiser"] == "800.00"
        assert totaux["realise_eligible"] == "1200.00"
        assert totaux["realise_total"] == "2200.00"

        missing = await ac.get("/v1/erp/projects/inconnu/suivi")
        assert missing.status_code == 404


async def test_projects_ventilation(tmp_path) -> None:  # type: ignore[no-untyped-def]
    async with _client(tmp_path) as ac:
        p1 = (
            await ac.post(
                "/v1/erp/projects",
                json={
                    "intitule": "Projet Nord",
                    "bailleur": "Banque Mondiale",
                    "budget_total": "5000",
                },
            )
        ).json()
        p2 = (
            await ac.post(
                "/v1/erp/projects",
                json={
                    "intitule": "Projet Sud",
                    "bailleur": "Banque Mondiale",
                    "budget_total": "3000",
                },
            )
        ).json()
        await ac.post(
            "/v1/erp/projects",
            json={
                "intitule": "Autre bailleur",
                "bailleur": "UNICEF",
                "budget_total": "1000",
            },
        )

        await ac.post(
            "/v1/erp/budget-lines",
            json={"project_id": p1["id"], "rubrique": "Salaires", "montant_realise": "1000"},
        )
        await ac.post(
            "/v1/erp/budget-lines",
            json={"project_id": p2["id"], "rubrique": "Fonctionnement", "montant_realise": "500"},
        )

        ventilation = (await ac.get("/v1/erp/projects/ventilation")).json()

        bm = ventilation["Banque Mondiale"]
        assert bm["budget_total"] == "8000.00"
        assert bm["realise"] == "1500.00"
        assert bm["taux"] == round(1500 / 8000, 4)

        unicef = ventilation["UNICEF"]
        assert unicef["budget_total"] == "1000.00"
        assert unicef["realise"] == "0"
        assert unicef["taux"] == 0.0
