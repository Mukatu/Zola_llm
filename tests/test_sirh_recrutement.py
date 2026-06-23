"""Tests SIRH-2a Recrutement — indicateurs (pur) + pipeline/CRUD (SQLite)."""

from __future__ import annotations

from datetime import date

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from zolaos.agents.erp.recrutement import (
    ApplicationRef,
    CandidateRef,
    VacancyRef,
    recruitment_dashboard,
)
from zolaos.api.main import create_app
from zolaos.core.settings import Settings
from zolaos.db.session import get_session
from zolaos.db.store_models import StoreBase

TODAY = date(2026, 6, 23)


def test_recruitment_dashboard() -> None:
    vac = [VacancyRef(code_vacance="V1", statut="ouverte", date_ouverture=date(2026, 4, 1))]
    cand = [
        CandidateRef(id="C1", source="cooptation"),
        CandidateRef(id="C2", source="jobboard"),
        CandidateRef(id="C3", source="jobboard"),
    ]
    apps = [
        ApplicationRef(
            candidate_id="C1",
            code_vacance="V1",
            etape="embauché",
            date_candidature=date(2026, 4, 5),
            date_etape=date(2026, 5, 1),
        ),
        ApplicationRef(
            candidate_id="C2",
            code_vacance="V1",
            etape="entretien",
            date_candidature=date(2026, 4, 10),
        ),
        ApplicationRef(
            candidate_id="C3", code_vacance="V1", etape="rejeté", date_candidature=date(2026, 4, 11)
        ),
    ]
    d = recruitment_dashboard(vac, cand, apps, today=TODAY)
    assert d["total_candidatures"] == 3
    assert d["embauches"] == 1
    assert d["par_etape"]["entretien"] == 1  # type: ignore[index]
    assert d["rejetes"] == 1
    assert d["time_to_hire_jours"] == "30.0"  # 1 mai - 1 avril
    assert d["par_source"]["cooptation"]["embauches"] == 1  # type: ignore[index]
    # vacance ouverte depuis > 30 j → en souffrance
    assert len(d["vacances_en_souffrance"]) == 1  # type: ignore[arg-type]


def _settings() -> Settings:
    return Settings(
        POSTGRES_PASSWORD_APP="x", POSTGRES_PASSWORD_MIGRATIONS="x", JWT_SECRET="x" * 32
    )


async def _client(tmp_path):  # type: ignore[no-untyped-def]
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/rec.db")
    async with engine.begin() as conn:
        await conn.run_sync(StoreBase.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def _override():
        async with factory() as s:
            yield s

    app = create_app(settings=_settings())
    app.dependency_overrides[get_session] = _override
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_pipeline_move_and_dashboard(tmp_path) -> None:  # type: ignore[no-untyped-def]
    async with await _client(tmp_path) as ac:
        await ac.post(
            "/v1/erp/recruitment/vacancies",
            json={"code_vacance": "V1", "intitule": "Comptable", "date_ouverture": "2026-04-01"},
        )
        c = (
            await ac.post(
                "/v1/erp/recruitment/candidates", json={"nom": "Awa", "source": "cooptation"}
            )
        ).json()
        a = (
            await ac.post(
                "/v1/erp/recruitment/applications",
                json={
                    "candidate_id": c["id"],
                    "code_vacance": "V1",
                    "date_candidature": "2026-04-05",
                },
            )
        ).json()
        assert a["etape"] == "reçue"

        # déplacer dans le pipeline → embauché
        r = await ac.patch(
            f"/v1/erp/recruitment/applications/{a['id']}", json={"etape": "embauché"}
        )
        assert r.status_code == 200
        assert r.json()["etape"] == "embauché"
        assert r.json()["date_etape"] is not None

        d = (await ac.get("/v1/erp/recruitment/dashboard")).json()
        assert d["embauches"] == 1
