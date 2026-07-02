"""Tests boucle de feedback agents — POST/GET /v1/feedback + stats.

SQLite (override de get_session). Couvre :
- création d'un feedback (POST 201 + persistance)
- liste + filtres (agent, verdict, request_id)
- statistiques up/down par agent
- rejet d'un verdict invalide (422)
"""

from __future__ import annotations

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


async def _make_client(tmp_path):  # type: ignore[no-untyped-def]
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/feedback.db")
    async with engine.begin() as conn:
        await conn.run_sync(StoreBase.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def _override():
        async with factory() as s:
            yield s

    app = create_app(settings=_settings())
    app.dependency_overrides[get_session] = _override
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


# ---------------------------------------------------------------- helpers


def _payload(**overrides: object) -> dict:  # type: ignore[type-arg]
    base: dict = {  # type: ignore[type-arg]
        "agent": "legal.ohada",
        "query": "Quels sont les délais OHADA pour une procédure collective ?",
        "response": "Selon l'AUPC, le délai est de 30 jours.",
        "verdict": "up",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------- tests


async def test_creation_feedback_et_persistance(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """POST /v1/feedback crée l'enregistrement et le retourne."""
    async with await _make_client(tmp_path) as ac:
        r = await ac.post(
            "/v1/feedback",
            json=_payload(
                request_id="req-001",
                correction=None,
                context_snapshot={"chunks": [{"id": "c1", "score": 0.92}]},
            ),
        )
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["agent"] == "legal.ohada"
        assert body["verdict"] == "up"
        assert body["request_id"] == "req-001"
        assert body["context_snapshot"] == {"chunks": [{"id": "c1", "score": 0.92}]}
        assert body["id"] is not None
        assert body["created_at"] is not None

        # vérification persistance via GET
        r2 = await ac.get("/v1/feedback")
        assert r2.status_code == 200
        feedbacks = r2.json()["feedbacks"]
        assert len(feedbacks) == 1
        assert feedbacks[0]["id"] == body["id"]


async def test_liste_filtre_par_agent(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """GET /v1/feedback?agent=X ne retourne que les feedbacks de cet agent."""
    async with await _make_client(tmp_path) as ac:
        await ac.post("/v1/feedback", json=_payload(agent="legal.ohada"))
        await ac.post("/v1/feedback", json=_payload(agent="sante.pharma"))
        await ac.post("/v1/feedback", json=_payload(agent="legal.ohada"))

        r = await ac.get("/v1/feedback", params={"agent": "legal.ohada"})
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 2
        assert all(f["agent"] == "legal.ohada" for f in data["feedbacks"])


async def test_liste_filtre_par_verdict(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """GET /v1/feedback?verdict=down ne retourne que les feedbacks négatifs."""
    async with await _make_client(tmp_path) as ac:
        await ac.post("/v1/feedback", json=_payload(verdict="up"))
        await ac.post(
            "/v1/feedback",
            json=_payload(verdict="down", correction="La réponse correcte est 45 jours."),
        )
        await ac.post("/v1/feedback", json=_payload(verdict="up"))

        r = await ac.get("/v1/feedback", params={"verdict": "down"})
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 1
        assert data["feedbacks"][0]["verdict"] == "down"
        assert data["feedbacks"][0]["correction"] == "La réponse correcte est 45 jours."


async def test_liste_filtre_par_request_id(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """GET /v1/feedback?request_id=X ne retourne que les feedbacks liés à cette requête."""
    async with await _make_client(tmp_path) as ac:
        await ac.post("/v1/feedback", json=_payload(request_id="req-A"))
        await ac.post("/v1/feedback", json=_payload(request_id="req-B"))

        r = await ac.get("/v1/feedback", params={"request_id": "req-A"})
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 1
        assert data["feedbacks"][0]["request_id"] == "req-A"


async def test_stats_up_down_par_agent(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """GET /v1/feedback/stats retourne le décompte up/down par agent."""
    async with await _make_client(tmp_path) as ac:
        # 2 up + 1 down pour legal.ohada, 1 up pour sante.pharma
        await ac.post("/v1/feedback", json=_payload(agent="legal.ohada", verdict="up"))
        await ac.post("/v1/feedback", json=_payload(agent="legal.ohada", verdict="up"))
        await ac.post("/v1/feedback", json=_payload(agent="legal.ohada", verdict="down"))
        await ac.post("/v1/feedback", json=_payload(agent="sante.pharma", verdict="up"))

        r = await ac.get("/v1/feedback/stats")
        assert r.status_code == 200
        stats = r.json()["stats"]

        assert stats["legal.ohada"]["up"] == 2
        assert stats["legal.ohada"]["down"] == 1
        assert stats["sante.pharma"]["up"] == 1
        assert stats["sante.pharma"]["down"] == 0


async def test_stats_filtre_par_agent(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """GET /v1/feedback/stats?agent=X limite les stats à cet agent."""
    async with await _make_client(tmp_path) as ac:
        await ac.post("/v1/feedback", json=_payload(agent="legal.ohada", verdict="up"))
        await ac.post("/v1/feedback", json=_payload(agent="sante.pharma", verdict="up"))

        r = await ac.get("/v1/feedback/stats", params={"agent": "legal.ohada"})
        assert r.status_code == 200
        stats = r.json()["stats"]
        assert "legal.ohada" in stats
        assert "sante.pharma" not in stats


async def test_rejet_verdict_invalide_422(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """POST /v1/feedback avec un verdict invalide retourne 422."""
    async with await _make_client(tmp_path) as ac:
        r = await ac.post("/v1/feedback", json=_payload(verdict="neutre"))
        assert r.status_code == 422, r.text


async def test_rejet_verdict_invalide_liste_400(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """GET /v1/feedback?verdict=invalide retourne 400."""
    async with await _make_client(tmp_path) as ac:
        r = await ac.get("/v1/feedback", params={"verdict": "neutre"})
        assert r.status_code == 400, r.text
