"""Enrichissements du cockpit BI (P3) : masse salariale réelle (bulletins),
exécution budgétaire des projets, et échéances de mandats sociaux.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from decimal import Decimal

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from zolaos.api.main import create_app
from zolaos.core.settings import Settings
from zolaos.db.session import get_session
from zolaos.db.store_models import PayslipRecord, StoreBase


def _settings() -> Settings:
    return Settings(
        POSTGRES_PASSWORD_APP="x", POSTGRES_PASSWORD_MIGRATIONS="x", JWT_SECRET="x" * 32
    )


@asynccontextmanager
async def _client(tmp_path):  # type: ignore[no-untyped-def]
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/bi_enrich.db")
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
        yield client, factory
    finally:
        await client.aclose()
        await engine.dispose()


async def test_cockpit_enrichi(tmp_path) -> None:  # type: ignore[no-untyped-def]
    async with _client(tmp_path) as (ac, factory):
        # Bulletins de paie historisés (2 périodes) : la masse réelle = dernière période.
        async with factory() as s:
            s.add_all(
                [
                    PayslipRecord(
                        tenant_id="local", employee_matricule="M1", periode="2026-05",
                        brut_xaf=Decimal("100000"), cout_employeur_xaf=Decimal("130000"),
                    ),
                    PayslipRecord(
                        tenant_id="local", employee_matricule="M1", periode="2026-06",
                        brut_xaf=Decimal("120000"), cout_employeur_xaf=Decimal("156000"),
                    ),
                    PayslipRecord(
                        tenant_id="local", employee_matricule="M2", periode="2026-06",
                        brut_xaf=Decimal("80000"), cout_employeur_xaf=Decimal("104000"),
                    ),
                ]
            )
            await s.commit()

        # Projet bailleur + ligne budgétaire réalisée (exécution 25 %).
        proj = (
            await ac.post(
                "/v1/erp/projects",
                json={"intitule": "Eau", "bailleur": "UE", "budget_total": "4000"},
            )
        ).json()
        await ac.post(
            "/v1/erp/budget-lines",
            json={"project_id": proj["id"], "rubrique": "Travaux", "montant_realise": "1000"},
        )

        # Mandat social arrivant à échéance (nomination + durée ≈ +40 j).
        await ac.post(
            "/v1/erp/mandates",
            json={
                "titulaire": "A. Nkéé",
                "fonction": "gerant",
                "date_nomination": "2023-09-01",
                "duree_annees": 3,
            },
        )

        ck = (await ac.get("/v1/bi/cockpit")).json()
        kpis = {k["code"]: k for k in ck["kpis"]}

        # Masse salariale = bulletins de la dernière période (2026-06) : 120000 + 80000.
        assert Decimal(kpis["masse_salariale"]["valeur"]) == Decimal("200000")
        assert Decimal(kpis["cout_employeur"]["valeur"]) == Decimal("260000")
        assert kpis["cout_employeur"]["domaine"] == "rh"

        # Exécution budgétaire projets : 1000 / 4000 = 25 %.
        assert Decimal(kpis["realise_projets"]["valeur"]) == Decimal("1000")
        assert Decimal(kpis["execution_projets"]["valeur"]) == Decimal("25")
        assert kpis["execution_projets"]["domaine"] == "projets"

        # Échéance de mandat présente dans le cockpit.
        codes = [e["code"] for e in ck["echeances"]]
        assert any(c.startswith("mandat-") for c in codes)


async def test_cockpit_sans_donnees_optionnelles(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Sans bulletins ni projets, les KPIs optionnels sont absents (pas de bruit)."""
    async with _client(tmp_path) as (ac, _factory):
        ck = (await ac.get("/v1/bi/cockpit")).json()
        codes = {k["code"] for k in ck["kpis"]}
        assert "masse_salariale" in codes  # toujours présent (retombe sur salaires de base)
        assert "cout_employeur" not in codes
        assert "execution_projets" not in codes
        # Le mandat de test n'existe pas : au moins les échéances fiscales sont là.
        assert len(ck["echeances"]) >= 1
