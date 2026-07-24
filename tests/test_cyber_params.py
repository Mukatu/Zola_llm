"""CYBER-3 — base de durcissement + seuils d'anomalies gouvernés (override tenant).

Le moteur lit les paramètres effectifs (graine surchargée par le tenant) ;
éditer remet ``validated`` à false (re-validation experte requise).
"""

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
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/cyberparams.db")
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


async def test_params_defaut(tmp_path) -> None:  # type: ignore[no-untyped-def]
    async with _client(tmp_path) as ac:
        view = (await ac.get("/v1/cyber/params")).json()
        assert view["source_donnees"] == "defaut"
        assert view["validated"] is True  # la graine vendeur est réputée validée
        assert view["seuils"]["seuil_echecs"] == 5
        assert any(c["cle"] == "mfa_admin" for c in view["controles"])


async def test_gouvernance_seuils_affecte_le_moteur(tmp_path) -> None:  # type: ignore[no-untyped-def]
    async with _client(tmp_path) as ac:
        # 4 échecs : sous le seuil par défaut (5) → aucune alerte de force brute.
        logs = [
            {
                "horodatage": "2026-07-24T10:0%d:00" % m,
                "type": "auth_failure",
                "utilisateur": "a",
                "source_ip": "1.1.1.1",
            }
            for m in range(4)
        ]
        r1 = (await ac.post("/v1/cyber/anomalies", json={"events": logs})).json()
        assert not any(a["code"].startswith("force_brute") for a in r1["anomalies"])

        # Durcir le seuil à 3 (override tenant).
        edited = (await ac.put("/v1/cyber/params", json={"seuils": {"seuil_echecs": 3}})).json()
        assert edited["source_donnees"] == "tenant"
        assert edited["validated"] is False  # re-validation requise
        assert edited["seuils"]["seuil_echecs"] == 3

        # Le moteur applique le seuil gouverné → alerte désormais.
        r2 = (await ac.post("/v1/cyber/anomalies", json={"events": logs})).json()
        assert any(a["code"].startswith("force_brute") for a in r2["anomalies"])


async def test_gouvernance_controle_desactive(tmp_path) -> None:  # type: ignore[no-untyped-def]
    async with _client(tmp_path) as ac:
        # Désactiver le contrôle MFA → il disparaît de l'audit.
        await ac.put(
            "/v1/cyber/params",
            json={"controles": {"mfa_admin": {"active": False}}},
        )
        res = (await ac.post("/v1/cyber/audit", json={"mfa_admin": False})).json()
        assert not any(f["cle"] == "mfa_admin" for f in res["findings"])


async def test_cycle_validation(tmp_path) -> None:  # type: ignore[no-untyped-def]
    async with _client(tmp_path) as ac:
        # Valider sans override existant → 404.
        r = await ac.post("/v1/cyber/params/validate", json={"validated": True})
        assert r.status_code == 404

        await ac.put("/v1/cyber/params", json={"seuils": {"fenetre_minutes": 30}})
        validated = (
            await ac.post(
                "/v1/cyber/params/validate", json={"validated": True, "validated_by": "RSSI"}
            )
        ).json()
        assert validated["validated"] is True
        assert validated["validated_by"] == "RSSI"

        # Ré-éditer → le verrou retombe.
        again = (await ac.put("/v1/cyber/params", json={"seuils": {"fenetre_minutes": 20}})).json()
        assert again["validated"] is False
