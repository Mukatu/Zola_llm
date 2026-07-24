"""Parcours end-to-end — Fintech (crédit EMF).

Chaîne complète : dossier scoré → décision humaine → décaissement + échéancier →
encaissement d'une échéance → le portefeuille agrégé le reflète → snapshot
d'historisation. Déterministe, sans LLM.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from decimal import Decimal

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
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/parcours_fintech.db")
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


_DOSSIER = {
    "revenu_mensuel_xaf": "500000",
    "charges_mensuelles_xaf": "50000",
    "montant_demande_xaf": "1200000",
    "duree_mois": 12,
    "anciennete_activite_mois": 36,
    "incidents_paiement": 0,
    "epargne_xaf": "300000",
    "garanties_xaf": "1000000",
    "type_emploi": "salarie_public",
}


async def test_parcours_credit_complet(tmp_path) -> None:  # type: ignore[no-untyped-def]
    async with _client(tmp_path) as ac:
        # 1. Créer et scorer un dossier → statut "evaluee".
        app = (
            await ac.post(
                "/v1/fintech/applications",
                json={"client": "Awa N.", "dossier": _DOSSIER, "numero": "C-001"},
            )
        ).json()
        assert app["statut"] == "evaluee"
        assert app["score"] >= 0
        aid = app["id"]

        # 2. Décision humaine : accorder (le statut pilote le workflow, pas la reco).
        dec = (
            await ac.post(f"/v1/fintech/applications/{aid}/decision", json={"statut": "accordee"})
        ).json()
        assert dec["statut"] == "accordee"

        # 3. Décaisser → génère l'échéancier, statut "decaissee".
        disb = await ac.post(
            f"/v1/fintech/applications/{aid}/disburse",
            json={"date_decaissement": "2026-07-01", "taux_annuel": "0.18"},
        )
        assert disb.status_code == 200

        sched = (await ac.get(f"/v1/fintech/applications/{aid}/schedule")).json()
        echeances = sched["echeances"] if "echeances" in sched else sched.get("installments", sched)
        assert len(echeances) == 12  # 12 mois

        # 4. Le portefeuille agrégé reflète le prêt décaissé.
        pf1 = (await ac.get("/v1/fintech/portfolio")).json()
        assert pf1["nb_dossiers"] == 1
        assert Decimal(pf1["encours_decaisse_xaf"]) > 0
        encours_avant = Decimal(pf1["encours_restant_du_xaf"])

        # 5. Encaisser la 1re échéance → l'encours restant dû baisse.
        first = echeances[0]
        pay = await ac.post(f"/v1/fintech/installments/{first['id']}/pay", json={})
        assert pay.status_code == 200
        pf2 = (await ac.get("/v1/fintech/portfolio")).json()
        assert Decimal(pf2["encours_restant_du_xaf"]) < encours_avant

        # 6. Historisation : un snapshot capture l'état, l'historique le retrouve.
        await ac.post("/v1/fintech/portfolio/snapshot")
        hist = (await ac.get("/v1/fintech/portfolio/history")).json()["history"]
        assert len(hist) == 1
        assert hist[0]["nb_dossiers"] == 1
