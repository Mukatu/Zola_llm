"""GRC-1 — registre de conformité (obligations/contrôles/constats) + plan de contrôle."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import date, timedelta
from decimal import Decimal

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from zolaos.agents.grc.conformite import (
    ControlLite,
    FindingLite,
    ObligationLite,
    synthese_conformite,
)
from zolaos.api.main import create_app
from zolaos.core.settings import Settings
from zolaos.db.session import get_session
from zolaos.db.store_models import StoreBase

TODAY = date(2026, 7, 24)


# ---------------------------------------------------------------- moteur (pur)


def test_synthese_couverture_retard_alertes() -> None:
    obs = [
        ObligationLite(id="o1", reference="TVA", intitule="TVA mensuelle", domaine="fiscal"),
        ObligationLite(id="o2", reference="CNSS", intitule="CNSS", domaine="social"),
    ]
    # o1 a un contrôle en retard ; o2 n'a aucun contrôle.
    ctrls = [
        ControlLite(
            id="c1", obligation_id="o1", prochaine_execution=date(2026, 7, 1), statut="planifie"
        )
    ]
    finds = [
        FindingLite(id="f1", gravite="critique", statut="ouvert"),
        FindingLite(id="f2", gravite="mineur", statut="resolu"),
    ]
    s = synthese_conformite(obs, ctrls, finds, today=TODAY)

    assert s.nb_obligations == 2
    assert s.nb_obligations_sans_controle == 1  # o2
    assert s.taux_couverture == Decimal("50.0")
    assert s.nb_controls_en_retard == 1  # c1 dépassé, non réalisé
    assert s.nb_findings_ouverts == 1
    assert s.findings_ouverts_par_gravite["critique"] == 1
    assert s.taux_conformite == Decimal("50.0")  # 1 résolu / 2
    assert any("sans contrôle" in a for a in s.alertes)
    assert any("retard" in a for a in s.alertes)
    assert any("critique" in a for a in s.alertes)


def test_synthese_vide_conforme() -> None:
    s = synthese_conformite([], [], [], today=TODAY)
    assert s.taux_conformite == Decimal("100")  # aucun constat → conforme
    assert s.taux_couverture == Decimal("0")
    assert s.alertes == []


# ----------------------------------------------------------------- endpoints


def _settings() -> Settings:
    return Settings(
        POSTGRES_PASSWORD_APP="x", POSTGRES_PASSWORD_MIGRATIONS="x", JWT_SECRET="x" * 32
    )


@asynccontextmanager
async def _client(tmp_path):  # type: ignore[no-untyped-def]
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/grc.db")
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


async def test_grc_crud_et_plan(tmp_path) -> None:  # type: ignore[no-untyped-def]
    async with _client(tmp_path) as ac:
        obl = (
            await ac.post(
                "/v1/grc/obligations",
                json={"reference": "TVA", "intitule": "Déclaration TVA", "domaine": "fiscal"},
            )
        ).json()
        assert obl["statut"] == "active"
        oid = obl["id"]

        # Une obligation sans contrôle (pour la couverture).
        await ac.post("/v1/grc/obligations", json={"intitule": "CNSS", "domaine": "social"})

        # Contrôle en retard rattaché à l'obligation TVA.
        passe = (date.today() - timedelta(days=10)).isoformat()
        await ac.post(
            "/v1/grc/controls",
            json={"obligation_id": oid, "intitule": "Revue TVA", "prochaine_execution": passe},
        )

        # Constat critique ouvert.
        await ac.post(
            "/v1/grc/findings",
            json={
                "obligation_id": oid,
                "intitule": "Écart de TVA collectée",
                "gravite": "critique",
                "date_constat": date.today().isoformat(),
            },
        )

        # Filtre contrôles par obligation.
        ctrls = (await ac.get(f"/v1/grc/controls?obligation_id={oid}")).json()["controls"]
        assert len(ctrls) == 1

        plan = (await ac.get("/v1/grc/plan-controle")).json()
        assert plan["nb_obligations"] == 2
        assert plan["nb_obligations_sans_controle"] == 1
        assert plan["nb_controls_en_retard"] == 1
        assert plan["findings_ouverts_par_gravite"]["critique"] == 1
        assert len(plan["alertes"]) >= 3


async def test_grc_patch_delete_404(tmp_path) -> None:  # type: ignore[no-untyped-def]
    async with _client(tmp_path) as ac:
        obl = (await ac.post("/v1/grc/obligations", json={"intitule": "X"})).json()
        patched = (
            await ac.patch(f"/v1/grc/obligations/{obl['id']}", json={"statut": "suspendue"})
        ).json()
        assert patched["statut"] == "suspendue"
        assert (await ac.delete(f"/v1/grc/obligations/{obl['id']}")).status_code == 200
        assert (
            await ac.patch(f"/v1/grc/obligations/{obl['id']}", json={"statut": "active"})
        ).status_code == 404
        assert (await ac.delete("/v1/grc/controls/inconnu")).status_code == 404
        assert (await ac.delete("/v1/grc/findings/inconnu")).status_code == 404
