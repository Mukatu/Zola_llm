"""CYBER-2 — détection d'anomalies sur journaux (déterministe, défensive) + registre."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from zolaos.agents.cyber.anomalies import LogEvent, ParamsDetection, detecter_anomalies
from zolaos.api.main import create_app
from zolaos.core.settings import Settings
from zolaos.db.session import get_session
from zolaos.db.store_models import StoreBase


def _ev(minute: int, type_: str, user: str = "alice", ip: str = "10.0.0.1") -> LogEvent:
    return LogEvent(
        horodatage=datetime(2026, 7, 24, 10, minute, 0), type=type_, utilisateur=user, source_ip=ip
    )


# ---------------------------------------------------------------- moteur (pur)


def test_force_brute_detectee() -> None:
    events = [_ev(m, "auth_failure") for m in range(6)]  # 6 échecs en 6 min
    res = detecter_anomalies(events)
    assert res.niveau == "alerte"
    assert any(a.code.startswith("force_brute") for a in res.anomalies)


def test_succes_apres_echecs() -> None:
    events = [_ev(m, "auth_failure") for m in range(5)] + [_ev(6, "auth_success")]
    res = detecter_anomalies(events)
    assert any(a.code == "succes_apres_echecs" for a in res.anomalies)


def test_hors_horaires() -> None:
    tard = LogEvent(horodatage=datetime(2026, 7, 24, 23, 0, 0), type="access", utilisateur="bob")
    res = detecter_anomalies([tard])
    assert any(a.code == "hors_horaires" for a in res.anomalies)


def test_ip_multiples() -> None:
    events = [
        _ev(1, "auth_success", ip="1.1.1.1"),
        _ev(2, "auth_success", ip="2.2.2.2"),
        _ev(3, "auth_success", ip="3.3.3.3"),
    ]
    res = detecter_anomalies(events)
    assert any(a.code == "ip_multiples" for a in res.anomalies)


def test_ras_aucune_anomalie() -> None:
    res = detecter_anomalies([_ev(1, "auth_success")])
    assert res.anomalies == []
    assert res.niveau == "aucun"


def test_seuils_parametrables() -> None:
    events = [_ev(m, "auth_failure") for m in range(4)]
    assert detecter_anomalies(events).anomalies == []  # < seuil 5 par défaut
    strict = detecter_anomalies(events, ParamsDetection(seuil_echecs=3))
    assert any(a.code.startswith("force_brute") for a in strict.anomalies)


# ----------------------------------------------------------------- endpoints


def _settings() -> Settings:
    return Settings(
        POSTGRES_PASSWORD_APP="x", POSTGRES_PASSWORD_MIGRATIONS="x", JWT_SECRET="x" * 32
    )


@asynccontextmanager
async def _client(tmp_path):  # type: ignore[no-untyped-def]
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/cyberdet.db")
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


_LOGS = [
    {"horodatage": "2026-07-24T10:0%d:00" % m, "type": "auth_failure", "utilisateur": "alice", "source_ip": "10.0.0.1"}
    for m in range(6)
]


async def test_anomalies_stateless(tmp_path) -> None:  # type: ignore[no-untyped-def]
    async with _client(tmp_path) as ac:
        res = (await ac.post("/v1/cyber/anomalies", json={"events": _LOGS})).json()
        assert res["niveau"] == "alerte"
        assert res["nb_echecs_auth"] == 6


async def test_detection_persistee_et_workflow(tmp_path) -> None:  # type: ignore[no-untyped-def]
    async with _client(tmp_path) as ac:
        rec = (
            await ac.post(
                "/v1/cyber/detections", json={"cible": "SSH prod", "events": _LOGS}
            )
        ).json()
        assert rec["statut"] == "a_examiner"
        assert rec["niveau"] == "alerte"
        did = rec["id"]

        listed = (await ac.get("/v1/cyber/detections")).json()["detections"]
        assert any(d["id"] == did for d in listed)

        # Statut invalide → 422.
        bad = await ac.post(f"/v1/cyber/detections/{did}/decision", json={"statut": "x"})
        assert bad.status_code == 422

        done = (
            await ac.post(
                f"/v1/cyber/detections/{did}/decision",
                json={"statut": "traitee", "commentaire": "IP bloquée"},
            )
        ).json()
        assert done["statut"] == "traitee"

        assert (await ac.delete(f"/v1/cyber/detections/{did}")).status_code == 200
        assert (await ac.get(f"/v1/cyber/detections/{did}")).status_code == 404
