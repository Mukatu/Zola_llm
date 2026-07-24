"""Cyber-1 — audit de durcissement déterministe (défensif) + registre persisté."""

from __future__ import annotations

from contextlib import asynccontextmanager
from decimal import Decimal

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from zolaos.agents.cyber.hardening import BASELINE, ConfigAudit, auditer
from zolaos.api.main import create_app
from zolaos.core.settings import Settings
from zolaos.db.session import get_session
from zolaos.db.store_models import StoreBase

# ---------------------------------------------------------------- moteur (pur)


def test_tout_conforme_score_100() -> None:
    faits = {c.cle: True for c in BASELINE}
    res = auditer(ConfigAudit(**faits))
    assert res.nb_conforme == len(BASELINE)
    assert res.nb_non_conforme == 0
    assert res.score_conformite == Decimal("100.0")
    assert res.niveau == "aucun"


def test_non_renseigne_est_a_verifier() -> None:
    """Config vide → tout « à vérifier », rien n'est fabriqué en conforme/non conforme."""
    res = auditer(ConfigAudit())
    assert res.nb_a_verifier == len(BASELINE)
    assert res.nb_conforme == 0 and res.nb_non_conforme == 0
    assert res.score_conformite == Decimal("0")


def test_non_conformite_critique_remonte_le_niveau() -> None:
    # MFA admin (critical) non conforme, le reste conforme.
    faits = {c.cle: True for c in BASELINE}
    faits["mfa_admin"] = False
    res = auditer(ConfigAudit(**faits))
    assert res.nb_non_conforme == 1
    assert res.niveau == "critical"
    # Les non-conformités passent en tête des findings.
    assert res.findings[0].statut == "non_conforme"
    assert res.findings[0].cle == "mfa_admin"


def test_score_partiel() -> None:
    # 2 conformes, 2 non conformes, reste à vérifier → 50 %.
    res = auditer(
        ConfigAudit(mfa_admin=True, tls_applique=True, correctifs_a_jour=False, pare_feu_deny=False)
    )
    assert res.nb_conforme == 2 and res.nb_non_conforme == 2
    assert res.score_conformite == Decimal("50.0")


# ----------------------------------------------------------------- endpoints


def _settings() -> Settings:
    return Settings(
        POSTGRES_PASSWORD_APP="x", POSTGRES_PASSWORD_MIGRATIONS="x", JWT_SECRET="x" * 32
    )


@asynccontextmanager
async def _client(tmp_path):  # type: ignore[no-untyped-def]
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/cyber.db")
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


async def test_audit_stateless(tmp_path) -> None:  # type: ignore[no-untyped-def]
    async with _client(tmp_path) as ac:
        res = (await ac.post("/v1/cyber/audit", json={"mfa_admin": False})).json()
        assert res["nb_non_conforme"] == 1
        assert res["niveau"] == "critical"
        assert any(f["cle"] == "mfa_admin" for f in res["findings"])


async def test_audit_persiste_et_registre(tmp_path) -> None:  # type: ignore[no-untyped-def]
    async with _client(tmp_path) as ac:
        rec = (
            await ac.post(
                "/v1/cyber/audits",
                json={"cible": "Serveur ERP", "config": {"mfa_admin": True, "sauvegardes_testees": False}},
            )
        ).json()
        assert rec["cible"] == "Serveur ERP"
        assert rec["nb_non_conforme"] == 1
        assert rec["niveau"] == "critical"
        aid = rec["id"]

        listed = (await ac.get("/v1/cyber/audits")).json()["audits"]
        assert any(a["id"] == aid for a in listed)

        assert (await ac.delete(f"/v1/cyber/audits/{aid}")).status_code == 200
        assert (await ac.get(f"/v1/cyber/audits/{aid}")).status_code == 404


async def test_baseline_endpoint(tmp_path) -> None:  # type: ignore[no-untyped-def]
    async with _client(tmp_path) as ac:
        data = (await ac.get("/v1/cyber/baseline")).json()
        assert len(data["controles"]) == len(BASELINE)
