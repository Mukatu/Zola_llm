"""Parcours end-to-end — Cyber (défense) & GRC (conformité).

Cyber : audit de durcissement → détection d'anomalies → workflow de traitement.
GRC : obligation → contrôle en retard → constat critique → le plan de contrôle
agrège tout (couverture, retards, alertes). Déterministe, sans LLM.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import date, timedelta

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
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/parcours_cg.db")
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


async def test_parcours_cyber_defense(tmp_path) -> None:  # type: ignore[no-untyped-def]
    async with _client(tmp_path) as ac:
        # 1. Audit de durcissement : MFA absent → non-conformité critique persistée.
        audit = (
            await ac.post(
                "/v1/cyber/audits",
                json={"cible": "VPS prod", "config": {"mfa_admin": False}},
            )
        ).json()
        assert audit["niveau"] == "critical"
        assert audit["nb_non_conforme"] >= 1

        # 2. Détection d'anomalies : rafale d'échecs → alerte + dossier à examiner.
        logs = [
            {
                "horodatage": "2026-07-24T10:0%d:00" % m,
                "type": "auth_failure",
                "utilisateur": "root",
                "source_ip": "10.0.0.9",
            }
            for m in range(6)
        ]
        det = (await ac.post("/v1/cyber/detections", json={"cible": "SSH", "events": logs})).json()
        assert det["niveau"] == "alerte"
        assert det["statut"] == "a_examiner"

        # 3. Workflow : traiter la détection.
        done = (
            await ac.post(
                f"/v1/cyber/detections/{det['id']}/decision",
                json={"statut": "traitee", "commentaire": "IP bloquée"},
            )
        ).json()
        assert done["statut"] == "traitee"


async def test_parcours_grc_conformite(tmp_path) -> None:  # type: ignore[no-untyped-def]
    async with _client(tmp_path) as ac:
        # 1. Obligation fiscale.
        obl = (
            await ac.post(
                "/v1/grc/obligations",
                json={"reference": "TVA", "intitule": "Déclaration TVA", "domaine": "fiscal"},
            )
        ).json()
        oid = obl["id"]

        # Obligation sociale SANS contrôle → trou de couverture.
        await ac.post("/v1/grc/obligations", json={"intitule": "CNSS", "domaine": "social"})

        # 2. Contrôle en retard rattaché à la TVA.
        passe = (date.today() - timedelta(days=10)).isoformat()
        await ac.post(
            "/v1/grc/controls",
            json={"obligation_id": oid, "intitule": "Revue TVA", "prochaine_execution": passe},
        )

        # 3. Constat critique ouvert.
        await ac.post(
            "/v1/grc/findings",
            json={
                "obligation_id": oid,
                "intitule": "Écart de TVA collectée",
                "gravite": "critique",
                "date_constat": date.today().isoformat(),
            },
        )

        # 4. Le plan de contrôle agrège la chaîne complète.
        plan = (await ac.get("/v1/grc/plan-controle")).json()
        assert plan["nb_obligations"] == 2
        assert plan["nb_obligations_sans_controle"] == 1  # CNSS
        assert plan["nb_controls_en_retard"] == 1
        assert plan["findings_ouverts_par_gravite"]["critique"] == 1
        assert len(plan["alertes"]) >= 3
